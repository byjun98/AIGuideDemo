#if UNITY_EDITOR
using System.Collections;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEditor.SceneManagement;

namespace AIGuide.Tests
{
    public class DemoSceneSmokeTests
    {
        IEnumerator Smoke(string scenePath)
        {
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(scenePath, new LoadSceneParameters(LoadSceneMode.Single));
            yield return null;
            var director = Object.FindFirstObjectByType<GuideDirector>();
            Assert.That(director, Is.Not.Null);
            Assert.That(director.enabled, Is.True);
            Assert.That(director.logger.logPath, Is.Empty);
            var panel = Object.FindFirstObjectByType<Demo.DemoControlPanel>();
            Assert.That(panel.history, Is.Not.Null);
            Assert.That(panel.suggestionButtons.Length, Is.EqualTo(3));
            panel.crossGame = true;
            for (int i = 0; i < panel.characters.Count; i++)
            {
                panel.SwapCharacter(i);
                var character = panel.characters[i];
                Assert.That(panel.storySlider.maxValue, Is.EqualTo(character.storyChapters.Max(c => c.index)));
                panel.SetStoryChapter(0);
                Assert.That(director.CaptureState().story_chapter, Is.Zero);
                panel.SetStoryChapter(panel.storySlider.maxValue);
                Assert.That(director.CaptureState().story_chapter, Is.EqualTo((int)panel.storySlider.maxValue));
                panel.SetAffection(0); panel.SetAffection(100);
                director.Ask("지금 뭐 하면 돼?");
                director.SwapCharacter(character);
                yield return null;
            }
            director.enabled = false;
            Assert.That(director.CurrentPhase, Is.EqualTo(GuideDirector.Phase.Idle));
            director.enabled = true;
            director.api.serverUrl = "http://127.0.0.1:9";
            director.api.timeoutSeconds = 1;
            director.Ask("지금 뭐 하면 돼?");
            float deadline = Time.realtimeSinceStartup + 4;
            while (director.CurrentPhase == GuideDirector.Phase.Thinking && Time.realtimeSinceStartup < deadline) yield return null;
            Assert.That(director.CurrentPhase, Is.Not.EqualTo(GuideDirector.Phase.Thinking));
            Assert.That(director.enabled, Is.True);
        }

        [UnityTest] public IEnumerator NikkeSceneSwapsCharactersAndRecoversFromOfflineServer() => Smoke("Assets/GuideDemo/Scenes/AIGuideDemo_Nikke.unity");
        [UnityTest] public IEnumerator BlueArchiveSceneSwapsCharactersAndRecoversFromOfflineServer() => Smoke("Assets/GuideDemo/Scenes/AIGuideDemo_BlueArchive.unity");
        [UnityTest] public IEnumerator TrickcalSceneSwapsCharactersAndRecoversFromOfflineServer() => Smoke("Assets/GuideDemo/Scenes/AIGuideDemo_Trickcal.unity");

        [UnityTest]
        public IEnumerator RapiSceneRecoversFromOfflineServer()
        {
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode("Assets/RapiRAGDemo/Scenes/RapiLobbyDemo.unity", new LoadSceneParameters(LoadSceneMode.Single));
            yield return null;
            var type = System.Type.GetType("RapiRAGDemo.RapiDialogueApiClient, Assembly-CSharp");
            var client = Object.FindFirstObjectByType(type);
            Assert.That(client, Is.Not.Null);
            type.GetField("endpoint").SetValue(client, "http://127.0.0.1:9/dialogue/generate");
            type.GetField("requestTimeoutSeconds").SetValue(client, 1);
            type.GetMethod("RequestGiftDialogue", System.Type.EmptyTypes).Invoke(client, null);
            var busy = type.GetField("isRequesting", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            float end = Time.realtimeSinceStartup + 4;
            while ((bool)busy.GetValue(client) && Time.realtimeSinceStartup < end) yield return null;
            Assert.That(busy.GetValue(client), Is.False);
            Assert.That(((UnityEngine.UI.Button)type.GetField("giftButton").GetValue(client)).interactable, Is.True);
        }
    }
}
#endif
