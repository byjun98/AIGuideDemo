using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIGuide
{
    [CreateAssetMenu(menuName = "AIGuide/Game Pack", fileName = "GuidePack_")]
    public class GuideGamePack : ScriptableObject
    {
        public TextAsset packJson;
        [NonSerialized] private PackData _data;

        public PackData Data
        {
            get
            {
                if (_data == null && packJson != null) _data = JsonUtility.FromJson<PackData>(packJson.text);
                return _data;
            }
        }

        public SystemDef System(string id) => Data?.systems?.Find(s => s.id == id);
        public StepDef Step(string id) => Data?.tutorial_steps?.Find(s => s.id == id);
    }

}
