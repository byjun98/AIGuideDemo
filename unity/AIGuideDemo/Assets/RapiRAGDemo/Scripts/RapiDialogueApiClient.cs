using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace RapiRAGDemo
{
    public class RapiDialogueApiClient : MonoBehaviour
    {
        [Header("API")]
        public string endpoint = "http://127.0.0.1:8001/dialogue/generate";
        [Min(1)] public int requestTimeoutSeconds = 60;
        public bool autoRequestOnStart = false;
        public float autoRequestDelay = 0.8f;

        [Header("Runtime State")]
        [Range(1, 30)] public int bondRank = 22;
        [Range(1, 46)] public int storyChapter = 4;
        public int selectedSceneIndex = 1;

        [Header("Dialogue UI")]
        public Text speakerText;
        public Text lineText;
        public Text statusText;
        public Text riskText;
        public Text modeText;
        public Text rankText;
        public Text stateSummaryText;
        public Text storyProgressText;
        public Text sceneText;
        public Text adviceFooterText;
        public Text nextEpisodeText;
        public GameObject adviceOverlay;
        public Button adviceAllTabButton;
        public Button adviceMissionTabButton;
        public Button adviceDailyTabButton;
        public Button adviceMemoryTabButton;
        public Button adviceStoryTabButton;
        public Button adviceSpecialTabButton;

        [Header("Gift UI")]
        public GameObject giftOverlay;
        public Text giftTitleText;
        public Text giftRankText;
        public Text giftGaugeText;
        public Text giftHintText;
        public Button closeGiftButton;
        public Button giftAllTabButton;
        public Button giftFavoriteTabButton;
        public Button giftPremiumTabButton;
        public Button giftCommonTabButton;
        public Button giftConfirmButton;
        public Button[] giftItemButtons;
        public Text[] giftItemNameLabels;
        public Text[] giftItemMetaLabels;
        public Image[] giftItemFrames;

        [Header("Buttons")]
        public Button giftButton;
        public Button adviseButton;
        public Button closeAdviceButton;
        public Button[] choiceButtons;
        public Text[] choiceButtonLabels;
        public Button rankDownButton;
        public Button rankUpButton;
        public Button chapterDownButton;
        public Button chapterUpButton;
        public Button scenePrevButton;
        public Button sceneNextButton;

        [Header("Scene")]
        public RapiLobbyAnimator characterAnimator;

        private readonly List<string> recentLines = new List<string>();
        private readonly List<string> recentCardIds = new List<string>();
        private readonly List<DialogueChoice> currentChoices = new List<DialogueChoice>();
        private readonly List<GiftItem> giftItems = new List<GiftItem>();
        private readonly List<int> visibleGiftIndices = new List<int>();
        private bool isRequesting;
        private Coroutine dialogueRequest;
        private UnityWebRequest activeRequest;
        private DialogueChoice pendingChoice;
        private AdviceCategory selectedAdviceCategory = AdviceCategory.All;
        private GiftCategory selectedGiftCategory = GiftCategory.All;
        private int selectedGiftIndex = -1;
        private bool currentPayloadHasGift;
        private string currentGiftId;
        private string currentGiftName;
        private string currentGiftCategory;
        private string currentGiftPreference;
        private int currentGiftAffectionGain;
        private string currentQuery = "선물을 받은 뒤 라피가 절제되게 고마워하는 짧은 호감도 대사";
        private string currentSceneId = "gift_received";
        private string currentRecentAction = "gave_favorite_gift";
        private string currentResultLabel = "선물 반응";

        private readonly ScenePreset[] scenePresets =
        {
            new ScenePreset("lobby_morning", "로비 아침"),
            new ScenePreset("advise_session", "상담"),
            new ScenePreset("after_battle_hard", "고난도 전투 후"),
            new ScenePreset("event_idle", "이벤트 대기")
        };

        private void Awake()
        {
            if (giftButton != null)
            {
                giftButton.onClick.AddListener(OpenGiftModal);
            }

            if (adviseButton != null)
            {
                adviseButton.onClick.AddListener(OpenAdviceChoices);
            }

            if (closeAdviceButton != null)
            {
                closeAdviceButton.onClick.AddListener(CloseAdviceChoices);
            }

            if (closeGiftButton != null)
            {
                closeGiftButton.onClick.AddListener(CloseGiftModal);
            }

            if (giftConfirmButton != null)
            {
                giftConfirmButton.onClick.AddListener(ConfirmSelectedGift);
            }

            HookGiftTabButton(giftAllTabButton, GiftCategory.All);
            HookGiftTabButton(giftFavoriteTabButton, GiftCategory.Favorite);
            HookGiftTabButton(giftPremiumTabButton, GiftCategory.Premium);
            HookGiftTabButton(giftCommonTabButton, GiftCategory.Common);
            HookAdviceTabButton(adviceAllTabButton, AdviceCategory.All);
            HookAdviceTabButton(adviceMissionTabButton, AdviceCategory.Mission);
            HookAdviceTabButton(adviceDailyTabButton, AdviceCategory.Daily);
            HookAdviceTabButton(adviceMemoryTabButton, AdviceCategory.Memory);
            HookAdviceTabButton(adviceStoryTabButton, AdviceCategory.Story);
            HookAdviceTabButton(adviceSpecialTabButton, AdviceCategory.Special);
            HookGiftItemButtons();
            HookChoiceButtons();
            HookStateButtons();
        }

        private IEnumerator Start()
        {
            RefreshStateUi();
            SetIdleCopy();
            CloseAdviceChoices();
            CloseGiftModal();

            if (!autoRequestOnStart)
            {
                yield break;
            }

            yield return new WaitForSeconds(autoRequestDelay);
            RequestGiftDialogue();
        }

        private void Update()
        {
            var selected = UnityEngine.EventSystems.EventSystem.current != null
                ? UnityEngine.EventSystems.EventSystem.current.currentSelectedGameObject : null;
            bool inputFocused = selected != null && (selected.GetComponent<InputField>() != null || selected.GetComponent<TMPro.TMP_InputField>() != null);
            bool giftOpen = giftOverlay != null && giftOverlay.activeInHierarchy;
            bool adviceOpen = adviceOverlay != null && adviceOverlay.activeInHierarchy;
            if (Keyboard.current == null || isRequesting || inputFocused || (!giftOpen && !adviceOpen))
            {
                return;
            }

            if (giftOpen && Keyboard.current.spaceKey.wasPressedThisFrame)
            {
                ConfirmSelectedGift();
            }

            if (!adviceOpen)
            {
                if (Keyboard.current.escapeKey.wasPressedThisFrame) CloseGiftModal();
                return;
            }

            if (Keyboard.current.digit1Key.wasPressedThisFrame)
            {
                RequestChoice(0);
            }

            if (Keyboard.current.digit2Key.wasPressedThisFrame)
            {
                RequestChoice(1);
            }

            if (Keyboard.current.digit3Key.wasPressedThisFrame)
            {
                RequestChoice(2);
            }

            if (Keyboard.current.digit4Key.wasPressedThisFrame)
            {
                RequestChoice(3);
            }

            if (Keyboard.current.digit5Key.wasPressedThisFrame)
            {
                RequestChoice(4);
            }

            if (Keyboard.current.digit6Key.wasPressedThisFrame)
            {
                RequestChoice(5);
            }

            if (Keyboard.current.escapeKey.wasPressedThisFrame)
            {
                CloseAdviceChoices();
                CloseGiftModal();
            }
        }

        public void RequestGiftDialogue()
        {
            if (isRequesting) return;
            EnsureGiftItems();
            if (giftItems.Count == 0)
            {
                return;
            }

            RequestGiftDialogue(giftItems[0]);
        }

        public void OpenGiftModal()
        {
            if (isRequesting)
            {
                return;
            }

            EnsureGiftItems();
            CloseAdviceChoices();
            RefreshStateUi();

            if (selectedGiftIndex < 0 && giftItems.Count > 0)
            {
                selectedGiftIndex = 0;
            }

            RebuildGiftItems();
            if (giftOverlay != null)
            {
                giftOverlay.SetActive(true);
            }

            SetMode("선물 선택");
            SetStatus("라피에게 줄 선물을 선택해 주세요.");
            SetLine("선물 종류에 따라 라피의 반응과 호감도 상승량이 달라집니다.");
            SetRisk("대기 중");
        }

        public void CloseGiftModal()
        {
            if (giftOverlay != null)
            {
                giftOverlay.SetActive(false);
            }
        }

        public void SelectGiftCategory(int category)
        {
            selectedGiftCategory = (GiftCategory)Mathf.Clamp(category, 0, 3);
            RebuildGiftItems();
        }

        public void SelectGiftItem(int visibleIndex)
        {
            if (visibleIndex < 0 || visibleIndex >= visibleGiftIndices.Count)
            {
                return;
            }

            selectedGiftIndex = visibleGiftIndices[visibleIndex];
            RebuildGiftItems();
        }

        public void ConfirmSelectedGift()
        {
            if (isRequesting) return;
            EnsureGiftItems();
            if (selectedGiftIndex < 0 || selectedGiftIndex >= giftItems.Count)
            {
                return;
            }

            GiftItem gift = giftItems[selectedGiftIndex];
            bondRank = Mathf.Clamp(bondRank + gift.rankDelta, 1, 30);
            RefreshStateUi();
            CloseGiftModal();
            RequestGiftDialogue(gift);
        }

        private void RequestGiftDialogue(GiftItem selectedGift)
        {
            if (isRequesting) return;
            DialogueChoice gift = new DialogueChoice
            {
                label = selectedGift.displayName,
                resultLabel = selectedGift.resultLabel,
                sceneId = "gift_received",
                actionId = selectedGift.actionId,
                query = BuildGiftQuery(selectedGift)
            };

            ApplyChoice(gift);
            ApplyGiftPayload(selectedGift);
            CloseAdviceChoices();
            RequestDialogue(selectedGift.displayName + " 반응 생성 중...");
        }

        public void OpenAdviceChoices()
        {
            CloseGiftModal();
            RefreshStateUi();
            RebuildAdviceChoices();

            if (adviceOverlay != null)
            {
                adviceOverlay.SetActive(true);
            }

            SetMode("상담 선택");
            SetStatus("상담 주제를 선택해 주세요.");
            SetLine("지휘관, 현재 상태에 맞는 상담 항목을 준비했습니다.");
            SetRisk("대기 중");
        }

        public void CloseAdviceChoices()
        {
            if (adviceOverlay != null)
            {
                adviceOverlay.SetActive(false);
            }
        }

        public void RequestChoice(int index)
        {
            if (isRequesting) return;
            if (currentChoices.Count == 0)
            {
                RebuildAdviceChoices();
            }

            if (index < 0 || index >= currentChoices.Count)
            {
                return;
            }

            ApplyChoice(currentChoices[index]);
            CloseAdviceChoices();
            RequestDialogue("상담 답변 생성 중...");
        }

        public void ChangeBondRank(int delta)
        {
            bondRank = Mathf.Clamp(bondRank + delta, 1, 30);
            RefreshStateUi();

            if (adviceOverlay != null && adviceOverlay.activeSelf)
            {
                RebuildAdviceChoices();
            }

            if (giftOverlay != null && giftOverlay.activeSelf)
            {
                RebuildGiftItems();
            }
        }

        public void ChangeStoryChapter(int delta)
        {
            storyChapter = Mathf.Clamp(storyChapter + delta, 1, 46);
            RefreshStateUi();

            if (adviceOverlay != null && adviceOverlay.activeSelf)
            {
                RebuildAdviceChoices();
            }

            if (giftOverlay != null && giftOverlay.activeSelf)
            {
                RefreshGiftHeader();
            }
        }

        public void ChangeScene(int delta)
        {
            selectedSceneIndex += delta;
            if (selectedSceneIndex < 0)
            {
                selectedSceneIndex = scenePresets.Length - 1;
            }
            else if (selectedSceneIndex >= scenePresets.Length)
            {
                selectedSceneIndex = 0;
            }

            RefreshStateUi();

            if (adviceOverlay != null && adviceOverlay.activeSelf)
            {
                RebuildAdviceChoices();
            }

            if (giftOverlay != null && giftOverlay.activeSelf)
            {
                RefreshGiftHeader();
            }
        }

        private void HookGiftTabButton(Button button, GiftCategory category)
        {
            if (button != null)
            {
                button.onClick.AddListener(() => SelectGiftCategory((int)category));
            }
        }

        private void HookAdviceTabButton(Button button, AdviceCategory category)
        {
            if (button != null)
            {
                button.onClick.AddListener(() => SelectAdviceCategory((int)category));
            }
        }

        public void SelectAdviceCategory(int category)
        {
            selectedAdviceCategory = (AdviceCategory)Mathf.Clamp(category, 0, 5);
            RebuildAdviceChoices();
        }

        private void HookGiftItemButtons()
        {
            if (giftItemButtons == null)
            {
                return;
            }

            for (int i = 0; i < giftItemButtons.Length; i++)
            {
                int captured = i;
                if (giftItemButtons[i] != null)
                {
                    giftItemButtons[i].onClick.AddListener(() => SelectGiftItem(captured));
                }
            }
        }

        private void HookChoiceButtons()
        {
            if (choiceButtons == null)
            {
                return;
            }

            for (int i = 0; i < choiceButtons.Length; i++)
            {
                int captured = i;
                if (choiceButtons[i] != null)
                {
                    choiceButtons[i].onClick.AddListener(() => RequestChoice(captured));
                }
            }
        }

        private void HookStateButtons()
        {
            if (rankDownButton != null)
            {
                rankDownButton.onClick.AddListener(() => ChangeBondRank(-1));
            }

            if (rankUpButton != null)
            {
                rankUpButton.onClick.AddListener(() => ChangeBondRank(1));
            }

            if (chapterDownButton != null)
            {
                chapterDownButton.onClick.AddListener(() => ChangeStoryChapter(-1));
            }

            if (chapterUpButton != null)
            {
                chapterUpButton.onClick.AddListener(() => ChangeStoryChapter(1));
            }

            if (scenePrevButton != null)
            {
                scenePrevButton.onClick.AddListener(() => ChangeScene(-1));
            }

            if (sceneNextButton != null)
            {
                sceneNextButton.onClick.AddListener(() => ChangeScene(1));
            }
        }

        private void EnsureGiftItems()
        {
            if (giftItems.Count > 0)
            {
                return;
            }

            giftItems.Add(new GiftItem(
                "gift_rapi_favorite_milk",
                "♥ 밀크",
                GiftCategory.Favorite,
                "라피 최애 · 크게 오름",
                "최고 선호",
                7,
                2,
                "gave_rapi_favorite_gift_milk",
                "최애 선물 반응",
                new Color(1f, 0.2f, 0.22f, 0.98f)));
            giftItems.Add(new GiftItem(
                "gift_other_favorite_date_ticket",
                "데이트 이용권",
                GiftCategory.Premium,
                "고급 · 타 니케 선호",
                "적당히 선호",
                4,
                1,
                "gave_high_grade_other_nikke_gift",
                "고급 선물 반응",
                new Color(0.86f, 0.18f, 0.82f, 0.98f)));
            giftItems.Add(new GiftItem(
                "gift_other_favorite_module_booster",
                "모듈 부스터",
                GiftCategory.Premium,
                "고급 · 실용품",
                "적당히 선호",
                4,
                1,
                "gave_high_grade_practical_gift",
                "고급 선물 반응",
                new Color(0.95f, 0.62f, 0.12f, 0.98f)));
            giftItems.Add(new GiftItem(
                "gift_other_favorite_tactical_note",
                "전술 교본",
                GiftCategory.Premium,
                "고급 · 타 니케 선호",
                "적당히 선호",
                4,
                1,
                "gave_high_grade_other_nikke_gift",
                "고급 선물 반응",
                new Color(0.78f, 0.26f, 0.88f, 0.98f)));
            giftItems.Add(new GiftItem(
                "gift_common_purple",
                "공용 보라 선물",
                GiftCategory.Common,
                "공용 · 보라 등급",
                "소폭 선호",
                3,
                1,
                "gave_common_purple_gift",
                "공용 선물 반응",
                new Color(0.54f, 0.22f, 0.9f, 0.98f)));
            giftItems.Add(new GiftItem(
                "gift_common_blue",
                "공용 파란 선물",
                GiftCategory.Common,
                "공용 · 파란 등급",
                "가볍게 선호",
                2,
                1,
                "gave_common_blue_gift",
                "공용 선물 반응",
                new Color(0.08f, 0.56f, 0.95f, 0.98f)));
        }

        private void RebuildGiftItems()
        {
            EnsureGiftItems();
            visibleGiftIndices.Clear();

            for (int i = 0; i < giftItems.Count; i++)
            {
                if (selectedGiftCategory == GiftCategory.All || giftItems[i].category == selectedGiftCategory)
                {
                    visibleGiftIndices.Add(i);
                }
            }

            if (visibleGiftIndices.Count > 0 && !visibleGiftIndices.Contains(selectedGiftIndex))
            {
                selectedGiftIndex = visibleGiftIndices[0];
            }

            ApplyGiftButtons();
            RefreshGiftHeader();
        }

        private void ApplyGiftButtons()
        {
            int max = giftItemButtons == null ? 0 : giftItemButtons.Length;
            for (int i = 0; i < max; i++)
            {
                bool active = i < visibleGiftIndices.Count;
                if (giftItemButtons[i] != null)
                {
                    giftItemButtons[i].gameObject.SetActive(active);
                    giftItemButtons[i].interactable = active && !isRequesting;
                }

                GiftItem gift = active ? giftItems[visibleGiftIndices[i]] : default;
                if (giftItemNameLabels != null && i < giftItemNameLabels.Length && giftItemNameLabels[i] != null)
                {
                    giftItemNameLabels[i].text = active ? gift.displayName : "";
                }

                if (giftItemMetaLabels != null && i < giftItemMetaLabels.Length && giftItemMetaLabels[i] != null)
                {
                    giftItemMetaLabels[i].text = active ? gift.metaLabel + "\n+" + gift.affectionGain : "";
                }

                if (giftItemFrames != null && i < giftItemFrames.Length && giftItemFrames[i] != null)
                {
                    Color color = active ? gift.uiColor : new Color(0.72f, 0.72f, 0.74f, 0.95f);
                    if (active && visibleGiftIndices[i] == selectedGiftIndex)
                    {
                        color = Color.Lerp(color, Color.white, 0.24f);
                    }

                    giftItemFrames[i].color = color;
                }
            }

            ApplyGiftTabVisual(giftAllTabButton, GiftCategory.All);
            ApplyGiftTabVisual(giftFavoriteTabButton, GiftCategory.Favorite);
            ApplyGiftTabVisual(giftPremiumTabButton, GiftCategory.Premium);
            ApplyGiftTabVisual(giftCommonTabButton, GiftCategory.Common);
            SetButton(giftConfirmButton, selectedGiftIndex >= 0 && !isRequesting);
        }

        private void ApplyGiftTabVisual(Button button, GiftCategory category)
        {
            if (button == null)
            {
                return;
            }

            Image image = button.GetComponent<Image>();
            if (image != null)
            {
                image.color = selectedGiftCategory == category
                    ? new Color(0.08f, 0.62f, 0.94f, 0.98f)
                    : new Color(0.12f, 0.13f, 0.15f, 0.96f);
            }
        }

        private void RefreshGiftHeader()
        {
            if (giftTitleText != null)
            {
                giftTitleText.text = "♥ 선물하기";
            }

            if (giftRankText != null)
            {
                giftRankText.text = string.Format("RANK {0}  >  RANK {1}", bondRank, PreviewGiftRank());
            }

            if (giftGaugeText != null)
            {
                giftGaugeText.text = string.Format("R{0}/{1} EXP {2}", bondRank, CurrentBondCap(), CurrentBondExp());
            }

            if (giftHintText != null)
            {
                giftHintText.text = SelectedGiftHint();
            }
        }

        private int PreviewGiftRank()
        {
            if (selectedGiftIndex < 0 || selectedGiftIndex >= giftItems.Count)
            {
                return bondRank;
            }

            return Mathf.Clamp(bondRank + giftItems[selectedGiftIndex].rankDelta, 1, 30);
        }

        private string SelectedGiftHint()
        {
            if (selectedGiftIndex < 0 || selectedGiftIndex >= giftItems.Count)
            {
                return "선물을 선택하면 예상 상승량이 표시됩니다.";
            }

            GiftItem gift = giftItems[selectedGiftIndex];
            return gift.displayName + " / " + GiftMatchTypeForCategory(gift.category) + " / +" + gift.affectionGain;
        }

        private void RebuildAdviceChoices()
        {
            currentChoices.Clear();
            ScenePreset scene = CurrentScene();
            string band = CurrentBandId();

            AddChoice("임무 상태를 먼저 확인한다.", "기본 상담", AdviceCategory.Mission, scene.id, "advise_choice_mission_check", 1, 1,
                "상담 주제: 임무 상태 확인. 현재 장면, 호감도, 스토리 진행도에 맞춰 라피가 작전 준비와 지휘관의 컨디션을 짧게 점검하는 답변");

            AddChoice("오늘 작전 우선순위를 묻는다.", "작전 상담", AdviceCategory.Mission, "advise_session", "advise_choice_operation_priority", 1, 1,
                "상담 주제: 오늘 작전 우선순위. RAG의 임무/지휘관실/작전 판단 정보를 근거로 라피가 무엇부터 확인할지 보고하듯 답하는 대사");

            AddChoice("내 컨디션을 물어본다.", "컨디션 상담", AdviceCategory.Mission, "advise_session", "advise_choice_commander_condition", 1, 1,
                "상담 주제: 지휘관 컨디션 확인. 라피가 임무 보고 말투를 유지하면서도 지휘관의 무리 여부를 조용히 걱정하는 짧은 답변");

            if (bondRank >= 6 && storyChapter >= 2)
            {
                AddChoice("전초기지 생활에 대해 묻는다.", "전초기지 상담", AdviceCategory.Daily, "lobby_morning", "advise_choice_outpost_life", 6, 2,
                    "상담 주제: 전초기지 생활. 반복되는 임무와 생활 공간에 대해 라피가 친근하지만 절제되게 답하는 상담 대사");

                AddChoice("지휘관실이 익숙한지 묻는다.", "일상 상담", AdviceCategory.Daily, "lobby_morning", "advise_choice_commander_room", 6, 2,
                    "상담 주제: 지휘관실과 일상 루틴. 현재 배경과 전초기지 RAG 정보를 근거로 라피가 공간 적응과 대기 시간을 담백하게 말하는 대사");
            }

            if (bondRank >= 10 && storyChapter >= 2)
            {
                AddChoice("잠깐 쉬어도 되는지 묻는다.", "휴식 상담", AdviceCategory.Daily, "lobby_morning", "advise_choice_short_rest", 10, 2,
                    "상담 주제: 짧은 휴식. 라피가 임무 효율과 지휘관 건강을 함께 고려하며 쉬는 것을 허락하거나 권하는 짧은 대사");
            }

            if (bondRank >= 15 && storyChapter >= 3)
            {
                AddChoice("지금까지 쌓인 기억.", "상담 결과 · 쌓인 기억", AdviceCategory.Memory, "advise_session", "advise_choice_past_memory", 15, 3,
                    "상담 주제: 지금까지 쌓인 기억. 현재까지 해금된 이야기와 RAG 카드만 바탕으로 라피가 차분하게 기억을 돌아보는 대사");
            }

            if (bondRank >= 15 && storyChapter >= 3)
            {
                AddChoice("앞으로 쌓아나갈 기억.", "상담 결과 · 앞으로의 기억", AdviceCategory.Memory, "advise_session", "advise_choice_future_memory", 15, 3,
                    "상담 주제: 앞으로 쌓아나갈 기억. 라피가 신뢰와 보호 의지를 조용히 표현하되 관계 단계보다 앞서가지 않는 대사");
            }

            if (bondRank >= 18 && storyChapter >= 4)
            {
                AddChoice("내 판단을 신뢰하는지 묻는다.", "신뢰 상담", AdviceCategory.Memory, "advise_session", "advise_choice_trust_judgment", 18, 4,
                    "상담 주제: 지휘관의 판단에 대한 신뢰. 챕터 4까지의 판단/명령/존재 의미 맥락을 근거로 라피가 신뢰를 절제되게 표현하는 답변");
            }

            if (storyChapter >= 3 && scene.id == "after_battle_hard")
            {
                AddChoice("방금 전투가 신경 쓰인다.", "전투 후 상담", AdviceCategory.Mission, "after_battle_hard", "advise_choice_after_battle", 10, 3,
                    "상담 주제: 고난도 전투 후. 라피가 결과 보고와 지휘관의 무리 여부를 함께 걱정하는 짧은 상담 대사");
            }

            if (storyChapter >= 3 && bondRank >= 12)
            {
                AddChoice("초반 작전에서 배운 점을 묻는다.", "스토리 상담", AdviceCategory.Story, "advise_session", "advise_choice_chapter_three", 12, 3,
                    "상담 주제: 챕터 3까지의 초반 작전 경험. 강적 조우와 다음 대응을 스포일러 없이 짧게 돌아보는 라피의 답변");
            }

            if (storyChapter >= 4 && bondRank >= 18)
            {
                AddChoice("최근 작전의 의미를 묻는다.", "스토리 상담", AdviceCategory.Story, "advise_session", "advise_choice_chapter_four", 18, 4,
                    "상담 주제: 챕터 4까지 공개된 작전 맥락. 라피가 존재 의미와 명령에 대해 스포일러 없이 절제되게 답하는 대사");
            }

            if (storyChapter >= 5 && bondRank >= 15)
            {
                AddChoice("설원 작전이 남긴 것을 묻는다.", "설원 상담", AdviceCategory.Story, "advise_session", "advise_choice_chapter_five_snowfield", 15, 5,
                    "상담 주제: 챕터 5 설원/구조/재합류 맥락. 라피가 감상적으로 길어지지 않고 구조 확인과 다음 대응을 말하는 대사");
            }

            if (bondRank >= 25 && band == "special_trust")
            {
                AddChoice("조금 더 솔직하게 말해도 돼.", "특별 상담", AdviceCategory.Special, "advise_session", "advise_choice_special_trust", 25, 4,
                    "상담 주제: 특별한 신뢰. 라피가 과장 없이 아주 짧게 속마음을 드러내는 상담 대사");

                AddChoice("나를 특별히 대하는 이유를 묻는다.", "특별 신뢰 상담", AdviceCategory.Special, "advise_session", "advise_choice_special_reason", 25, 4,
                    "상담 주제: 특별한 신뢰의 이유. 라피가 둘만 아는 맥락을 직접적인 고백으로 과장하지 않고 짧게 답하는 대사");
            }

            if (storyChapter >= 34 && bondRank >= 20)
            {
                AddChoice("지금의 라피에 대해 묻는다.", "현재 라피 상담", AdviceCategory.Story, "advise_session", "advise_choice_current_rapi", 20, 34,
                    "상담 주제: 챕터 34 이후 현재 라피. 레드 후드 상태에서 계승과 자기 자신으로 살아가는 결의를 짧게 표현하는 대사");
            }

            if (storyChapter >= 46 && bondRank >= 20)
            {
                AddChoice("누군가의 짐을 함께 질 수 있냐고 묻는다.", "후반 스토리 상담", AdviceCategory.Story, "advise_session", "advise_choice_share_burden", 20, 46,
                    "상담 주제: 챕터 46까지 허용된 후반 스토리. 라피가 상처와 계승의 짐을 함께 짊어지는 태도를 조용히 말하는 대사");
            }

            FilterAdviceChoices(scene.id);
            ApplyChoiceButtons();
        }

        private void AddChoice(string label, string resultLabel, AdviceCategory category, string sceneId, string actionId, int minRank, int minChapter, string query)
        {
            if (bondRank < minRank || storyChapter < minChapter)
            {
                return;
            }

            currentChoices.Add(new DialogueChoice
            {
                label = label,
                resultLabel = resultLabel,
                category = category,
                sceneId = sceneId,
                actionId = actionId,
                query = query
            });
        }

        private void FilterAdviceChoices(string selectedSceneId)
        {
            List<DialogueChoice> ordered = new List<DialogueChoice>();
            for (int i = 0; i < currentChoices.Count; i++)
            {
                if (currentChoices[i].sceneId == selectedSceneId && AdviceCategoryMatches(currentChoices[i]))
                {
                    ordered.Add(currentChoices[i]);
                }
            }

            for (int i = 0; i < currentChoices.Count; i++)
            {
                if (currentChoices[i].sceneId != selectedSceneId && AdviceCategoryMatches(currentChoices[i]))
                {
                    ordered.Add(currentChoices[i]);
                }
            }

            currentChoices.Clear();
            int maxChoices = choiceButtons == null ? 0 : choiceButtons.Length;
            int count = Mathf.Min(maxChoices, ordered.Count);
            for (int i = 0; i < count; i++)
            {
                currentChoices.Add(ordered[i]);
            }
        }

        private bool AdviceCategoryMatches(DialogueChoice choice)
        {
            return selectedAdviceCategory == AdviceCategory.All || choice.category == selectedAdviceCategory;
        }

        private void ApplyChoiceButtons()
        {
            int max = choiceButtons == null ? 0 : choiceButtons.Length;
            for (int i = 0; i < max; i++)
            {
                bool active = i < currentChoices.Count;
                if (choiceButtons[i] != null)
                {
                    choiceButtons[i].gameObject.SetActive(active);
                    choiceButtons[i].interactable = active && !isRequesting;
                }

                if (choiceButtonLabels != null && i < choiceButtonLabels.Length && choiceButtonLabels[i] != null)
                {
                    choiceButtonLabels[i].text = active ? currentChoices[i].label : "";
                }
            }

            if (adviceFooterText != null)
            {
                adviceFooterText.text = string.Format(
                    "현재 조건  호감도 {0} · {1} · 챕터 {2}까지 · 장면 {3} · {4} {5}개",
                    bondRank,
                    CurrentBandLabel(),
                    storyChapter,
                    CurrentScene().label,
                    AdviceCategoryLabel(selectedAdviceCategory),
                    currentChoices.Count);
            }

            ApplyAdviceTabVisual(adviceAllTabButton, AdviceCategory.All);
            ApplyAdviceTabVisual(adviceMissionTabButton, AdviceCategory.Mission);
            ApplyAdviceTabVisual(adviceDailyTabButton, AdviceCategory.Daily);
            ApplyAdviceTabVisual(adviceMemoryTabButton, AdviceCategory.Memory);
            ApplyAdviceTabVisual(adviceStoryTabButton, AdviceCategory.Story);
            ApplyAdviceTabVisual(adviceSpecialTabButton, AdviceCategory.Special);
        }

        private void ApplyAdviceTabVisual(Button button, AdviceCategory category)
        {
            if (button == null)
            {
                return;
            }

            Image image = button.GetComponent<Image>();
            if (image != null)
            {
                image.color = selectedAdviceCategory == category
                    ? new Color(0.08f, 0.62f, 0.94f, 0.98f)
                    : new Color(0.12f, 0.13f, 0.15f, 0.96f);
            }
        }

        private void ApplyChoice(DialogueChoice choice)
        {
            pendingChoice = choice;
            currentPayloadHasGift = false;
            currentSceneId = choice.sceneId;
            currentRecentAction = choice.actionId;
            currentQuery = choice.query;
            currentResultLabel = choice.resultLabel;
        }

        private void ApplyGiftPayload(GiftItem gift)
        {
            currentPayloadHasGift = true;
            currentGiftId = gift.id;
            currentGiftName = gift.displayName.Replace("♥ ", "");
            currentGiftCategory = GiftCategoryLabel(gift.category);
            currentGiftPreference = gift.preferenceLabel;
            currentGiftAffectionGain = gift.affectionGain;
        }

        private string BuildGiftQuery(GiftItem gift)
        {
            return string.Format(
                "선물하기 결과. 라피가 받은 선물은 '{0}'이고 분류는 '{1}', 선호도는 '{2}', 호감도 상승량은 {3}이다. " +
                "현재 호감도 {4}({5}), 스토리 챕터 {6}까지 허용된 RAG 카드만 근거로 이전 대사와 다른 짧은 한국어 반응을 생성한다. " +
                "최애 선물은 더 조용히 기뻐하고, 타 니케 선호 고급 선물은 고마워하되 라피 최애와 온도차를 둔다. 공용 보라/파란 선물은 실용적이고 담백하게 받는다.",
                gift.displayName.Replace("♥ ", ""),
                GiftCategoryLabel(gift.category),
                gift.preferenceLabel,
                gift.affectionGain,
                bondRank,
                CurrentBandLabel(),
                storyChapter);
        }

        private string GiftCategoryLabel(GiftCategory category)
        {
            switch (category)
            {
                case GiftCategory.Favorite:
                    return "favorite";
                case GiftCategory.Premium:
                    return "premium_other_preferred";
                case GiftCategory.Common:
                    return "common";
                default:
                    return "all";
            }
        }

        private string AdviceCategoryLabel(AdviceCategory category)
        {
            switch (category)
            {
                case AdviceCategory.Mission:
                    return "임무";
                case AdviceCategory.Daily:
                    return "일상";
                case AdviceCategory.Memory:
                    return "기억";
                case AdviceCategory.Story:
                    return "스토리";
                case AdviceCategory.Special:
                    return "특별";
                default:
                    return "전체";
            }
        }

        private void RequestDialogue(string loadingText)
        {
            if (!isRequesting)
            {
                dialogueRequest = StartCoroutine(PostDialogue(loadingText));
            }
        }

        private IEnumerator PostDialogue(string loadingText)
        {
            isRequesting = true;
            try
            {
            SetButtonsInteractable(false);
            SetStatus(loadingText);
            SetRisk("검색 중");

            DialogueGenerateRequest payload = BuildPayload();
            string json = JsonUtility.ToJson(payload);

            using (UnityWebRequest request = new UnityWebRequest(endpoint, "POST"))
            {
                activeRequest = request;
                request.timeout = Mathf.Max(1, requestTimeoutSeconds);
                byte[] body = Encoding.UTF8.GetBytes(json);
                request.uploadHandler = new UploadHandlerRaw(body);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string message = RequestError(request);
                    SetStatus("대사 요청 실패");
                    SetLine(message);
                    SetRisk("연결 끊김");
                }
                else
                {
                    HandleResponse(request.downloadHandler.text);
                }
            }
            }
            finally
            {
                activeRequest = null;
                dialogueRequest = null;
                ResetRequestState();
            }
        }

        private void ResetRequestState()
        {
            isRequesting = false;
            SetButtonsInteractable(true);
            ApplyGiftButtons();
        }

        private void OnDisable()
        {
            if (activeRequest != null) activeRequest.Abort();
            if (dialogueRequest != null) StopCoroutine(dialogueRequest);
            dialogueRequest = null;
            activeRequest = null;
            ResetRequestState();
        }

        [Serializable]
        private class ApiError { public string detail; }

        private static string RequestError(UnityWebRequest request)
        {
            string message;
            switch (request.responseCode)
            {
                case 404: message = "현재 조건에 맞는 대사 카드가 없습니다."; break;
                case 422: message = "요청 상태를 확인해 주세요."; break;
                case 502: message = "모델 서버에 연결하지 못했습니다. Ollama 실행 상태를 확인해 주세요."; break;
                default:
                    message = request.error != null && request.error.IndexOf("tim", StringComparison.OrdinalIgnoreCase) >= 0
                        ? "응답 대기 시간이 초과되었습니다. 다시 시도해 주세요."
                        : "로컬 대사 서버에 연결하지 못했습니다. 서버 실행 상태를 확인해 주세요.";
                    break;
            }
            if (request.downloadHandler != null)
            {
                try
                {
                    var error = JsonUtility.FromJson<ApiError>(request.downloadHandler.text);
                    if (error != null && !string.IsNullOrWhiteSpace(error.detail)) message += "\n" + error.detail;
                }
                catch (ArgumentException) { }
            }
            return message;
        }

        private DialogueGenerateRequest BuildPayload()
        {
            DialogueState state = new DialogueState
            {
                character_id = "rapi",
                affection = CurrentAffection(),
                affection_band = CurrentBandId(),
                bond_rank = bondRank,
                bond_exp = CurrentBondExp(),
                bond_cap = CurrentBondCap(),
                limit_break = CurrentLimitBreak(),
                daily_advise_remaining = CurrentDailyAdviseRemaining(),
                quick_advise_unlocked = CurrentQuickAdviseUnlocked(),
                advise_seen_count = CurrentAdviseSeenCount(),
                advise_collection_count = CurrentAdviseCollectionCount(),
                story_flags = BuildStoryFlags(),
                scene = currentSceneId,
                player_recent_action = currentRecentAction,
                interaction_type = currentPayloadHasGift ? "gift" : "advice",
                time_of_day = DateTime.Now.Hour < 12 ? "morning" : "evening",
                place = "outpost_lobby",
                recent_lines = recentLines.ToArray(),
                recent_card_ids = recentCardIds.ToArray(),
                tone = "subculture_romantic_but_wholesome",
                max_spoiler_level = CurrentMaxSpoilerLevel(),
                output_language = "ko",
                gift_context_active = currentPayloadHasGift,
                gift_id = currentPayloadHasGift ? currentGiftId : null,
                gift_name = currentPayloadHasGift ? currentGiftName : null,
                gift_category = currentPayloadHasGift ? currentGiftCategory : null,
                gift_preference = currentPayloadHasGift ? currentGiftPreference : null,
                gift_affection_gain = currentPayloadHasGift ? currentGiftAffectionGain : 0,
                gift_type = CurrentGiftType(),
                gift_rarity = CurrentGiftRarity(),
                gift_match_type = CurrentGiftMatchType(),
                favorite_item_phase = CurrentFavoriteItemPhase(),
                collection_item_phase = CurrentCollectionItemPhase()
            };

            return new DialogueGenerateRequest
            {
                state = state,
                query = currentQuery,
                limit = 5,
                temperature = 0.72f,
                accept_cache = false,
                include_cards = false
            };
        }

        private void HandleResponse(string json)
        {
            DialogueGenerateResponse response;
            try { response = JsonUtility.FromJson<DialogueGenerateResponse>(json); }
            catch (ArgumentException)
            {
                SetStatus("응답 형식 오류");
                SetLine("대사 서버가 올바른 JSON 응답을 보내지 않았습니다. 다시 시도해 주세요.");
                SetRisk("검수 필요");
                return;
            }
            if (response == null || response.output == null || string.IsNullOrWhiteSpace(response.output.line))
            {
                SetStatus("응답 확인 실패");
                SetLine("대사 응답을 읽지 못했습니다.");
                SetRisk("검수 필요");
                return;
            }

            string line = response.output.line.Trim();
            SetLine(line);
            SetStatus(ToKoreanVoiceTag(response.output.voice_tag) + " / " + ToKoreanMotion(response.output.motion));
            SetRisk(ToKoreanRisk(response.output.risk));
            SetMode(currentResultLabel);

            if (characterAnimator != null)
            {
                characterAnimator.ApplyTags(response.output.emotion, response.output.motion);
            }

            recentLines.Add(line);
            while (recentLines.Count > 20)
            {
                recentLines.RemoveAt(0);
            }

            if (response.retrieved_card_ids != null)
            {
                foreach (string cardId in response.retrieved_card_ids)
                {
                    if (!string.IsNullOrEmpty(cardId))
                    {
                        recentCardIds.Add(cardId);
                    }
                }
                while (recentCardIds.Count > 10)
                {
                    recentCardIds.RemoveAt(0);
                }
            }
        }

        private int CurrentAffection()
        {
            return Mathf.Clamp(Mathf.RoundToInt(bondRank / 30f * 100f), 1, 100);
        }

        private int CurrentBondExp()
        {
            return Mathf.Clamp(bondRank * 100, 0, CurrentBondCap() * 100);
        }

        private int CurrentBondCap()
        {
            int limitBreak = CurrentLimitBreak();
            if (limitBreak <= 0)
            {
                return 10;
            }

            if (limitBreak == 1)
            {
                return 20;
            }

            return 30;
        }

        private int CurrentLimitBreak()
        {
            if (bondRank >= 30)
            {
                return 3;
            }

            if (bondRank > 20)
            {
                return 2;
            }

            if (bondRank > 10)
            {
                return 1;
            }

            return 0;
        }

        private int CurrentDailyAdviseRemaining()
        {
            int dailyLimit = CurrentQuickAdviseUnlocked() ? 3 : 1;
            bool hasPendingAdvice = !currentPayloadHasGift && !string.IsNullOrEmpty(currentRecentAction) && currentRecentAction.StartsWith("advise_choice");
            int consumedByPendingAdvice = hasPendingAdvice ? 1 : 0;
            return Mathf.Clamp(dailyLimit - consumedByPendingAdvice, 0, dailyLimit);
        }

        private bool CurrentQuickAdviseUnlocked()
        {
            return bondRank >= 10 || storyChapter >= 3;
        }

        private int CurrentAdviseSeenCount()
        {
            int count = 0;
            if (bondRank >= 6)
            {
                count += 1;
            }

            if (bondRank >= 10)
            {
                count += 1;
            }

            if (bondRank >= 15)
            {
                count += 2;
            }

            if (bondRank >= 18 && storyChapter >= 4)
            {
                count += 1;
            }

            if (bondRank >= 25)
            {
                count += 2;
            }

            if (!currentPayloadHasGift && !string.IsNullOrEmpty(currentRecentAction) && currentRecentAction.StartsWith("advise_choice"))
            {
                count += 1;
            }

            return Mathf.Clamp(count, 0, CurrentAdviseCollectionCount());
        }

        private int CurrentAdviseCollectionCount()
        {
            int count = 3;
            if (bondRank >= 6 && storyChapter >= 2)
            {
                count += 2;
            }

            if (bondRank >= 10 && storyChapter >= 2)
            {
                count += 1;
            }

            if (bondRank >= 15 && storyChapter >= 3)
            {
                count += 2;
            }

            if (bondRank >= 18 && storyChapter >= 4)
            {
                count += 1;
            }

            if (storyChapter >= 3)
            {
                count += 1;
            }

            if (storyChapter >= 3 && bondRank >= 12)
            {
                count += 1;
            }

            if (storyChapter >= 4 && bondRank >= 18)
            {
                count += 1;
            }

            if (storyChapter >= 5 && bondRank >= 15)
            {
                count += 1;
            }

            if (bondRank >= 25)
            {
                count += 2;
            }

            if (storyChapter >= 34 && bondRank >= 20)
            {
                count += 1;
            }

            if (storyChapter >= 46 && bondRank >= 20)
            {
                count += 1;
            }

            return count;
        }

        private string CurrentGiftType()
        {
            if (!currentPayloadHasGift)
            {
                return "none";
            }

            switch (currentGiftCategory)
            {
                case "favorite":
                    return "favorite_item";
                case "premium_other_preferred":
                    return "premium_item";
                case "common":
                    return "common_item";
                default:
                    return "unknown_item";
            }
        }

        private string CurrentGiftRarity()
        {
            if (!currentPayloadHasGift)
            {
                return "none";
            }

            if (currentGiftCategory == "favorite")
            {
                return "favorite";
            }

            if (currentGiftCategory == "premium_other_preferred")
            {
                return "sr";
            }

            if (!string.IsNullOrEmpty(currentGiftId) && currentGiftId.Contains("purple"))
            {
                return "sr";
            }

            if (!string.IsNullOrEmpty(currentGiftId) && currentGiftId.Contains("blue"))
            {
                return "r";
            }

            return "r";
        }

        private string CurrentGiftMatchType()
        {
            if (!currentPayloadHasGift)
            {
                return "none";
            }

            return GiftMatchTypeForCategory(currentGiftCategory);
        }

        private string GiftMatchTypeForCategory(GiftCategory category)
        {
            return GiftMatchTypeForCategory(GiftCategoryLabel(category));
        }

        private string GiftMatchTypeForCategory(string category)
        {
            switch (category)
            {
                case "favorite":
                    return "favorite_match";
                case "premium_other_preferred":
                    return "preferred_but_not_favorite";
                case "common":
                    return "neutral_match";
                default:
                    return "none";
            }
        }

        private string CurrentFavoriteItemPhase()
        {
            if (currentPayloadHasGift && CurrentGiftMatchType() == "favorite_match")
            {
                return "favorite_received";
            }

            if (bondRank >= 30)
            {
                return "max_bond";
            }

            if (bondRank >= 15)
            {
                return "preference_known";
            }

            if (bondRank >= 6)
            {
                return "preference_hint";
            }

            return "locked";
        }

        private string CurrentCollectionItemPhase()
        {
            if (bondRank >= 30 && storyChapter >= 34)
            {
                return "variant_memory_unlocked";
            }

            if (bondRank >= 25)
            {
                return "bond_episode_03";
            }

            if (bondRank >= 15)
            {
                return "bond_episode_02";
            }

            if (bondRank >= 10)
            {
                return "bond_episode_01";
            }

            if (bondRank >= 6)
            {
                return "first_advise";
            }

            return "locked";
        }

        private string CurrentBandId()
        {
            if (bondRank <= 5)
            {
                return "cautious";
            }

            if (bondRank <= 14)
            {
                return "friendly";
            }

            if (bondRank <= 24)
            {
                return "trust";
            }

            return "special_trust";
        }

        private string CurrentBandLabel()
        {
            switch (CurrentBandId())
            {
                case "cautious":
                    return "조심스러움";
                case "friendly":
                    return "친근함";
                case "trust":
                    return "신뢰";
                default:
                    return "특별한 신뢰";
            }
        }

        private int CurrentMaxSpoilerLevel()
        {
            if (storyChapter >= 26)
            {
                return 5;
            }

            if (storyChapter >= 13)
            {
                return 4;
            }

            if (storyChapter >= 10)
            {
                return 3;
            }

            if (storyChapter >= 4 || bondRank >= 25)
            {
                return 2;
            }

            if (storyChapter >= 3)
            {
                return 1;
            }

            return 0;
        }

        private string[] BuildStoryFlags()
        {
            List<string> flags = new List<string>();
            for (int chapter = 1; chapter <= storyChapter; chapter++)
            {
                flags.Add(string.Format("chapter_{0:00}_cleared", chapter));
            }

            if (bondRank >= 6)
            {
                flags.Add("first_advise_seen");
            }

            if (bondRank >= 10)
            {
                flags.Add("favorite_gift_received");
                flags.Add("bond_episode_01_seen");
            }

            if (bondRank >= 25)
            {
                flags.Add("bond_episode_03_seen");
            }

            if (storyChapter >= 3)
            {
                flags.Add("chapter_03_rapi_repair_nikke_body_seen");
            }

            if (storyChapter >= 4)
            {
                flags.Add("chapter_04_red_hood_hint_seen");
            }

            if (storyChapter >= 10)
            {
                flags.Add("chapter_10_memory_wipe_anomaly_seen");
            }

            if (storyChapter >= 11)
            {
                flags.Add("chapter_11_absolute_past_seen");
            }

            if (storyChapter >= 13)
            {
                flags.Add("chapter_13_code_red_hood_activation_seen");
            }

            if (storyChapter >= 24)
            {
                flags.Add("chapter_24_red_hood_takeover_seen");
            }

            if (storyChapter >= 26)
            {
                flags.Add("chapter_26_red_hood_truth_known");
                flags.Add("rapi_core_secret_unlocked");
            }

            if (storyChapter >= 32)
            {
                flags.Add("chapter_32_behemoth_defeat_seen");
            }

            if (storyChapter >= 34)
            {
                flags.Add("chapter_34_rapi_inheritance_seen");
                flags.Add("character_variant_rapi_red_hood_unlocked");
            }

            if (storyChapter >= 36)
            {
                flags.Add("chapter_36_post_inheritance_state_seen");
            }

            if (storyChapter >= 38)
            {
                flags.Add("chapter_38_four_beasts_pursuit_seen");
            }

            if (storyChapter >= 40)
            {
                flags.Add("chapter_40_nayuta_dual_core_seen");
            }

            if (storyChapter >= 46)
            {
                flags.Add("chapter_46_dorothy_doban_aftermath_seen");
            }

            return flags.ToArray();
        }

        private ScenePreset CurrentScene()
        {
            if (selectedSceneIndex < 0 || selectedSceneIndex >= scenePresets.Length)
            {
                selectedSceneIndex = 1;
            }

            return scenePresets[selectedSceneIndex];
        }

        private void RefreshStateUi()
        {
            string bandLabel = CurrentBandLabel();
            if (rankText != null)
            {
                rankText.text = string.Format("Bond {0}/{1}", bondRank, CurrentBondCap());
            }

            if (stateSummaryText != null)
            {
                stateSummaryText.text = string.Format("{0}  LB{1}  EXP {2}", bandLabel, CurrentLimitBreak(), CurrentBondExp());
            }

            if (storyProgressText != null)
            {
                storyProgressText.text = "스토리 챕터 " + storyChapter + "까지";
            }

            if (sceneText != null)
            {
                sceneText.text = "장면 " + CurrentScene().label;
            }

            if (nextEpisodeText != null)
            {
                nextEpisodeText.text = NextEpisodeText();
            }

            if (giftOverlay != null && giftOverlay.activeSelf)
            {
                RefreshGiftHeader();
            }
        }

        private string NextEpisodeText()
        {
            if (bondRank < 6)
            {
                return "Next advise R6 / Daily " + CurrentDailyAdviseRemaining();
            }

            if (bondRank < 15)
            {
                return "Memory advise R15 / Daily " + CurrentDailyAdviseRemaining();
            }

            if (bondRank < 25)
            {
                return "Special advise R25 / Daily " + CurrentDailyAdviseRemaining();
            }

            return string.Format("Advise {0}/{1} / Daily {2}", CurrentAdviseSeenCount(), CurrentAdviseCollectionCount(), CurrentDailyAdviseRemaining());
        }

        private void SetIdleCopy()
        {
            if (speakerText != null)
            {
                speakerText.text = "라피";
            }

            SetMode("호감도 화면");
            SetLine("지휘관, 오늘은 어떤 일부터 확인할까요?");
            SetStatus("선물하기 또는 상담하기를 선택해 주세요.");
            SetRisk("대기 중");
        }

        private void SetMode(string text)
        {
            if (modeText != null)
            {
                modeText.text = text;
            }
        }

        private void SetLine(string text)
        {
            if (lineText != null)
            {
                lineText.text = text;
            }
        }

        private void SetStatus(string text)
        {
            if (statusText != null)
            {
                statusText.text = text;
            }
        }

        private void SetRisk(string text)
        {
            if (riskText != null)
            {
                riskText.text = text;
            }
        }

        private void SetButtonsInteractable(bool value)
        {
            if (giftButton != null)
            {
                giftButton.interactable = value;
            }

            if (adviseButton != null)
            {
                adviseButton.interactable = value;
            }

            SetButton(choiceButtons, value);
            SetButton(rankDownButton, value);
            SetButton(rankUpButton, value);
            SetButton(chapterDownButton, value);
            SetButton(chapterUpButton, value);
            SetButton(scenePrevButton, value);
            SetButton(sceneNextButton, value);
            SetButton(adviceAllTabButton, value);
            SetButton(adviceMissionTabButton, value);
            SetButton(adviceDailyTabButton, value);
            SetButton(adviceMemoryTabButton, value);
            SetButton(adviceStoryTabButton, value);
            SetButton(adviceSpecialTabButton, value);
            SetButton(closeGiftButton, value);
            SetButton(giftAllTabButton, value);
            SetButton(giftFavoriteTabButton, value);
            SetButton(giftPremiumTabButton, value);
            SetButton(giftCommonTabButton, value);
            SetButton(giftItemButtons, value);
            SetButton(giftConfirmButton, value && selectedGiftIndex >= 0);
        }

        private void SetButton(Button[] buttons, bool value)
        {
            if (buttons == null)
            {
                return;
            }

            for (int i = 0; i < buttons.Length; i++)
            {
                SetButton(buttons[i], value);
            }
        }

        private void SetButton(Button button, bool value)
        {
            if (button != null)
            {
                button.interactable = value;
            }
        }

        private string ToKoreanVoiceTag(string value)
        {
            switch (value)
            {
                case "calm_brief":
                    return "차분하고 짧음";
                case "warm_reserved":
                    return "따뜻하지만 절제됨";
                case "mission_report":
                    return "임무 보고";
                case "protective_soft":
                    return "조용한 보호";
                case "rare_tease":
                    return "드문 장난기";
                case "vulnerable_short":
                    return "짧은 속마음";
                case "legacy_resolved":
                    return "계승을 받아들임";
                case "direct_affection":
                    return "직접적인 애정";
                case "red_hood_combat":
                    return "레드 후드 전투";
                case "event_flirt":
                    return "이벤트 호감";
                case "event_comedy_direct":
                    return "이벤트 직진";
                default:
                    return "기본 말투";
            }
        }

        private string ToKoreanMotion(string value)
        {
            switch (value)
            {
                case "nod":
                    return "작게 끄덕임";
                case "look_away":
                    return "시선 회피";
                case "soft_smile":
                    return "옅은 미소";
                case "salute":
                    return "보고 자세";
                case "hand_to_chest":
                    return "가슴에 손";
                case "battle_ready":
                    return "전투 준비";
                default:
                    return "기본 대기";
            }
        }

        private string ToKoreanRisk(string value)
        {
            switch (value)
            {
                case "safe":
                    return "안전";
                case "needs_review":
                    return "검수 필요";
                case "blocked":
                    return "차단";
                case "offline":
                    return "연결 끊김";
                default:
                    return "대기 중";
            }
        }

        private enum AdviceCategory
        {
            All,
            Mission,
            Daily,
            Memory,
            Story,
            Special
        }

        private enum GiftCategory
        {
            All,
            Favorite,
            Premium,
            Common
        }

        private struct GiftItem
        {
            public readonly string id;
            public readonly string displayName;
            public readonly GiftCategory category;
            public readonly string metaLabel;
            public readonly string preferenceLabel;
            public readonly int affectionGain;
            public readonly int rankDelta;
            public readonly string actionId;
            public readonly string resultLabel;
            public readonly Color uiColor;

            public GiftItem(
                string id,
                string displayName,
                GiftCategory category,
                string metaLabel,
                string preferenceLabel,
                int affectionGain,
                int rankDelta,
                string actionId,
                string resultLabel,
                Color uiColor)
            {
                this.id = id;
                this.displayName = displayName;
                this.category = category;
                this.metaLabel = metaLabel;
                this.preferenceLabel = preferenceLabel;
                this.affectionGain = affectionGain;
                this.rankDelta = rankDelta;
                this.actionId = actionId;
                this.resultLabel = resultLabel;
                this.uiColor = uiColor;
            }
        }

        private struct ScenePreset
        {
            public readonly string id;
            public readonly string label;

            public ScenePreset(string id, string label)
            {
                this.id = id;
                this.label = label;
            }
        }

        private struct DialogueChoice
        {
            public string label;
            public string resultLabel;
            public AdviceCategory category;
            public string sceneId;
            public string actionId;
            public string query;
        }

        [Serializable]
        public class DialogueGenerateRequest
        {
            public DialogueState state;
            public string query;
            public int limit;
            public float temperature;
            public bool accept_cache;
            public bool include_cards;
        }

        [Serializable]
        public class DialogueState
        {
            public string character_id;
            public int affection;
            public string affection_band;
            public int bond_rank;
            public int bond_exp;
            public int bond_cap;
            public int limit_break;
            public int daily_advise_remaining;
            public bool quick_advise_unlocked;
            public int advise_seen_count;
            public int advise_collection_count;
            public string[] story_flags;
            public string scene;
            public string player_recent_action;
            public string interaction_type;
            public string time_of_day;
            public string place;
            public string[] recent_lines;
            public string[] recent_card_ids;
            public string tone;
            public int max_spoiler_level;
            public string output_language;
            public bool gift_context_active;
            public string gift_id;
            public string gift_name;
            public string gift_category;
            public string gift_preference;
            public int gift_affection_gain;
            public string gift_type;
            public string gift_rarity;
            public string gift_match_type;
            public string favorite_item_phase;
            public string collection_item_phase;
        }

        [Serializable]
        public class DialogueGenerateResponse
        {
            public string generated_id;
            public string[] retrieved_card_ids;
            public DialogueOutput output;
        }

        [Serializable]
        public class DialogueOutput
        {
            public string line;
            public string emotion;
            public string voice_tag;
            public string motion;
            public string risk;
        }
    }
}
