using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIGuide
{
    [Serializable] public class StoryChapter { public int index; public string name; public string[] spoiler_markers; }
    [Serializable] public class CharacterStory { public StoryChapter[] chapters; }
    [Serializable]
    public class SpriteBinding
    {
        public string key;
        public Sprite sprite;
    }

    [Serializable]
    public class EmotionBinding
    {
        public string tag;
        public string[] blendShapeKeywords;
        [Range(0, 100)] public float weight = 40f;
    }

    [Serializable]
    public class MotionBinding
    {
        public string tag;
        public string animatorTrigger;
    }

    [Serializable] public class PackData
    {
        public string game_id;
        public string display_name;
        public string address_term;
        public List<SystemDef> systems;
        public List<StepDef> tutorial_steps;
        public List<string> screens;
    }

    [Serializable] public class SystemDef { public string id; public string name; public string ui_target; public UnlockDef unlock; public bool info_only; }
    [Serializable] public class UnlockDef { public string type; public int value; }
    [Serializable] public class StepDef { public string id; public string system; public string goal; public string @short; public string ui_target; public string action_label; }

    [Serializable]
    public class GuideState
    {
        public string tutorial_step;
        public string tutorial_goal;
        public string tutorial_screen;
        public string tutorial_target;
        public List<string> unlocked_systems = new List<string>();
        public int missions_cleared;
        public string screen = "lobby";
        public List<string> visible_targets = new List<string>();
        public bool in_cutscene;
        public bool result_playing;
        public bool player_typing;
        public int idle_seconds;
        public int seconds_since_last_line;
        public int fail_count;
        public int affection = 50;
        public int story_chapter;
        public string story_name;
        public string affection_band = "trust";
    }

    [Serializable]
    public class GuideRequest
    {
        public string trigger;
        public string player_input;
        public GuideState state;
        public string character_id;
        public string game_id;
        public string model;
        public bool use_schema = true;
    }

    [Serializable]
    public class GuideResponse
    {
        public bool speak;
        public string line;
        public string emotion;
        public string voice_tag;
        public string motion;
        public string ui_target;
        public string action;
        public string refusal;
        public string risk;
        public GuideDebug debug;
    }

    [Serializable]
    public class GuideDebug
    {
        public string model;
        public string parse;
        public string[] issues;
        public string[] card_ids;
        public int llm_ms;
        public int total_ms;
    }

    public static class GuideTriggers
    {
        public const string PlayerUtterance = "player_utterance";
        public const string IdleTick = "idle_tick";
        public const string ScreenEnter = "screen_enter";
        public const string ActionFailed = "action_failed";
    }
}
