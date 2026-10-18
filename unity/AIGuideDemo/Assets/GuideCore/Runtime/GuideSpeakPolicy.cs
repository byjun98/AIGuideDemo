using System;
using UnityEngine;

namespace AIGuide
{
    [Serializable]
    public class GuideSpeakPolicy
    {
        public bool enabled = true;
        public int idleHintSeconds = 20;
        public int minSecondsBetweenLines = 8;

        public string Check(string trigger, GuideState s)
        {
            if (!enabled) return null;
            bool auto = trigger == GuideTriggers.IdleTick || trigger == GuideTriggers.ScreenEnter;
            if (auto && s.in_cutscene) return "in_cutscene";
            if (auto && s.result_playing) return "result_playing";
            if (auto && s.player_typing) return "player_typing";
            if (trigger == GuideTriggers.IdleTick && s.idle_seconds < idleHintSeconds) return "short_idle";
            if (trigger == GuideTriggers.IdleTick && s.seconds_since_last_line < minSecondsBetweenLines) return "recent_line";
            if (trigger == GuideTriggers.IdleTick && string.IsNullOrEmpty(s.tutorial_target)) return "nothing_to_guide";
            if (trigger == GuideTriggers.ScreenEnter && s.screen != s.tutorial_screen) return "off_screen";
            return null;
        }
    }
}
