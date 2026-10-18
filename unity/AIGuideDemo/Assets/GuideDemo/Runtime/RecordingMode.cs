using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace AIGuide.Demo
{
    public class RecordingMode : MonoBehaviour
    {
        public int idleHintSeconds = 45;
        public int minSecondsBetweenLines = 60;
        public Color rippleColor = new Color(1f, 0.82f, 0.18f, 1f);

        const float RippleSeconds = 0.5f;
        const float RippleStart = 24f, RippleEnd = 120f;

        RectTransform _root, _cursor, _press;
        Image _pressImage;
        Sprite _ring;
        bool _policyApplied;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            bool byArg = System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-recording") >= 0;
            bool byEnv = System.Environment.GetEnvironmentVariable("AIGD_RECORDING") == "1";
            if (byArg || byEnv) Enable();
        }

        public static RecordingMode Enable()
        {
            var existing = FindAnyObjectByType<RecordingMode>();
            if (existing != null) return existing;
            var go = new GameObject("RecordingMode");
            DontDestroyOnLoad(go);
            return go.AddComponent<RecordingMode>();
        }

        void Awake()
        {
            var canvas = gameObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 32000;
            var scaler = gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            _root = (RectTransform)transform;

            _ring = MakeSprite(MakeRing(128), new Vector2(0.5f, 0.5f));
            _press = NewImage("Press", MakeSprite(MakeDisc(64), new Vector2(0.5f, 0.5f)), new Vector2(38, 38));
            _pressImage = _press.GetComponent<Image>();
            _pressImage.color = new Color(rippleColor.r, rippleColor.g, rippleColor.b, 0.45f);
            _press.gameObject.SetActive(false);
            _cursor = NewImage("Cursor", MakeSprite(MakeArrow(64), new Vector2(4f / 64f, 1f - 4f / 64f)), new Vector2(48, 48));
        }

        void Update()
        {
            if (!_policyApplied) ApplyPolicy();
            Cursor.visible = false;
            var mouse = Mouse.current;
            if (mouse == null) return;
            Vector2 pos = mouse.position.ReadValue();
            _cursor.position = pos;
            _cursor.SetAsLastSibling();

            bool held = mouse.leftButton.isPressed;
            _cursor.localScale = Vector3.one * (held ? 0.85f : 1f);
            _press.gameObject.SetActive(held);
            if (held) _press.position = pos;
            if (mouse.leftButton.wasPressedThisFrame) StartCoroutine(Ripple(pos));
        }

        void OnDestroy() => Cursor.visible = true;

        void ApplyPolicy()
        {
            var director = FindAnyObjectByType<GuideDirector>();
            if (director == null) return;
            director.policy.idleHintSeconds = Mathf.Max(director.policy.idleHintSeconds, idleHintSeconds);
            director.policy.minSecondsBetweenLines = Mathf.Max(director.policy.minSecondsBetweenLines, minSecondsBetweenLines);
            _policyApplied = true;
        }

        System.Collections.IEnumerator Ripple(Vector2 pos)
        {
            var ring = NewImage("Ripple", _ring, Vector2.one * RippleStart);
            ring.position = pos;
            ring.SetSiblingIndex(0);
            var image = ring.GetComponent<Image>();
            for (float t = 0f; t < RippleSeconds; t += Time.unscaledDeltaTime)
            {
                float k = t / RippleSeconds;
                float eased = 1f - (1f - k) * (1f - k);
                ring.sizeDelta = Vector2.one * Mathf.Lerp(RippleStart, RippleEnd, eased);
                image.color = new Color(rippleColor.r, rippleColor.g, rippleColor.b, 1f - k);
                yield return null;
            }
            Destroy(ring.gameObject);
        }

        RectTransform NewImage(string name, Sprite sprite, Vector2 size)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            var rt = (RectTransform)go.transform;
            rt.SetParent(_root, false);
            rt.sizeDelta = size;
            var image = go.GetComponent<Image>();
            image.sprite = sprite;
            image.raycastTarget = false;
            return rt;
        }

        static Sprite MakeSprite(Texture2D tex, Vector2 pivot) =>
            Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), pivot, 100f);

        static Texture2D NewTexture(int size)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            tex.wrapMode = TextureWrapMode.Clamp;
            tex.filterMode = FilterMode.Bilinear;
            return tex;
        }

        static Texture2D MakeRing(int size)
        {
            var tex = NewTexture(size);
            float r = size * 0.5f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(r, r)) / r;
                    float a = Mathf.Clamp01(1f - Mathf.Abs(d - 0.86f) / 0.1f);
                    tex.SetPixel(x, y, new Color(1, 1, 1, a));
                }
            tex.Apply();
            return tex;
        }

        static Texture2D MakeDisc(int size)
        {
            var tex = NewTexture(size);
            float r = size * 0.5f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(r, r)) / r;
                    tex.SetPixel(x, y, new Color(1, 1, 1, Mathf.Clamp01((1f - d) / 0.15f)));
                }
            tex.Apply();
            return tex;
        }

        static readonly Vector2[] Arrow =
        {
            new Vector2(4, 4), new Vector2(4, 50), new Vector2(15, 39), new Vector2(23, 57),
            new Vector2(31, 53), new Vector2(23, 36), new Vector2(39, 36),
        };

        static Texture2D MakeArrow(int size)
        {
            var tex = NewTexture(size);
            const float outline = 3f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x + 0.5f, size - y - 0.5f);
                    bool inside = Inside(p);
                    float edge = EdgeDistance(p);
                    Color c = Color.clear;
                    if (inside) c = edge < outline ? new Color(0.08f, 0.08f, 0.1f, 1f) : Color.white;
                    else if (edge < 1.2f) c = new Color(0.08f, 0.08f, 0.1f, 1f - edge / 1.2f);
                    tex.SetPixel(x, y, c);
                }
            tex.Apply();
            return tex;
        }

        static bool Inside(Vector2 p)
        {
            bool inside = false;
            for (int i = 0, j = Arrow.Length - 1; i < Arrow.Length; j = i++)
            {
                Vector2 a = Arrow[i], b = Arrow[j];
                if ((a.y > p.y) != (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x) inside = !inside;
            }
            return inside;
        }

        static float EdgeDistance(Vector2 p)
        {
            float best = float.MaxValue;
            for (int i = 0, j = Arrow.Length - 1; i < Arrow.Length; j = i++)
            {
                Vector2 a = Arrow[j], b = Arrow[i], ab = b - a;
                float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
                best = Mathf.Min(best, Vector2.Distance(p, a + ab * t));
            }
            return best;
        }
    }
}
