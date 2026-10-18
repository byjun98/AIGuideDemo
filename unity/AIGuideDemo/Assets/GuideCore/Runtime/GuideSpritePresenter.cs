using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace AIGuide
{
    public class GuideSpritePresenter : MonoBehaviour, IGuidePresenter
    {
        [Header("대사창")]
        public Text nameText;
        public Text lineText;
        public GameObject thinkingIndicator;
        public float charsPerSecond = 28f;

        [Header("일러스트 레이어")]
        public RectTransform portraitRoot;
        public Image bodyImage;
        public Image faceImage;
        public Image mouthImage;
        public float blinkInterval = 4f;

        GuideCharacterProfile _p;
        string _emotion = "neutral", _pose = "idle";
        Coroutine _typing, _motion;
        float _nextBlink;
        bool _talking;
        Vector2 _basePos;

        public void Bind(GuideCharacterProfile profile)
        {
            if (_motion != null) StopCoroutine(_motion);
            if (_typing != null) StopCoroutine(_typing);
            _motion = _typing = null;
            _p = profile;
            if (profile == null) { Clear(); return; }
            if (nameText != null) { nameText.text = profile.displayName; nameText.color = profile.nameColor; }
            if (portraitRoot != null)
            {
                _basePos = profile.portraitAnchoredPos;
                portraitRoot.anchoredPosition = _basePos;
                portraitRoot.localScale = Vector3.one * profile.portraitScale;
            }
            _emotion = "neutral"; _pose = "idle";
            Apply();
            Clear();
        }

        public void ShowThinking(bool on) { if (thinkingIndicator != null) thinkingIndicator.SetActive(on); }

        public void Say(string line, string emotion, string motion)
        {
            if (_p == null) return;
            ShowThinking(false);
            _emotion = string.IsNullOrEmpty(emotion) ? "neutral" : emotion;
            if (!string.IsNullOrEmpty(motion) && (_p.FindSprite(_p.poseSprites, motion) != null || _p.FindSprite(_p.fullSprites, _emotion + "@" + motion) != null))
                _pose = motion;
            else if (motion == "idle") _pose = "idle";
            Apply();
            if (_typing != null) StopCoroutine(_typing);
            _typing = StartCoroutine(TypeLine(line ?? ""));
            if (motion == "nod" || motion == "salute" || motion == "soft_smile")
            {
                if (_motion != null) StopCoroutine(_motion);
                _motion = StartCoroutine(Bob(motion == "nod" ? 14f : 8f));
            }
        }

        public void Clear()
        {
            if (_typing != null) StopCoroutine(_typing);
            if (lineText != null) lineText.text = "";
            _talking = false;
            ShowThinking(false);
        }

        void Apply()
        {
            if (_p == null) return;
            var full = _p.FindSprite(_p.fullSprites, _emotion + "@" + _pose) ?? _p.FindSprite(_p.fullSprites, _emotion);
            if (full != null)
            {
                Set(bodyImage, full); Set(faceImage, null);
                return;
            }
            Set(bodyImage, _p.FindSprite(_p.poseSprites, _pose) ?? _p.FindSprite(_p.poseSprites, "idle"));
            Set(faceImage, _p.FindSprite(_p.faceSprites, _emotion) ?? _p.FindSprite(_p.faceSprites, "neutral"));
        }

        static void Set(Image img, Sprite s)
        {
            if (img == null) return;
            img.sprite = s;
            img.enabled = s != null;
        }

        void Update()
        {
            if (_p == null || faceImage == null || _p.blinkFace == null || _talking) return;
            if (Time.unscaledTime > _nextBlink)
            {
                _nextBlink = Time.unscaledTime + blinkInterval + Random.Range(-1f, 1.5f);
                StartCoroutine(Blink());
            }
        }

        IEnumerator Blink()
        {
            if (!faceImage.enabled) yield break;
            var prev = faceImage.sprite;
            faceImage.sprite = _p.blinkFace;
            yield return new WaitForSecondsRealtime(0.12f);
            if (faceImage.sprite == _p.blinkFace) faceImage.sprite = prev;
        }

        IEnumerator TypeLine(string line)
        {
            if (lineText == null) yield break;
            _talking = true;
            lineText.text = "";
            float t = 0;
            while (lineText.text.Length < line.Length)
            {
                t += Time.unscaledDeltaTime * charsPerSecond;
                int n = Mathf.Min(line.Length, Mathf.FloorToInt(t));
                lineText.text = line.Substring(0, n);
                if (mouthImage != null && _p.talkMouthOpen != null) { mouthImage.sprite = _p.talkMouthOpen; mouthImage.enabled = (n / 2) % 2 == 0; }
                yield return null;
            }
            if (mouthImage != null) mouthImage.enabled = false;
            _talking = false;
        }

        IEnumerator Bob(float px)
        {
            if (portraitRoot == null) yield break;
            for (float t = 0; t < 0.4f; t += Time.unscaledDeltaTime)
            {
                portraitRoot.anchoredPosition = _basePos + Vector2.down * Mathf.Sin(t / 0.4f * Mathf.PI) * px;
                yield return null;
            }
            portraitRoot.anchoredPosition = _basePos;
        }
    }
}
