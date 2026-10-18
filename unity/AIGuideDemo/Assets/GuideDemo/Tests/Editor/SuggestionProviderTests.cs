using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace AIGuide.Tests
{
    public class SuggestionProviderTests
    {
        static void SetTemplates(GuideCharacterProfile character)
        {
            character.suggestions.normal_questions = new[] { "진행 순서는?", "{system} 위치는?" };
            character.suggestions.locked_question = "{system} 해금 조건은?";
            character.suggestions.spoiler_question = "{marker} 이야기는?";
            character.suggestions.oos_questions = new[] { "세금은?" };
            character.suggestions.fallback_question = "자기소개는?";
        }

        [Test]
        public void SuggestionsRespectStoryAndAffectionProgress()
        {
            var pack = new PackData { systems = new List<SystemDef>(), tutorial_steps = new List<StepDef>() };
            var character = ScriptableObject.CreateInstance<GuideCharacterProfile>();
            SetTemplates(character);
            character.storyChapters.Add(new StoryChapter { index = 1, name = "Next", spoiler_markers = new[] { "Secret" } });
            character.suggestions.questions.Add(new GuideQuestion { category = "호감도", question = "Low", max_affection = 50 });
            character.suggestions.questions.Add(new GuideQuestion { category = "호감도", question = "High", min_affection = 51 });
            try
            {
                var state = new GuideState { affection = 10 };
                var low = GuideSuggestionProvider.GetSuggestions(pack, state, character, new HashSet<string>(), 0);
                Assert.That(low[1].category, Is.EqualTo("스포일러"));
                Assert.That(low[1].question, Does.Contain("Secret"));
                Assert.That(low[2].question, Is.EqualTo("Low"));
                state.affection = 90; state.story_chapter = 1;
                var high = GuideSuggestionProvider.GetSuggestions(pack, state, character, new HashSet<string>(), 0);
                Assert.That(high[1].category, Is.EqualTo("관계없는 질문"));
                Assert.That(high[2].question, Is.EqualTo("High"));
            }
            finally { UnityEngine.Object.DestroyImmediate(character); }
        }

        [Test]
        public void SuggestionsUsePackStateAndNeverRepeatAskedQuestions()
        {
            var provider = Type.GetType("AIGuide.GuideSuggestionProvider, GuideCore");
            Assert.That(provider, Is.Not.Null, "The generic suggestion provider is required");
            var method = provider.GetMethod("GetSuggestions");
            var pack = new PackData {
                systems = new List<SystemDef> { new SystemDef { id = "open", name = "첫 기능" }, new SystemDef { id = "locked", name = "잠긴 기능" } },
                tutorial_steps = new List<StepDef> { new StepDef { id = "S1", system = "open" } }
            };
            var state = new GuideState { tutorial_step = "S1", unlocked_systems = new List<string> { "open" } };
            var character = ScriptableObject.CreateInstance<GuideCharacterProfile>();
            SetTemplates(character);
            try
            {
                var used = new HashSet<string>();
                var suggestions = ((IEnumerable)method.Invoke(null, new object[] { pack, state, character, used, 0 })).Cast<object>().ToArray();
                Assert.That(suggestions.Length, Is.EqualTo(3));
                string Question(object item) => (string)item.GetType().GetField("question").GetValue(item);
                Assert.That(Question(suggestions[1]), Does.Contain("잠긴 기능"));
                foreach (var suggestion in suggestions) used.Add(Question(suggestion));
                var next = ((IEnumerable)method.Invoke(null, new object[] { pack, state, character, used, 1 })).Cast<object>().ToArray();
                Assert.That(next.Where(s => s != null).Select(Question).Any(used.Contains), Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(character); }
        }
    }
}
