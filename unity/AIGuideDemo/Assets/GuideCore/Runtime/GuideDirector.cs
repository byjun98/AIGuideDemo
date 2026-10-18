using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;

namespace AIGuide
{
    public class GuideDirector : MonoBehaviour
    {
        public enum Phase { Idle, Thinking, Speaking }

        [Header("교체 가능한 구성 요소")]
        public GuideCharacterProfile character;
        public GuideGameAdapterBase game;
        [Tooltip("IGuidePresenter를 구현한 컴포넌트(2D: GuideSpritePresenter, 3D: GuideAvatarPresenter)")]
        public MonoBehaviour presenterBehaviour;
        IGuidePresenter presenter => presenterBehaviour as IGuidePresenter;
        public GuideHighlighter highlighter;
        public GuideApiClient api;
        public GuideVoiceInput voice;
        public GuideTurnLogger logger;
        [Tooltip("캐릭터별 배경과 UI 테마를 적용한다(없어도 된다)")]
        public GuideUiTheme theme;

        [Header("정책")]
        public GuideSpeakPolicy policy = new GuideSpeakPolicy();
        [Tooltip("모델 응답이 이 시간보다 늦으면 고정 대사를 먼저 보여 준다")]
        public float latencyCoverSeconds = 1.2f;
        public float idleTickInterval = 5f;
        [Tooltip("비워 두면 캐릭터 프로필의 modelKey를 쓴다(base / lora 비교용)")]
        public string modelOverride = "";

        public Phase CurrentPhase { get; private set; } = Phase.Idle;
        public GuideResponse LastResponse { get; private set; }
        public event System.Action<string> PlayerUtterance;
        public event System.Action<GuideResponse, string, GuideState, string> ResponsePresented;
        public event System.Action TurnFinished;

        GuideCommandExecutor _exec;
        float _lastInputTime, _lastLineTime = -999f, _nextIdleTick;
        int _failCount;
        string _lastFailStep;
        int _requestSerial;
        int _inFlight;

        void Awake()
        {
            if (character == null || game == null || api == null || presenter == null)
            {
                Debug.LogError("[GuideDirector] Character, game, API and presenter references are required.", this);
                enabled = false;
            }
        }

        void OnEnable()
        {
            if (game == null) return;
            game.ActionFailed += OnActionFailed;
            game.ScreenChanged += OnScreenChanged;
            game.StepCompleted += OnStepCompleted;
            if (voice != null) voice.Transcribed += OnTranscribed;
        }

        void OnDisable()
        {
            if (game != null)
            {
                game.ActionFailed -= OnActionFailed;
                game.ScreenChanged -= OnScreenChanged;
                game.StepCompleted -= OnStepCompleted;
            }
            if (voice != null) voice.Transcribed -= OnTranscribed;
            _requestSerial++;
            StopAllCoroutines();
            _inFlight = 0;
            CurrentPhase = Phase.Idle;
            presenter?.ShowThinking(false);
        }

        void Start()
        {
            _exec = new GuideCommandExecutor(game, highlighter);
            presenter.Bind(character);
            theme?.Apply(character);
            _lastInputTime = Time.unscaledTime;
        }

        void OnScreenChanged(string screen)
        {
            _lastInputTime = Time.unscaledTime;
            _requestSerial++;
            Request(GuideTriggers.ScreenEnter, null);
        }

        void OnStepCompleted(string step)
        {
            _failCount = 0;
            _requestSerial++;
            highlighter?.Hide();
        }

        void OnTranscribed(string text, float ms) => Ask(text, ms);

        public void SwapCharacter(GuideCharacterProfile next)
        {
            if (next == null) return;
            _requestSerial++;
            character = next;
            presenter.Bind(next);
            theme?.Apply(next);
            highlighter?.Hide();
        }

        public void Ask(string text, float sttMs = 0f)
        {
            if (string.IsNullOrWhiteSpace(text)) return;
            _lastInputTime = Time.unscaledTime;
            PlayerUtterance?.Invoke(text.Trim());
            Request(GuideTriggers.PlayerUtterance, text.Trim(), sttMs);
        }

        public void NotifyPlayerActivity() => _lastInputTime = Time.unscaledTime;

        public void InvalidateContext()
        {
            _requestSerial++;
            LastResponse = null;
            CurrentPhase = Phase.Idle;
            presenter?.ShowThinking(false);
            presenter?.Clear();
            highlighter?.Hide();
        }

        void OnActionFailed(string wrongTarget)
        {
            var st = new GuideState(); game.FillState(st);
            if (_lastFailStep != st.tutorial_step) { _failCount = 0; _lastFailStep = st.tutorial_step; }
            _failCount++;
            _lastInputTime = Time.unscaledTime;
            Request(GuideTriggers.ActionFailed, null);
        }

        void Update()
        {
            if ((Keyboard.current != null && Keyboard.current.anyKey.wasPressedThisFrame) ||
                (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame)) _lastInputTime = Time.unscaledTime;
            if (Time.unscaledTime >= _nextIdleTick)
            {
                _nextIdleTick = Time.unscaledTime + idleTickInterval;
                if (CurrentPhase == Phase.Idle) Request(GuideTriggers.IdleTick, null);
            }
        }

