using NUnit.Framework;
using UnityEngine;

namespace AIGuide.Tests
{
    public class PresenterLifecycleTests
    {
        [Test]
        public void SpriteSayBeforeBindDoesNotThrow()
        {
            var go = new GameObject("PresenterTest");
            try { Assert.DoesNotThrow(() => go.AddComponent<GuideSpritePresenter>().Say("hello", "neutral", "nod")); }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
