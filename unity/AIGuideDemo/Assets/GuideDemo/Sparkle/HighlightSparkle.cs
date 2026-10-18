using System;
using System.Reflection;
using UnityEngine;

namespace AIGuide.Demo
{
    public class HighlightSparkle : MonoBehaviour
    {
        Component _pi;
        PropertyInfo _width, _height;
        RectTransform _rt;

        void Awake()
        {
            _rt = (RectTransform)transform;
            var type = Type.GetType("AssetKits.ParticleImage.ParticleImage, ParticleImage");
            if (type == null) { enabled = false; return; }
            _pi = GetComponent(type);
            _width = type.GetProperty("rectWidth");
            _height = type.GetProperty("rectHeight");
            if (_pi == null) enabled = false;
        }

        public static void AddTo(RectTransform frame, Texture2D texture)
        {
            var type = Type.GetType("AssetKits.ParticleImage.ParticleImage, ParticleImage");
            if (type == null) return;
            var rt = new GameObject("Sparkle", typeof(RectTransform)).GetComponent<RectTransform>();
            rt.SetParent(frame, false);
            rt.anchorMin = Vector2.zero; rt.anchorMax = Vector2.one;
            rt.offsetMin = rt.offsetMax = Vector2.zero;
            var pi = rt.gameObject.AddComponent(type);
            Set(pi, "texture", texture);
            Set(pi, "shape", "Rectangle");
            Set(pi, "space", "Local");
            Set(pi, "emitOnSurface", false);
            Set(pi, "emitterThickness", 6f);
            Set(pi, "loop", true);
            Set(pi, "rateOverTime", 26f);
            Set(pi, "lifetime", new ParticleSystem.MinMaxCurve(0.6f, 1.0f));
            Set(pi, "startSpeed", new ParticleSystem.MinMaxCurve(0.05f, 0.3f));
            var sizeType = type.GetProperty("startSize").PropertyType;
            Set(pi, "startSize", Activator.CreateInstance(sizeType, new object[] { 18f, false, true }));
            Set(pi, "startColor", new ParticleSystem.MinMaxGradient(new Color(1f, 0.85f, 0.3f), Color.white));
            Set(pi, "timeScale", "Unscaled");
            Set(pi, "PlayMode", "OnEnable");
            Set(pi, "raycastTarget", false);
            rt.gameObject.AddComponent<HighlightSparkle>();
        }

        static void Set(Component component, string name, object value)
        {
            var property = component.GetType().GetProperty(name);
            property.SetValue(component, property.PropertyType.IsEnum ? Enum.Parse(property.PropertyType, (string)value) : value);
        }

        void LateUpdate()
        {
            var r = _rt.rect;
            if (Mathf.Abs((float)_width.GetValue(_pi) - r.width) > 0.5f) _width.SetValue(_pi, r.width);
            if (Mathf.Abs((float)_height.GetValue(_pi) - r.height) > 0.5f) _height.SetValue(_pi, r.height);
        }
    }
}
