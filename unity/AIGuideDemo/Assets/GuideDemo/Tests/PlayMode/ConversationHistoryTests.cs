#if UNITY_EDITOR
using System;
using System.Collections;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace AIGuide.Tests
{
    public class ConversationHistoryTests
    {
        HttpListener listener;

        [TearDown] public void TearDown() => listener?.Close();

        async Task Respond(HttpListenerContext context, string line, int delay)
        {
            await Task.Delay(delay);
            string json = "{\"speak\":true,\"line\":\"" + line + "\",\"emotion\":\"neutral\",\"voice_tag\":\"calm_brief\",\"motion\":\"idle\",\"ui_target\":null,\"action\":\"none\",\"refusal\":null,\"risk\":\"safe\"}";
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            context.Response.ContentType = "application/json";
            context.Response.ContentLength64 = bytes.Length;
            await context.Response.OutputStream.WriteAsync(bytes, 0, bytes.Length);
            context.Response.Close();
        }

        [UnityTest]
        public IEnumerator LoweringStoryOrAffectionDiscardsPendingUnlockedReply()
        {
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode("Assets/GuideDemo/Scenes/AIGuideDemo_Nikke.unity", new LoadSceneParameters(LoadSceneMode.Single));
            yield return null;
            var director = UnityEngine.Object.FindFirstObjectByType<GuideDirector>();
            var panel = UnityEngine.Object.FindFirstObjectByType<Demo.DemoControlPanel>();
            var tcp = new TcpListener(IPAddress.Loopback, 0); tcp.Start();
            int port = ((IPEndPoint)tcp.LocalEndpoint).Port; tcp.Stop();
            listener = new HttpListener(); listener.Prefixes.Add("http://127.0.0.1:" + port + "/"); listener.Start();
            director.api.serverUrl = "http://127.0.0.1:" + port;
            int shown = 0;
            director.ResponsePresented += (response, trigger, state, line) => shown++;
            for (int mode = 0; mode < 2; mode++)
            {
                panel.SetStoryChapter(panel.storySlider.maxValue);
                panel.SetAffection(100);
                var server = Task.Run(async () => await Respond(await listener.GetContextAsync(), "future_or_affection_locked", 250));
                director.Ask("unlocked_question");
                yield return new WaitForSecondsRealtime(.05f);
                if (mode == 0) panel.SetStoryChapter(0); else panel.SetAffection(0);
                float end = Time.realtimeSinceStartup + 5;
                while (!server.IsCompleted && Time.realtimeSinceStartup < end) yield return null;
                yield return new WaitForSecondsRealtime(.1f);
                Assert.That(server.IsCompleted && !server.IsFaulted, Is.True);
                Assert.That(shown, Is.Zero, "A response generated for an older unlock state must be discarded");
                Assert.That(director.CurrentPhase, Is.EqualTo(GuideDirector.Phase.Idle));
            }
        }

        [UnityTest]
        public IEnumerator TypedAndSpokenHistoryExcludesStaleResponses()
        {
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode("Assets/GuideDemo/Scenes/AIGuideDemo_Nikke.unity", new LoadSceneParameters(LoadSceneMode.Single));
            yield return null;
            var director = UnityEngine.Object.FindFirstObjectByType<GuideDirector>();
            var panel = UnityEngine.Object.FindFirstObjectByType<Demo.DemoControlPanel>();
            var tcp = new TcpListener(IPAddress.Loopback, 0); tcp.Start();
            int port = ((IPEndPoint)tcp.LocalEndpoint).Port; tcp.Stop();
            listener = new HttpListener(); listener.Prefixes.Add("http://127.0.0.1:" + port + "/"); listener.Start();
            director.api.serverUrl = "http://127.0.0.1:" + port;
            var server = Task.Run(async () =>
            {
                var first = await listener.GetContextAsync();
                var firstResponse = Respond(first, "stale_first", 500);
                var second = await listener.GetContextAsync();
                await Respond(second, "current_second", 5);
                await firstResponse;
            });
            director.Ask("typed_question");
            yield return new WaitForSecondsRealtime(.05f);
            var transcribed = (Action<string, float>)typeof(GuideVoiceInput).GetField("Transcribed", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(director.voice);
            transcribed("spoken_question", 10);
            float end = Time.realtimeSinceStartup + 5;
            while (!server.IsCompleted && Time.realtimeSinceStartup < end) yield return null;
            yield return new WaitForSecondsRealtime(.15f);
            Assert.That(server.IsCompleted && !server.IsFaulted, Is.True);
            string text = string.Join("\n", panel.history.content.GetComponentsInChildren<Text>().Select(t => t.text));
            Assert.That(text, Does.Contain("typed_question").And.Contain("spoken_question").And.Contain("current_second"));
            Assert.That(text, Does.Not.Contain("stale_first"));
            panel.history.SetExplanationMode(false);
            panel.history.SetExplanationMode(true);
            for (int i = 0; i < 20; i++) panel.history.AddPlayer("bounded_" + i);
            yield return null;
            Assert.That(panel.history.content.childCount, Is.EqualTo(16));
        }
    }
}
#endif
