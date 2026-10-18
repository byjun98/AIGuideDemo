using System.Collections.Generic;
using UnityEngine;

namespace AIGuide
{
    [DisallowMultipleComponent]
    public class GuideUiTarget : MonoBehaviour
    {
        public string targetId;
        static readonly Dictionary<string, GuideUiTarget> Registry = new Dictionary<string, GuideUiTarget>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetRegistry() => Registry.Clear();

        void OnEnable() { if (!string.IsNullOrEmpty(targetId)) Registry[targetId] = this; }
        void OnDisable() { if (Registry.TryGetValue(targetId ?? "", out var t) && t == this) Registry.Remove(targetId); }

        public static bool TryGet(string id, out GuideUiTarget t)
        {
            t = null;
            return !string.IsNullOrEmpty(id) && Registry.TryGetValue(id, out t) && t != null && t.isActiveAndEnabled;
        }

        public static List<string> ActiveIds()
        {
            var list = new List<string>();
            foreach (var kv in Registry) if (kv.Value != null && kv.Value.isActiveAndEnabled) list.Add(kv.Key);
            list.Sort(System.StringComparer.Ordinal);
            return list;
        }

        public RectTransform Rect => transform as RectTransform;
    }
}
