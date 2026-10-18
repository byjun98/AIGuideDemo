using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace AIGuide
{
    public class GuideAvatarPresenter : MonoBehaviour, IGuidePresenter
    {
        [Header("대사창")]
        public Text nameText;
        public Text lineText;
        public GameObject thinkingIndicator;
        public float charsPerSecond = 28f;

        [Header("모델 배치")]
        public Transform avatarAnchor;

        GuideCharacterProfile _profile;
        GameObject _avatar;
        Animator _animator;
        SkinnedMeshRenderer[] _meshes = new SkinnedMeshRenderer[0];
        Coroutine _typing, _motion;

        public void Bind(GuideCharacterProfile profile)
        {
            if (_motion != null) StopCoroutine(_motion);
            if (_typing != null) StopCoroutine(_typing);
            _motion = _typing = null;
            _profile = profile;
            if (_avatar != null) Destroy(_avatar);
            _avatar = null;
            _animator = null;
            _meshes = new SkinnedMeshRenderer[0];
            if (profile == null) { Clear(); return; }
            if (nameText != null) { nameText.text = profile.displayName; nameText.color = profile.nameColor; }
            if (profile.avatarPrefab != null && avatarAnchor != null)
            {
                _avatar = Instantiate(profile.avatarPrefab, avatarAnchor);
                _avatar.transform.localPosition = profile.avatarPosition;
                _avatar.transform.localRotation = Quaternion.Euler(profile.avatarEuler);
                _avatar.transform.localScale = Vector3.one * profile.avatarScale;
                _animator = _avatar.GetComponentInChildren<Animator>();
                _meshes = _avatar.GetComponentsInChildren<SkinnedMeshRenderer>();
            }
            Clear();
        }

        public void ShowThinking(bool on)
        {
            if (thinkingIndicator != null) thinkingIndicator.SetActive(on);
        }

        public void Say(string line, string emotion, string motion)
        {
            ShowThinking(false);
            if (_typing != null) StopCoroutine(_typing);
            _typing = StartCoroutine(TypeLine(line ?? ""));
            ApplyEmotion(emotion);
            PlayMotion(motion);
        }

        public void Clear()
        {
            if (_typing != null) StopCoroutine(_typing);
            if (lineText != null) lineText.text = "";
            ShowThinking(false);
        }

        IEnumerator TypeLine(string line)
        {
            if (lineText == null) yield break;
            lineText.text = "";
            float t = 0;
            while (lineText.text.Length < line.Length)
            {
                t += Time.unscaledDeltaTime * charsPerSecond;
                lineText.text = line.Substring(0, Mathf.Min(line.Length, Mathf.FloorToInt(t)));
                yield return null;
            }
        }

        void ApplyEmotion(string tag)
        {
            foreach (var m in _meshes)
            {
                if (m == null || m.sharedMesh == null) continue;
                for (int i = 0; i < m.sharedMesh.blendShapeCount; i++) m.SetBlendShapeWeight(i, 0f);
            }
            var e = _profile != null ? _profile.FindEmotion(tag) : null;
            if (e == null || e.blendShapeKeywords == null) return;
            foreach (var m in _meshes)
            {
                if (m == null || m.sharedMesh == null) continue;
                for (int i = 0; i < m.sharedMesh.blendShapeCount; i++)
                {
                    string n = m.sharedMesh.GetBlendShapeName(i).ToLowerInvariant();
                    foreach (var k in e.blendShapeKeywords)
                        if (!string.IsNullOrEmpty(k) && n.Contains(k.ToLowerInvariant())) { m.SetBlendShapeWeight(i, e.weight); break; }
                }
            }
        }

        void PlayMotion(string tag)
        {
            var mb = _profile != null ? _profile.FindMotion(tag) : null;
            if (_animator != null && mb != null && !string.IsNullOrEmpty(mb.animatorTrigger) && HasParam(_animator, mb.animatorTrigger))
            {
                _animator.SetTrigger(mb.animatorTrigger);
                return;
            }
            if (_avatar == null || tag == "idle") return;
            if (_motion != null) StopCoroutine(_motion);
            _motion = StartCoroutine(Bob(tag == "nod" || tag == "salute" ? 0.025f : 0.012f));
        }

        IEnumerator Bob(float amount)
        {
            var tr = _avatar.transform;
            Vector3 basePos = _profile.avatarPosition;
            for (float t = 0; t < 0.45f; t += Time.unscaledDeltaTime)
            {
                tr.localPosition = basePos + Vector3.down * Mathf.Sin(t / 0.45f * Mathf.PI) * amount;
                yield return null;
            }
            tr.localPosition = basePos;
        }

        static bool HasParam(Animator a, string name)
        {
            foreach (var p in a.parameters) if (p.name == name) return true;
            return false;
        }
    }
}
