using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIGuide
{
    [CreateAssetMenu(menuName = "AIGuide/Character Profile", fileName = "GuideCharacter_")]
    public class GuideCharacterProfile : ScriptableObject
    {
        [Header("식별")]
        public string serverCharacterId = "";
        public string displayName = "";
        public string addressTerm = "";
        public List<StoryChapter> storyChapters = new List<StoryChapter>();
        public GuideQuestionBank suggestions = new GuideQuestionBank();

        [Header("소속 게임")]
        [Tooltip("이 캐릭터가 안내하는 게임의 씬 이름. 캐릭터를 바꾸면 이 씬(게임 pack)으로 넘어간다. 비워 두면 지금 게임에 그대로 남는다")]
        public string homeScene = "";

        [Header("모델")]
        [Tooltip("서버에서 사용할 모델 키. base = 기본 모델, lora = 이 캐릭터용 LoRA를 병합한 모델")]
        public string modelKey = "adapter";

        [Header("외형")]
        public GameObject avatarPrefab;
        public Vector3 avatarPosition = new Vector3(0f, -1.1f, 0f);
        public Vector3 avatarEuler = new Vector3(0f, 180f, 0f);
        public float avatarScale = 1f;
        public Color nameColor = new Color(1f, 0.3f, 0.3f);

        [Header("2D 일러스트 (상반신). 비워 두면 3D 모델을 쓴다")]
        [Tooltip("자세별 몸 이미지. pose 태그는 모션 태그와 같다(idle, salute, hand_to_chest, battle_ready, look_away)")]
        public List<SpriteBinding> poseSprites = new List<SpriteBinding>();
        [Tooltip("표정 이미지(얼굴만 잘라 몸 위에 겹치는 방식). 표정이 몸 이미지에 포함된 경우 fullSprites를 쓴다")]
        public List<SpriteBinding> faceSprites = new List<SpriteBinding>();
        [Tooltip("표정과 자세가 한 장에 모두 들어간 이미지. 키 형식: 표정 또는 표정@자세 (예: soft_smile, stern@battle_ready)")]
        public List<SpriteBinding> fullSprites = new List<SpriteBinding>();
        public Sprite blinkFace;
        public Sprite talkMouthOpen;
        public Vector2 portraitAnchoredPos = new Vector2(0, 0);
        public float portraitScale = 1f;

        [Header("화면 테마 (캐릭터를 바꾸면 배경과 UI 모양, 색이 함께 바뀐다)")]
        public Sprite background;
        [Tooltip("배경 위에 덮는 어둡기. 0이면 배경 그대로")]
        [Range(0f, 1f)] public float backgroundDim = 0.35f;
        [Tooltip("패널(게임 영역, 대사창, 입력줄, 상단 바) 9-slice 모양")]
        public Sprite panelShape;
        [Tooltip("버튼 9-slice 모양")]
        public Sprite buttonShape;
        [Tooltip("모양 이미지의 모서리 크기 배율. 클수록 모서리가 작아진다")]
        public float shapeScale = 2f;
        public Color panelColor = new Color(0.03f, 0.04f, 0.06f, 0.8f);
        public Color buttonColor = new Color(0.16f, 0.24f, 0.34f, 0.95f);
        public Color accentColor = new Color(0.15f, 0.45f, 0.7f, 1f);
        [Tooltip("강조 테두리 모양(외곽선 9-slice). 비워 두면 직선 테두리를 쓴다")]
        public Sprite highlightShape;
        public float highlightScale = 0.4f;

        [Header("감정 태그 -> 블렌드셰이프 키워드")]
        public List<EmotionBinding> emotions = new List<EmotionBinding>();

        [Header("모션 태그 -> 애니메이터 트리거")]
        public List<MotionBinding> motions = new List<MotionBinding>();

        [Header("모델을 기다리는 동안이나 실패했을 때 쓰는 고정 대사")]
        public List<string> thinkingLines = new List<string>();
        public List<string> errorLines = new List<string>();
        public List<string> targetMissingLines = new List<string>();

        public Sprite FindSprite(List<SpriteBinding> list, string key) => list.Find(b => b.key == key)?.sprite;

        public EmotionBinding FindEmotion(string tag) => emotions.Find(e => e.tag == tag);
        public MotionBinding FindMotion(string tag) => motions.Find(m => m.tag == tag);

        public string Pick(List<string> pool, string fallback)
        {
            if (pool == null || pool.Count == 0) return fallback;
            return pool[UnityEngine.Random.Range(0, pool.Count)].Replace("{address}", addressTerm);
        }
    }

}
