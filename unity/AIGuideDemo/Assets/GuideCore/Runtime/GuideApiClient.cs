using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace AIGuide
{
    public class GuideApiClient : MonoBehaviour
    {
        public string serverUrl = "http://127.0.0.1:8000";
        public int timeoutSeconds = 35;

        public IEnumerator Generate(GuideRequest req, Action<GuideResponse, float, string> done)
        {
            string body = JsonUtility.ToJson(req);
            using (var www = new UnityWebRequest(serverUrl.TrimEnd('/') + "/guide/generate", "POST"))
            {
                www.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body));
                www.downloadHandler = new DownloadHandlerBuffer();
                www.SetRequestHeader("Content-Type", "application/json");
                www.timeout = timeoutSeconds;
                float t0 = Time.realtimeSinceStartup;
                yield return www.SendWebRequest();
                float sec = Time.realtimeSinceStartup - t0;
                if (www.result != UnityWebRequest.Result.Success)
                {
                    done(null, sec, www.error);
                    yield break;
                }
                GuideResponse resp = null;
                string err = null;
                try { resp = JsonUtility.FromJson<GuideResponse>(www.downloadHandler.text); }
                catch (Exception e) { err = e.Message; }
                done(resp, sec, err);
            }
        }
    }
}
