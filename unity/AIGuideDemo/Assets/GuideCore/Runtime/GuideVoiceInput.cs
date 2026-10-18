using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.InputSystem;

namespace AIGuide
{
    public class GuideVoiceInput : MonoBehaviour
    {
        public string whisperUrl = "http://127.0.0.1:8090/inference";
        public Key pushToTalkKey = Key.V;
        public int maxSeconds = 12;
        public int sampleRate = 16000;
        public int requestTimeoutSeconds = 35;

        public event Action<string, float> Transcribed;
        public event Action<bool> RecordingChanged;

        AudioClip _clip;
        string _device;
        public bool IsRecording { get; private set; }

        void OnDisable()
        {
            if (IsRecording) Microphone.End(_device);
            IsRecording = false;
            RecordingChanged?.Invoke(false);
            StopAllCoroutines();
            if (_clip != null) Destroy(_clip);
            _clip = null;
        }

        void Update()
        {
            var kb = Keyboard.current;
            if (kb == null) return;
            if (UnityEngine.EventSystems.EventSystem.current != null &&
                UnityEngine.EventSystems.EventSystem.current.currentSelectedGameObject != null &&
                UnityEngine.EventSystems.EventSystem.current.currentSelectedGameObject.GetComponent<UnityEngine.UI.InputField>() != null) return;
            if (kb[pushToTalkKey].wasPressedThisFrame) Begin();
            if (kb[pushToTalkKey].wasReleasedThisFrame) End();
        }

        public void Begin()
        {
            if (IsRecording || Microphone.devices.Length == 0) return;
            _device = Microphone.devices[0];
            _clip = Microphone.Start(_device, false, maxSeconds, sampleRate);
            IsRecording = true;
            RecordingChanged?.Invoke(true);
        }

        public void End()
        {
            if (!IsRecording) return;
            int pos = Microphone.GetPosition(_device);
            if (pos <= 0 && _clip != null) pos = _clip.samples;
            Microphone.End(_device);
            IsRecording = false;
            RecordingChanged?.Invoke(false);
            if (pos <= sampleRate / 4) return;
            var data = new float[pos * _clip.channels];
            _clip.GetData(data, 0);
            StartCoroutine(Send(ToWav(data, _clip.channels, sampleRate)));
        }

        IEnumerator Send(byte[] wav)
        {
            var form = new WWWForm();
            form.AddBinaryData("file", wav, "input.wav", "audio/wav");
            form.AddField("response_format", "json");
            form.AddField("language", "ko");
            form.AddField("temperature", "0.0");
            float t0 = Time.realtimeSinceStartup;
            using (var www = UnityWebRequest.Post(whisperUrl, form))
            {
                www.timeout = Mathf.Max(1, requestTimeoutSeconds);
                yield return www.SendWebRequest();
                float ms = (Time.realtimeSinceStartup - t0) * 1000f;
                if (www.result != UnityWebRequest.Result.Success) { Debug.LogWarning("[GuideVoice] " + www.error); yield break; }
                var r = JsonUtility.FromJson<WhisperResult>(www.downloadHandler.text);
                string text = (r?.text ?? "").Trim();
                if (text.Length > 0) Transcribed?.Invoke(text, ms);
            }
        }

        [Serializable] class WhisperResult { public string text; }

        static byte[] ToWav(float[] samples, int channels, int rate)
        {
            using (var ms = new MemoryStream())
            using (var w = new BinaryWriter(ms))
            {
                int byteCount = samples.Length * 2;
                w.Write(new[] { 'R', 'I', 'F', 'F' }); w.Write(36 + byteCount);
                w.Write(new[] { 'W', 'A', 'V', 'E' }); w.Write(new[] { 'f', 'm', 't', ' ' });
                w.Write(16); w.Write((short)1); w.Write((short)channels); w.Write(rate);
                w.Write(rate * channels * 2); w.Write((short)(channels * 2)); w.Write((short)16);
                w.Write(new[] { 'd', 'a', 't', 'a' }); w.Write(byteCount);
                foreach (var s in samples) w.Write((short)(Mathf.Clamp(s, -1f, 1f) * short.MaxValue));
                return ms.ToArray();
            }
        }
    }
}
