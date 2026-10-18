using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using AIGuide;

namespace AIGuide.Demo
{
    public class DemoOutpostAdapter : GuideGameAdapterBase
    {
        [Header("데이터")]
        public GuideGamePack pack;
        [Range(0, 100)] public int affection = 60;
        public int storyChapter;

        [Header("화면 패널 (이름 = 화면 ID)")]
        public List<GameObject> screens = new List<GameObject>();
        public GameObject resultOverlay;
        public Text statusText;
        public InputField chatInput;

        int _missions, _enhances, _formed, _purchases, _researchStarted;
        string _screen = "lobby";
        bool _resultPlaying;
        int _stepIndex;

        public override GuideGamePack Pack => pack;

        string StepId => pack.Data.tutorial_steps[Mathf.Min(_stepIndex, pack.Data.tutorial_steps.Count - 1)].id;

        void Start()
        {
            ShowScreen("lobby");
            Refresh();
        }

        public override void FillState(GuideState s)
        {
            var step = pack.Step(StepId);
            s.tutorial_step = step.id;
            s.tutorial_goal = step.goal;
            s.tutorial_screen = step.system;
            s.tutorial_target = string.IsNullOrEmpty(step.ui_target) ? null : step.ui_target;
            s.unlocked_systems = Unlocked();
            s.missions_cleared = _missions;
            s.screen = _resultPlaying ? "result" : _screen;
            s.result_playing = _resultPlaying;
            s.in_cutscene = false;
            s.player_typing = chatInput != null && chatInput.isFocused && chatInput.text.Length > 0;
            s.affection = affection;
            s.story_chapter = storyChapter;
            s.affection_band = affection <= 20 ? "cautious" : affection <= 50 ? "friendly" : affection <= 80 ? "trust" : "special_trust";
        }

        public List<string> Unlocked()
        {
            var list = new List<string>();
            foreach (var sys in pack.Data.systems)
            {
                var u = sys.unlock;
                bool open = u == null || u.type == "always"
                    || (u.type == "missions_cleared" && _missions >= u.value)
                    || (u.type == "enhance_count" && _enhances >= u.value);
                if (open) list.Add(sys.id);
            }
            return list;
        }

        public override bool IsTargetAvailable(string targetId)
        {
            if (_resultPlaying) return false;
            foreach (var sys in pack.Data.systems)
                if (sys.ui_target == targetId) return Unlocked().Contains(sys.id) && _screen == "lobby";
            return GuideUiTarget.TryGet(targetId, out _);
        }

        public override string ResolveTarget(string targetId)
        {
            if (_resultPlaying) return null;
            string owner = null;
            foreach (var st in pack.Data.tutorial_steps) if (st.ui_target == targetId) owner = st.system;
            if (_screen == "lobby")
            {
                var sys = owner != null ? pack.System(owner) : null;
                return sys != null ? sys.ui_target : null;
            }
            return owner == _screen ? null : "btn_back";
        }

        public void OpenSystem(string systemId)
        {
            if (!Unlocked().Contains(systemId)) { RaiseActionFailed(pack.System(systemId)?.ui_target ?? systemId); Flash("아직 잠겨 있습니다"); return; }
            ShowScreen(systemId);
            RaiseScreenChanged(systemId);
        }

        public void Back() { ShowScreen("lobby"); RaiseScreenChanged("lobby"); }

        string StepAt(int i) => i < pack.Data.tutorial_steps.Count ? pack.Data.tutorial_steps[i].id : "";
        string SortieSystem => pack.Data.tutorial_steps.Count > 1 ? pack.Data.tutorial_steps[1].system : "";

        public void StepAction(string systemId)
        {
            int role = pack.Data.tutorial_steps.FindIndex(st => st.system == systemId);
            switch (role)
            {
                case 0:
                    _formed = Mathf.Min(5, _formed + 1);
                    Flash($"편성 {_formed}/5");
                    TryComplete(StepAt(0), _formed >= 1);
                    break;
                case 1:
                    if (_formed < 1) { RaiseActionFailed(pack.Data.tutorial_steps[1].ui_target); Flash("먼저 편성을 해야 합니다"); return; }
                    StartCoroutine(PlayResult());
                    break;
                case 2:
                    _enhances++; Flash("성장 완료"); TryComplete(StepAt(2), true);
                    break;
                case 3:
                    _purchases++; Flash("수령 완료"); TryComplete(StepAt(3), true);
                    break;
                default:
                    _researchStarted++; Flash("시작했습니다"); TryComplete(StepAt(5), true);
                    break;
            }
        }

        IEnumerator PlayResult()
        {
            _resultPlaying = true;
            if (resultOverlay != null) resultOverlay.SetActive(true);
            yield return new WaitForSecondsRealtime(4f);
            if (resultOverlay != null) resultOverlay.SetActive(false);
            _resultPlaying = false;
            OnMissionCleared();
        }

        void OnMissionCleared()
        {
            _missions++;
            ShowScreen("lobby");
            TryComplete(StepAt(1), true);
            TryComplete(StepAt(4), _missions >= 3);
            Refresh();
            RaiseScreenChanged("lobby");
        }

        public void SkipResult() { if (_resultPlaying) StopAllCoroutines(); if (_resultPlaying) { _resultPlaying = false; if (resultOverlay) resultOverlay.SetActive(false); OnMissionCleared(); } }

        public void WrongClick(string id) => RaiseActionFailed(id);

        public void CheatMissions(int n)
        {
            _missions = n;
            if (n >= 1 && _stepIndex < 2) _stepIndex = 2;
            TryComplete(StepAt(4), _missions >= 3);
            Refresh();
        }
        public void SetAffection(float v) { affection = Mathf.RoundToInt(v); Refresh(); }

        void TryComplete(string stepId, bool cond)
        {
            if (!cond || StepId != stepId) { Refresh(); return; }
            _stepIndex++;
            RaiseStepCompleted(stepId);
            Refresh();
        }

        void ShowScreen(string id)
        {
            _screen = id;
            foreach (var s in screens) if (s != null) s.SetActive(s.name == id);
            Refresh();
        }

        void Refresh()
        {
            if (statusText == null || pack == null) return;
            var step = pack.Step(StepId);
            statusText.text = $"[{pack.Data.display_name}]\n단계: {step.goal}\n임무 {_missions} · 성장 {_enhances} · 호감도 {affection}\n해금: {string.Join(", ", Unlocked())}";
        }

        void Flash(string msg) { if (statusText != null) statusText.text = msg + "\n" + statusText.text; }
    }
}
