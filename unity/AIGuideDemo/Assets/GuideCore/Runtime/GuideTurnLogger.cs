using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace AIGuide
{
    public class GuideTurnLogger : MonoBehaviour
    {
        [Tooltip("비워 두면 Application.persistentDataPath/guide_turns.jsonl")]
        public string logPath = "";
        string PathOrDefault => string.IsNullOrEmpty(logPath) ? Path.Combine(Application.persistentDataPath, "guide_turns.jsonl") : logPath;
        float _fpsAccum; int _fpsFrames;

        [Serializable]
        public class Turn
        {
            public string time;
            public string session;
            public string character;
            public string model;
            public string trigger;
            public string player_input;
            public string step;
            public string policy_silence;
            public float stt_ms;
            public float request_ms;
            public int server_llm_ms;
            public bool speak;
            public string line;
            public string ui_target;
            public string exec_stage;
            public string exec_reason;
            public bool cover_shown;
            public float fps_during_wait;
            public string risk;
            public string error;
        }

        public static readonly string Session = DateTime.Now.ToString("yyyyMMdd_HHmmss");

        public void BeginWait() { _fpsAccum = 0; _fpsFrames = 0; }
        public void TickWait() { _fpsAccum += Time.unscaledDeltaTime; _fpsFrames++; }
        public float WaitFps() => _fpsAccum > 0 ? _fpsFrames / _fpsAccum : 0f;

        public void Write(Turn t)
        {
            t.time = DateTime.Now.ToString("o");
            t.session = Session;
            try
            {
                string p = PathOrDefault;
                Directory.CreateDirectory(Path.GetDirectoryName(p));
                File.AppendAllText(p, JsonUtility.ToJson(t) + "\n", new UTF8Encoding(false));
            }
            catch (Exception e) { Debug.LogWarning("[GuideTurnLogger] " + e.Message); }
        }
    }
}
