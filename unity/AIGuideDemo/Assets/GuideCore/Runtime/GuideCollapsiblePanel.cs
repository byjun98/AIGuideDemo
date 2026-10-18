using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace AIGuide
{
    public class GuideCollapsiblePanel : MonoBehaviour
    {
        public enum Side { Left, Right, Top, Bottom }

        [Tooltip("접을 때 패널이 들어가는 화면 가장자리")]
        public Side side = Side.Left;
        public Button toggle;
        [Tooltip("위쪽을 가리키는 화살표 이미지. 상태에 따라 회전한다")]
        public RectTransform arrow;
        public float duration = 0.25f;
        public bool startCollapsed;

        public bool Collapsed { get; private set; }
        public event Action<bool> Changed;

        RectTransform _rt;
        Vector2 _openPos;
        Coroutine _anim;

        void Awake()
        {
            _rt = (RectTransform)transform;
            _openPos = _rt.anchoredPosition;
            if (toggle != null) toggle.onClick.AddListener(Toggle);
        }

        void Start()
        {
            if (startCollapsed) Set(true, true);
            else UpdateArrow();
        }

        public void Toggle() => Set(!Collapsed, false);

        public void Set(bool collapsed, bool instant)
        {
            Collapsed = collapsed;
            var target = collapsed ? _openPos + HiddenOffset() : _openPos;
            if (_anim != null) StopCoroutine(_anim);
            if (instant || !isActiveAndEnabled) _rt.anchoredPosition = target;
            else _anim = StartCoroutine(Slide(target));
            UpdateArrow();
            Changed?.Invoke(collapsed);
        }

        Vector2 HiddenOffset()
        {
            var parent = _rt.parent as RectTransform;
            var size = parent != null ? parent.rect.size : new Vector2(Screen.width, Screen.height);
            switch (side)
            {
                case Side.Left: return new Vector2(-_rt.anchorMax.x * size.x, 0f);
                case Side.Right: return new Vector2((1f - _rt.anchorMin.x) * size.x, 0f);
                case Side.Top: return new Vector2(0f, (1f - _rt.anchorMin.y) * size.y);
                default: return new Vector2(0f, -_rt.anchorMax.y * size.y);
            }
        }

        IEnumerator Slide(Vector2 target)
        {
            var from = _rt.anchoredPosition;
            for (float t = 0f; t < duration; t += Time.unscaledDeltaTime)
            {
                _rt.anchoredPosition = Vector2.LerpUnclamped(from, target, Mathf.SmoothStep(0f, 1f, t / duration));
                yield return null;
            }
            _rt.anchoredPosition = target;
            _anim = null;
        }

        void UpdateArrow()
        {
            if (arrow == null) return;
            float toEdge = side == Side.Left ? 90f : side == Side.Right ? -90f : side == Side.Top ? 0f : 180f;
            arrow.localEulerAngles = new Vector3(0f, 0f, Collapsed ? toEdge + 180f : toEdge);
        }
    }
}