        public GuideState CaptureState()
        {
            var s = new GuideState();
            game.FillState(s);
            var chapter = character.storyChapters.Find(c => c.index == s.story_chapter);
            s.story_name = chapter != null ? chapter.name : "";
            s.idle_seconds = Mathf.FloorToInt(Time.unscaledTime - _lastInputTime);
            s.seconds_since_last_line = Mathf.Min(9999, Mathf.FloorToInt(Time.unscaledTime - _lastLineTime));
            s.fail_count = _failCount;
            s.visible_targets = new System.Collections.Generic.List<string>();
            foreach (var id in GuideUiTarget.ActiveIds())
                if (game.IsTargetAvailable(id)) s.visible_targets.Add(id);
            return s;
        }

        void Request(string trigger, string input, float sttMs = 0f)
        {
            var state = CaptureState();
            string model = string.IsNullOrEmpty(modelOverride) ? character.modelKey : modelOverride;
            string silence = policy.Check(trigger, state);
            if (silence != null)
            {
                if (trigger != GuideTriggers.IdleTick)
                    logger?.Write(new GuideTurnLogger.Turn { character = character.serverCharacterId, model = model, trigger = trigger,
                        step = state.tutorial_step, policy_silence = silence });
                return;
            }
            if (trigger != GuideTriggers.PlayerUtterance && trigger != GuideTriggers.ScreenEnter && CurrentPhase == Phase.Thinking) return;
            int serial = ++_requestSerial;
            StartCoroutine(Run(trigger, input, state, model, sttMs, serial));
        }

        IEnumerator Run(string trigger, string input, GuideState state, string model, float sttMs, int serial)
        {
            _inFlight++;
            CurrentPhase = Phase.Thinking;
            presenter.ShowThinking(true);
            var turn = new GuideTurnLogger.Turn { character = character.serverCharacterId, model = model, trigger = trigger,
                player_input = input, step = state.tutorial_step, stt_ms = sttMs };
            var req = new GuideRequest { trigger = trigger, player_input = input ?? "", state = state,
                character_id = character.serverCharacterId, model = model,
                game_id = game.Pack != null && game.Pack.Data != null ? game.Pack.Data.game_id : null };

            GuideResponse resp = null; float sec = 0; string err = null; bool done = false;
            logger?.BeginWait();
            StartCoroutine(api.Generate(req, (r, s, e) => { resp = r; sec = s; err = e; done = true; }));
            float t0 = Time.unscaledTime;
            while (!done)
            {
                logger?.TickWait();
                if (serial == _requestSerial && !turn.cover_shown && Time.unscaledTime - t0 > latencyCoverSeconds && trigger == GuideTriggers.PlayerUtterance)
                {
                    turn.cover_shown = true;
                    presenter.Say(character.Pick(character.thinkingLines, "확인하겠습니다."), "neutral", "nod");
                    presenter.ShowThinking(true);
                }
                yield return null;
            }
            _inFlight--;
            turn.request_ms = sec * 1000f;
            turn.fps_during_wait = logger != null ? logger.WaitFps() : 0;
            if (serial != _requestSerial)
            {
                turn.error = "stale_response"; logger?.Write(turn);
                if (_inFlight == 0 && CurrentPhase == Phase.Thinking) { CurrentPhase = Phase.Idle; presenter.ShowThinking(false); }
                yield break;
            }

            if (resp == null)
            {
                turn.error = err;
                string errorLine = character.Pick(character.errorLines, "지금은 응답할 수 없습니다.");
                presenter.Say(errorLine, "neutral", "idle");
                ResponsePresented?.Invoke(null, trigger, state, errorLine);
                Finish(turn); yield break;
            }
            LastResponse = resp;
            turn.speak = resp.speak; turn.line = resp.line; turn.ui_target = resp.ui_target; turn.risk = resp.risk;
            turn.server_llm_ms = resp.debug != null ? resp.debug.llm_ms : 0;

            if (!resp.speak)
            {
                presenter.ShowThinking(false);
                if (turn.cover_shown) presenter.Clear();
                Finish(turn); yield break;
            }
            var result = _exec.Execute(resp);
            turn.exec_stage = result.stage; turn.exec_reason = result.reason;
            if (!result.ok)
            {
                string fallback = character.Pick(character.targetMissingLines, "표시할 위치를 찾지 못했습니다. 화면을 확인해 주십시오.");
                presenter.Say(fallback, "worried", "idle");
                ResponsePresented?.Invoke(resp, trigger, state, fallback);
            }
            else
            {
                presenter.Say(resp.line, resp.emotion, resp.motion);
                ResponsePresented?.Invoke(resp, trigger, state, resp.line);
            }
            _lastLineTime = Time.unscaledTime;
            CurrentPhase = Phase.Speaking;
            Finish(turn);
            yield return new WaitForSecondsRealtime(Mathf.Clamp((resp.line ?? "").Length / 14f, 1.5f, 6f));
            if (serial == _requestSerial && CurrentPhase == Phase.Speaking) CurrentPhase = Phase.Idle;
        }

        void Finish(GuideTurnLogger.Turn t)
        {
            logger?.Write(t);
            if (CurrentPhase == Phase.Thinking) CurrentPhase = Phase.Idle;
            TurnFinished?.Invoke();
        }
    }
}
