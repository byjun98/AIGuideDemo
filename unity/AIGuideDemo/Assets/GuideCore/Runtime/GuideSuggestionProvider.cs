using System;
using System.Collections.Generic;

namespace AIGuide
{
    [Serializable]
    public class GuideQuestion
    {
        public string category;
        public string question;
        public int min_affection;
        public int max_affection = 100;
        public int story_chapter;
    }

    [Serializable]
    public class GuideQuestionBank
    {
        public string[] normal_questions = new string[0];
        public string locked_question = "";
        public string spoiler_question = "";
        public string[] oos_questions = new string[0];
        public string fallback_question = "";
        public List<GuideQuestion> questions = new List<GuideQuestion>();
    }
    public class GuideSuggestion { public string category; public string question; }

    public static class GuideSuggestionProvider
    {
        public static GuideSuggestion[] GetSuggestions(PackData pack, GuideState state, GuideCharacterProfile character, HashSet<string> asked, int turn)
        {
            var normal = new List<GuideSuggestion>();
            var boundary = new List<GuideSuggestion>();
            var personal = new List<GuideSuggestion>();
            var bank = character.suggestions;
            var step = pack.tutorial_steps.Find(s => s.id == state.tutorial_step);
            var system = step != null ? pack.systems.Find(s => s.id == step.system) : null;
            foreach (var template in bank.normal_questions)
            {
                if (template.Contains("{system}") && system == null) continue;
                normal.Add(new GuideSuggestion { category = "지금 할 일", question = template.Replace("{system}", system != null ? system.name : "") });
            }
            foreach (var item in pack.systems)
                if (!state.unlocked_systems.Contains(item.id))
                    boundary.Add(new GuideSuggestion { category = "잠긴 기능", question = bank.locked_question.Replace("{system}", item.name) });
            foreach (var chapter in character.storyChapters)
            {
                if (chapter.index <= state.story_chapter || chapter.spoiler_markers == null || chapter.spoiler_markers.Length == 0) continue;
                boundary.Add(new GuideSuggestion { category = "스포일러", question = bank.spoiler_question.Replace("{marker}", chapter.spoiler_markers[0]) });
                break;
            }
            foreach (var question in bank.oos_questions)
                boundary.Add(new GuideSuggestion { category = "관계없는 질문", question = question });
            foreach (var question in bank.questions)
                if (question.min_affection <= state.affection && state.affection <= question.max_affection && question.story_chapter <= state.story_chapter)
                    personal.Add(new GuideSuggestion { category = question.category, question = question.question });
            if (!string.IsNullOrEmpty(bank.fallback_question)) personal.Add(new GuideSuggestion { category = "자기소개", question = bank.fallback_question });
            return new[] { Pick(normal, asked, 0), Pick(boundary, asked, turn), Pick(personal, asked, turn) };
        }

        static GuideSuggestion Pick(List<GuideSuggestion> candidates, HashSet<string> asked, int offset)
        {
            for (int i = 0; i < candidates.Count; i++)
            {
                var candidate = candidates[(offset + i) % candidates.Count];
                if (!asked.Contains(candidate.question)) return candidate;
            }
            return null;
        }
    }
}
