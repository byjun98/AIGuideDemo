using System;
using UnityEngine;

namespace AIGuide
{
    public interface IGuideGameAdapter
    {
        GuideGamePack Pack { get; }
        void FillState(GuideState state);
        bool IsTargetAvailable(string targetId);
        string ResolveTarget(string targetId);
        event Action<string> ActionFailed;
        event Action<string> ScreenChanged;
        event Action<string> StepCompleted;
    }

    public abstract class GuideGameAdapterBase : MonoBehaviour, IGuideGameAdapter
    {
        public abstract GuideGamePack Pack { get; }
        public abstract void FillState(GuideState state);
        public abstract bool IsTargetAvailable(string targetId);
        public virtual string ResolveTarget(string targetId) => null;
        public event Action<string> ActionFailed;
        public event Action<string> ScreenChanged;
        public event Action<string> StepCompleted;
        protected void RaiseActionFailed(string id) => ActionFailed?.Invoke(id);
        protected void RaiseScreenChanged(string id) => ScreenChanged?.Invoke(id);
        protected void RaiseStepCompleted(string id) => StepCompleted?.Invoke(id);
    }

    public interface IGuidePresenter
    {
        void Bind(GuideCharacterProfile profile);
        void ShowThinking(bool on);
        void Say(string line, string emotion, string motion);
        void Clear();
    }
}
