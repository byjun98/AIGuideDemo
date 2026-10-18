using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace AIGuide
{
    public class GuideUiTheme : MonoBehaviour
    {
        public Image background;
        public Image backgroundDim;
        [Tooltip("강조 테두리의 외곽선 이미지와, 모양이 없을 때 쓰는 직선 테두리")]
        public Image highlight;
        public GameObject highlightBars;
        [Tooltip("패널 모양과 패널 색을 받는 이미지")]
        public List<Image> panels = new List<Image>();
        [Tooltip("버튼 모양과 버튼 색을 받는 이미지(시스템 버튼, 제어 버튼)")]
        public List<Image> buttons = new List<Image>();
        [Tooltip("버튼 모양만 받고 원래 색을 유지하는 이미지(미끼 버튼, 뒤로 버튼 등)")]
        public List<Image> shapeOnly = new List<Image>();
        [Tooltip("버튼 모양과 강조색을 받는 이미지(보내기, 단계 행동 버튼)")]
        public List<Image> accents = new List<Image>();

        public void Apply(GuideCharacterProfile p)
        {
            if (p == null) return;
            if (background != null)
            {
                background.sprite = p.background;
                background.enabled = p.background != null;
                if (p.background != null && background.TryGetComponent<AspectRatioFitter>(out var fit))
                    fit.aspectRatio = p.background.rect.width / p.background.rect.height;
            }
            if (backgroundDim != null) backgroundDim.color = new Color(0f, 0f, 0f, p.background != null ? p.backgroundDim : 0f);
            if (highlight != null)
            {
                bool shaped = p.highlightShape != null;
                Shape(highlight, p.highlightShape, p.highlightScale, shaped ? new Color(1f, 0.85f, 0.2f, 1f) : new Color(1f, 1f, 1f, 0f));
                if (highlightBars != null) highlightBars.SetActive(!shaped);
            }
            foreach (var img in panels) Shape(img, p.panelShape, p.shapeScale, p.panelColor);
            foreach (var img in buttons) Shape(img, p.buttonShape, p.shapeScale, p.buttonColor);
            foreach (var img in shapeOnly) Shape(img, p.buttonShape, p.shapeScale, null);
            foreach (var img in accents) Shape(img, p.buttonShape, p.shapeScale, p.accentColor);
        }

        static void Shape(Image img, Sprite shape, float scale, Color? color)
        {
            if (img == null) return;
            img.sprite = shape;
            img.type = shape != null ? Image.Type.Sliced : Image.Type.Simple;
            img.pixelsPerUnitMultiplier = scale;
            if (color.HasValue) img.color = color.Value;
        }
    }
}
