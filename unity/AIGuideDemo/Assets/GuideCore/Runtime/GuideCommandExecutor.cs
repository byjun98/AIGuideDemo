using System;

namespace AIGuide
{
    public class GuideCommandExecutor
    {
        readonly IGuideGameAdapter _game;
        readonly GuideHighlighter _highlighter;

        public GuideCommandExecutor(IGuideGameAdapter game, GuideHighlighter highlighter)
        {
            _game = game;
            _highlighter = highlighter;
        }

        public struct Result
        {
            public string stage;
            public string reason;
            public bool ok;
        }

        public Result Execute(GuideResponse r)
        {
            if (r == null) return Fail("null_response");
            if (string.IsNullOrEmpty(r.action) || r.action == "none" || string.IsNullOrEmpty(r.ui_target))
            {
                _highlighter?.Hide();
                return new Result { stage = "skipped", ok = true };
            }
            if (r.action != "highlight") return Fail("unknown_action:" + r.action);
            string id = r.ui_target, stage = "executed", reason = null;
            if (!_game.IsTargetAvailable(id))
            {
                string alt = _game.ResolveTarget(id);
                if (string.IsNullOrEmpty(alt) || !_game.IsTargetAvailable(alt)) return Fail("target_unavailable:" + id);
                reason = "fallback:" + id + "->" + alt; id = alt; stage = "executed_fallback";
            }
            if (!GuideUiTarget.TryGet(id, out var target)) return Fail("target_not_in_scene:" + id);
            _highlighter?.Show(target.Rect);
            return new Result { stage = stage, reason = reason, ok = true };
        }

        static Result Fail(string reason) => new Result { stage = "failed", reason = reason, ok = false };
    }
}
