using System.Reflection;
using UnityEngine;

namespace AIGuide.Demo
{
    public class GuideStepBanner : MonoBehaviour
    {
        public DemoOutpostAdapter game;
        [Tooltip("Motion Titles Pack 프리팹 인스턴스(StyleManager가 붙은 오브젝트). 처음에는 꺼 둔다")]
        public GameObject title;
        [Tooltip("한국어 TMP 폰트 에셋(TMP_FontAsset)")]
        public ScriptableObject koreanFont;
        public string topLabel = "단계 완료";
        public float showSeconds = 2.5f;

        void Start()
        {
            if (game != null) game.StepCompleted += OnStep;
            if (title != null) title.SetActive(false);
        }

        void OnDestroy()
        {
            if (game != null) game.StepCompleted -= OnStep;
        }

        void OnStep(string stepId)
        {
            var step = game.pack != null ? game.pack.Step(stepId) : null;
            Show(topLabel, step != null && !string.IsNullOrEmpty(step.@short) ? step.@short : stepId);
        }

        public void Show(string top, string bottom)
        {
            if (title == null) return;
            foreach (var mb in title.GetComponentsInChildren<MonoBehaviour>(true))
            {
                var t = mb.GetType();
                if (t.Name != "TextItem") continue;
                string id = t.GetField("itemID")?.GetValue(mb) as string ?? "";
                t.GetField("text")?.SetValue(mb, id.StartsWith("Top") || id.StartsWith("Main") ? top : bottom);
                if (koreanFont != null) t.GetField("selectedFont")?.SetValue(mb, koreanFont);
                t.GetMethod("UpdateAll", BindingFlags.Public | BindingFlags.Instance)?.Invoke(mb, null);
            }
            if (_run != null) StopCoroutine(_run);
            _run = StartCoroutine(Run());
        }

        Coroutine _run;

        System.Collections.IEnumerator Run()
        {
            MonoBehaviour style = null;
            foreach (var mb in title.GetComponents<MonoBehaviour>())
                if (mb.GetType().Name == "StyleManager") style = mb;
            if (style == null) { title.SetActive(true); yield break; }
            var t = style.GetType();
            t.GetField("playOnEnable")?.SetValue(style, false);
            t.GetField("playOutAnimation")?.SetValue(style, false);
            title.SetActive(false);
            t.GetMethod("Play")?.Invoke(style, null);
            yield return new WaitForSecondsRealtime(showSeconds);
            t.GetMethod("PlayOut")?.Invoke(style, null);
            yield return new WaitForSecondsRealtime(1.2f);
            title.SetActive(false);
            _run = null;
        }
    }
}
