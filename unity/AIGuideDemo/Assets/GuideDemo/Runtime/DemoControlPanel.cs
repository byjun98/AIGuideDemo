using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UnityEngine.InputSystem;
using AIGuide;

namespace AIGuide.Demo
{
    public class DemoControlPanel : MonoBehaviour
    {
        public GuideDirector director;
        public DemoOutpostAdapter game;
        public InputField input;
        public Text modelLabel;
        public Text voiceLabel;
        public Slider storySlider;
        public Text storyLabel;
        public GuideConversationHistory history;
        public Button[] suggestionButtons = new Button[3];
        public Text[] suggestionLabels = new Text[3];
        public Text[] suggestionCategories = new Text[3];
        public List<GuideCharacterProfile> characters = new List<GuideCharacterProfile>();
        [Tooltip("켜면 게임은 그대로 두고 캐릭터만 바꾼다(처음 보는 게임에서 규칙을 지키는지 보여 줄 때)")]
        public bool crossGame = false;
        readonly HashSet<string> askedQuestions = new HashSet<string>();
        GuideSuggestion[] suggestions;
        int completedTurns;

        void OnEnable()
        {
            if (director == null || game == null) return;
            director.PlayerUtterance += OnPlayerUtterance;
            director.ResponsePresented += OnResponsePresented;
            director.TurnFinished += OnTurnFinished;
            game.ScreenChanged += OnContextChanged;
            game.StepCompleted += OnContextChanged;
        }

        void OnDisable()
        {
            if (director != null)
            {
                director.PlayerUtterance -= OnPlayerUtterance;
                director.ResponsePresented -= OnResponsePresented;
                director.TurnFinished -= OnTurnFinished;
            }
            if (game != null)
            {
                game.ScreenChanged -= OnContextChanged;
                game.StepCompleted -= OnContextChanged;
            }
        }

        void Start()
        {
            if (input != null) input.onEndEdit.AddListener(OnInputEndEdit);
            if (director.voice != null)
                director.voice.RecordingChanged += OnRecordingChanged;
            UpdateLabel();
            RefreshStoryRange();
            RefreshSuggestions();
        }

        void OnDestroy()
        {
            if (input != null) input.onEndEdit.RemoveListener(OnInputEndEdit);
            if (director != null && director.voice != null) director.voice.RecordingChanged -= OnRecordingChanged;
        }

        void OnInputEndEdit(string text)
        {
            var keyboard = Keyboard.current;
            if (keyboard != null && (keyboard.enterKey.wasPressedThisFrame || keyboard.numpadEnterKey.wasPressedThisFrame)) Send();
        }

        void OnRecordingChanged(bool on)
        {
            if (voiceLabel) voiceLabel.text = on ? "듣는 중..." : "V 키를 누르고 말하기";
        }

        public void Send()
        {
            if (input == null || string.IsNullOrWhiteSpace(input.text)) return;
            director.Ask(input.text);
            input.text = "";
        }

        public void UseBaseModel() { director.modelOverride = "lora:base"; UpdateLabel(); }
        public void UseLoraModel() { director.modelOverride = ""; UpdateLabel(); }
        public void TogglePolicy() { director.policy.enabled = !director.policy.enabled; UpdateLabel(); }

        public void SwapCharacter(int index)
        {
            if (index < 0 || index >= characters.Count) return;
            var next = characters[index];
            if (!crossGame && !string.IsNullOrEmpty(next.homeScene) && next.homeScene != SceneManager.GetActiveScene().name)
            {
                SceneManager.LoadScene(next.homeScene);
                return;
            }
            director.SwapCharacter(next);
            director.modelOverride = "";
            RefreshStoryRange();
            RefreshSuggestions();
            UpdateLabel();
        }

        void RefreshStoryRange()
        {
            if (storySlider == null || director.character == null) return;
            var chapters = director.character.storyChapters;
            int max = 0;
            foreach (var chapter in chapters) max = Mathf.Max(max, chapter.index);
            storySlider.minValue = 0;
            storySlider.maxValue = max;
            storySlider.wholeNumbers = true;
            game.storyChapter = Mathf.Clamp(game.storyChapter, 0, max);
            storySlider.SetValueWithoutNotify(game.storyChapter);
            UpdateStoryLabel();
        }

        public void SetStoryChapter(float value)
        {
            if (game.storyChapter != Mathf.RoundToInt(value)) director.InvalidateContext();
            game.storyChapter = Mathf.RoundToInt(value);
            UpdateStoryLabel();
            RefreshSuggestions();
        }

        void UpdateStoryLabel()
        {
            var chapter = director.character.storyChapters.Find(c => c.index == game.storyChapter);
            if (storyLabel != null) storyLabel.text = "스토리 진행도: " + (chapter != null ? chapter.name : "시작 전");
        }

        public void SetAffection(float v) { director.InvalidateContext(); game.SetAffection(v); RefreshSuggestions(); }
        public void CheatThreeMissions() { game.CheatMissions(3); RefreshSuggestions(); }

        void OnPlayerUtterance(string text)
        {
            askedQuestions.Add(text);
            history?.AddPlayer(text);
            foreach (var button in suggestionButtons) if (button != null) button.interactable = false;
        }

        void OnResponsePresented(GuideResponse response, string trigger, GuideState state, string line)
        {
            history?.AddCharacter(director.character.displayName, line, trigger, state, response, game.Pack.Data);
        }

        void OnTurnFinished() { completedTurns++; RefreshSuggestions(); }
        void OnContextChanged(string id) => RefreshSuggestions();

        public void SetExplanationMode(bool enabled) => history?.SetExplanationMode(enabled);

        public void SendSuggestion(int index)
        {
            if (suggestions == null || index < 0 || index >= suggestions.Length || suggestions[index] == null) return;
            director.Ask(suggestions[index].question);
        }

        void RefreshSuggestions()
        {
            if (director == null || director.character == null || game == null || game.Pack == null) return;
            suggestions = GuideSuggestionProvider.GetSuggestions(game.Pack.Data, director.CaptureState(), director.character, askedQuestions, completedTurns);
            for (int i = 0; i < 3; i++)
            {
                var suggestion = suggestions[i];
                if (i < suggestionLabels.Length && suggestionLabels[i] != null)
                    suggestionLabels[i].text = suggestion != null ? suggestion.question : "직접 질문해 주세요";
                if (i < suggestionCategories.Length && suggestionCategories[i] != null)
                    suggestionCategories[i].text = suggestion != null ? suggestion.category : "질문 확인 완료";
                if (i < suggestionButtons.Length && suggestionButtons[i] != null)
                    suggestionButtons[i].interactable = suggestion != null && director.CurrentPhase != GuideDirector.Phase.Thinking;
            }
        }

        void UpdateLabel()
        {
            if (modelLabel == null) return;
            string model = string.IsNullOrEmpty(director.modelOverride) ? director.character.modelKey : director.modelOverride;
            modelLabel.text = $"캐릭터 {director.character.displayName} · 모델 {model} · 규칙 정책 {(director.policy.enabled ? "켜짐" : "꺼짐")}";
        }
    }
}
