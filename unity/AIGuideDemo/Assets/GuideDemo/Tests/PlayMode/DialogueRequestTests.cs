using System;
using System.Collections;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace AIGuide.Tests
{
    public class DialogueRequestTests
    {
        GameObject root;
        Component client;
        Button button;
        HttpListener listener;
        Type ClientType => Type.GetType("RapiRAGDemo.RapiDialogueApiClient, Assembly-CSharp", true);
        static readonly BindingFlags PrivateInstance = BindingFlags.NonPublic | BindingFlags.Instance;

        [SetUp]
        public void SetUp()
        {
            root = new GameObject("RequestTest");
            client = root.AddComponent(ClientType);
            button = new GameObject("Button", typeof(RectTransform), typeof(Button)).GetComponent<Button>();
            button.transform.SetParent(root.transform);
            ClientType.GetField("giftButton").SetValue(client, button);
            ClientType.GetField("requestTimeoutSeconds").SetValue(client, 1);
        }

        [TearDown]
        public void TearDown()
        {
            listener?.Close();
            UnityEngine.Object.DestroyImmediate(root);
        }

        bool IsRequesting => (bool)ClientType.GetField("isRequesting", PrivateInstance).GetValue(client);

        int FreePort()
        {
            var tcp = new TcpListener(IPAddress.Loopback, 0);
            tcp.Start();
            int port = ((IPEndPoint)tcp.LocalEndpoint).Port;
            tcp.Stop();
            return port;
        }

        void StartRequest(int port)
        {
            ClientType.GetField("endpoint").SetValue(client, "http://127.0.0.1:" + port + "/dialogue/generate");
            ClientType.GetMethod("RequestDialogue", PrivateInstance).Invoke(client, new object[] { "Test" });
        }

        IEnumerator WaitForRecovery()
        {
            float end = Time.realtimeSinceStartup + 5;
            while (IsRequesting && Time.realtimeSinceStartup < end) yield return null;
            Assert.That(IsRequesting, Is.False, "Request must release its busy state");
            Assert.That(button.interactable, Is.True, "Request must re-enable the button");
        }

        [UnityTest]
        public IEnumerator StoppedServerReleasesButtons()
        {
            int port = FreePort();
            StartRequest(port);
            yield return WaitForRecovery();
            StartRequest(port);
            yield return WaitForRecovery();
        }

        [Test]
        public void BusyGiftRequestDoesNotChangePayload()
        {
            ClientType.GetField("isRequesting", PrivateInstance).SetValue(client, true);
            ClientType.GetField("currentQuery", PrivateInstance).SetValue(client, "sentinel");
            ClientType.GetMethod("RequestGiftDialogue", Type.EmptyTypes).Invoke(client, null);
            Assert.That(ClientType.GetField("currentQuery", PrivateInstance).GetValue(client), Is.EqualTo("sentinel"));
        }

        [Test]
        public void BusyGiftConfirmationDoesNotChangeBondRank()
        {
            ClientType.GetMethod("OpenGiftModal").Invoke(client, null);
            int rank = (int)ClientType.GetField("bondRank").GetValue(client);
            ClientType.GetField("isRequesting", PrivateInstance).SetValue(client, true);
            ClientType.GetMethod("ConfirmSelectedGift").Invoke(client, null);
            Assert.That(ClientType.GetField("bondRank").GetValue(client), Is.EqualTo(rank));
        }

        [Test]
        public void BusyAdviceRequestDoesNotChangePayload()
        {
            ClientType.GetField("choiceButtons").SetValue(client, new[] { button });
            ClientType.GetMethod("OpenAdviceChoices").Invoke(client, null);
            Assert.That(((System.Collections.IList)ClientType.GetField("currentChoices", PrivateInstance).GetValue(client)).Count, Is.GreaterThan(0));
            ClientType.GetField("isRequesting", PrivateInstance).SetValue(client, true);
            ClientType.GetField("currentQuery", PrivateInstance).SetValue(client, "sentinel");
            ClientType.GetMethod("RequestChoice").Invoke(client, new object[] { 0 });
            Assert.That(ClientType.GetField("currentQuery", PrivateInstance).GetValue(client), Is.EqualTo("sentinel"));
        }

        [UnityTest]
        public IEnumerator DelayedResponseTimesOutAndReleasesButtons()
        {
            int port = FreePort();
            listener = new HttpListener();
            listener.Prefixes.Add("http://127.0.0.1:" + port + "/");
            listener.Start();
            StartRequest(port);
            Assert.That(IsRequesting, Is.True);
            yield return WaitForRecovery();
        }

        [UnityTest]
        public IEnumerator DisableDuringRequestReleasesButtons()
        {
            int port = FreePort();
            listener = new HttpListener();
            listener.Prefixes.Add("http://127.0.0.1:" + port + "/");
            listener.Start();
            StartRequest(port);
            Assert.That(IsRequesting, Is.True);
            root.SetActive(false);
            Assert.That(IsRequesting, Is.False);
            Assert.That(button.interactable, Is.True);
            root.SetActive(true);
            yield return null;
        }

        [UnityTest]
        public IEnumerator InvalidJsonReleasesButtons()
        {
            int port = FreePort();
            listener = new HttpListener();
            listener.Prefixes.Add("http://127.0.0.1:" + port + "/");
            listener.Start();
            var response = Task.Run(async () =>
            {
                var context = await listener.GetContextAsync();
                byte[] body = Encoding.UTF8.GetBytes("{invalid json");
                context.Response.ContentLength64 = body.Length;
                await context.Response.OutputStream.WriteAsync(body, 0, body.Length);
                context.Response.Close();
            });
            StartRequest(port);
            yield return WaitForRecovery();
            Assert.That(response.IsFaulted, Is.False);
        }
    }
}
