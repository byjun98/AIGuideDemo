using UnityEngine;
using UnityEngine.UI;

namespace AIGuide
{
    public class GuideHighlighter : MonoBehaviour
    {
        public RectTransform frame;
        public float padding = 14f;
        public float pulseSpeed = 4f;
        public float autoHideSeconds = 8f;

        RectTransform _target;
        float _shownAt;
        CanvasGroup _group;
        readonly Vector3[] corners = new Vector3[4];

        void Awake()
        {
            if (frame != null) { if (!frame.TryGetComponent(out _group)) _group = frame.gameObject.AddComponent<CanvasGroup>(); _group.blocksRaycasts = false; frame.gameObject.SetActive(false); }
        }

        public void Show(RectTransform target)
        {
            _target = target;
            _shownAt = Time.unscaledTime;
            if (frame != null) frame.gameObject.SetActive(true);
            Follow();
        }

        public void Hide()
        {
            _target = null;
            if (frame != null) frame.gameObject.SetActive(false);
        }

        public bool IsShowing(string targetId) => _target != null && _target.GetComponent<GuideUiTarget>()?.targetId == targetId;

        void LateUpdate()
        {
            if (_target == null || frame == null) return;
            if (!_target.gameObject.activeInHierarchy || Time.unscaledTime - _shownAt > autoHideSeconds) { Hide(); return; }
            Follow();
            if (_group != null) _group.alpha = 0.7f + 0.3f * Mathf.Sin(Time.unscaledTime * pulseSpeed);
        }

        void Follow()
        {
            _target.GetWorldCorners(corners);
            var parent = frame.parent as RectTransform;
            Vector2 min = parent.InverseTransformPoint(corners[0]);
            Vector2 max = parent.InverseTransformPoint(corners[2]);
            frame.anchorMin = frame.anchorMax = new Vector2(0.5f, 0.5f);
            frame.pivot = new Vector2(0.5f, 0.5f);
            frame.anchoredPosition = (min + max) * 0.5f;
            frame.sizeDelta = (max - min) + Vector2.one * padding * 2f;
            frame.SetAsLastSibling();
        }
    }
}
