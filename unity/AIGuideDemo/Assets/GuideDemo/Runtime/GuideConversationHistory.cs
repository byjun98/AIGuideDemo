using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace AIGuide.Demo
{
    public class GuideConversationHistory : MonoBehaviour, IPointerDownHandler
    {
        public RectTransform content;
        public ScrollRect scroll;
        public Font font;
        public bool explanationMode = true;
        public int maxMessages = 16;
        readonly List<Message> messages = new List<Message>();
        class Message { public string speaker, line, reason, badges; public bool player; }

        public void AddPlayer(string line) => Add(new Message { speaker = "플레이어", line = line, player = true });

        public void AddCharacter(string speaker, string line, string trigger, GuideState state, GuideResponse response, PackData pack)
        {
            string reason = trigger == GuideTriggers.IdleTick ? "(대기 " + state.idle_seconds + "초)"
                : trigger == GuideTriggers.ScreenEnter ? "(화면 진입)"
                : trigger == GuideTriggers.ActionFailed ? "(실패 후 안내)" : "";
            var badges = new List<string>();
            if (response != null)
            {
                if (response.refusal == "locked") badges.Add("잠긴 기능 거절");
                if (response.refusal == "spoiler") badges.Add("스포일러 차단");
                if (response.refusal == "out_of_scope") badges.Add("관계없는 질문 거절");
                if (response.risk == "replaced") badges.Add("서버 대체 대사");
                if (!string.IsNullOrEmpty(response.ui_target))
                {
                    var system = pack.systems.Find(s => s.ui_target == response.ui_target);
                    var step = pack.tutorial_steps.Find(s => s.ui_target == response.ui_target);
                    badges.Add("강조: " + (system != null ? system.name : step != null ? step.action_label : response.ui_target));
                }
                if (response.debug != null && response.debug.issues != null && response.debug.issues.Length > 0)
                    badges.Add("검사: " + string.Join(", ", response.debug.issues));
            }
            else badges.Add("연결 실패");
            Add(new Message { speaker = speaker, line = line, reason = reason, badges = string.Join(" · ", badges) });
        }

        void Add(Message message)
        {
            messages.Add(message);
            while (messages.Count > maxMessages) messages.RemoveAt(0);
            Render();
        }

        public void SetExplanationMode(bool enabled)
        {
            explanationMode = enabled;
            Render();
        }

        static string Escape(string text) => (text ?? "").Replace("<", "＜").Replace(">", "＞");

        void Render()
        {
            if (content == null || font == null) return;
            foreach (Transform child in content) { child.gameObject.SetActive(false); Destroy(child.gameObject); }
            float availableWidth = content.rect.width > 1 ? content.rect.width : 900;
            foreach (var message in messages)
            {
                var row = new GameObject("Message", typeof(RectTransform), typeof(LayoutElement)).GetComponent<RectTransform>();
                row.SetParent(content, false);
                var bubble = new GameObject(message.player ? "PlayerBubble" : "CharacterBubble", typeof(RectTransform), typeof(Image)).GetComponent<RectTransform>();
                bubble.SetParent(row, false);
                bubble.anchorMin = new Vector2(message.player ? .15f : 0, 0);
                bubble.anchorMax = new Vector2(message.player ? 1 : .85f, 1);
                bubble.offsetMin = new Vector2(4, 4); bubble.offsetMax = new Vector2(-4, -4);
                var background = bubble.GetComponent<Image>();
                background.color = message.player ? new Color(.12f, .24f, .34f, .95f) : new Color(.10f, .12f, .17f, .95f);
                background.raycastTarget = false;
                var label = new GameObject("Text", typeof(RectTransform), typeof(Text)).GetComponent<Text>();
                label.transform.SetParent(bubble, false);
                label.font = font; label.fontSize = 22; label.color = Color.white;
                label.alignment = TextAnchor.UpperLeft; label.raycastTarget = false;
                label.horizontalOverflow = HorizontalWrapMode.Wrap; label.verticalOverflow = VerticalWrapMode.Overflow;
                label.supportRichText = true;
                label.text = "<size=17><b>" + Escape(message.speaker) + "</b> " + Escape(message.reason) + "</size>\n" + Escape(message.line);
                if (explanationMode && !string.IsNullOrEmpty(message.badges)) label.text += "\n<size=16><color=#C9D9EE>" + Escape(message.badges) + "</color></size>";
                var rect = label.rectTransform;
                rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one;
                rect.offsetMin = new Vector2(12, 10); rect.offsetMax = new Vector2(-12, -10);
                var settings = label.GetGenerationSettings(new Vector2(availableWidth * .85f - 32, 0));
                float height = label.cachedTextGeneratorForLayout.GetPreferredHeight(label.text, settings) / label.pixelsPerUnit;
                row.GetComponent<LayoutElement>().preferredHeight = height + 32;
            }
            Canvas.ForceUpdateCanvases();
            LayoutRebuilder.ForceRebuildLayoutImmediate(content);
            if (scroll != null) scroll.verticalNormalizedPosition = 0;
        }

        public void OnPointerDown(PointerEventData eventData)
        {
            var system = EventSystem.current;
            if (system != null && system.currentSelectedGameObject != null && system.currentSelectedGameObject.GetComponent<InputField>() != null)
                system.SetSelectedGameObject(null);
        }
    }
}
