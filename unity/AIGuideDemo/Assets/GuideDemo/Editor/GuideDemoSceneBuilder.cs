using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Events;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;
using AIGuide;
using TMPro;

namespace AIGuide.Demo.EditorTools
{
    public static class GuideDemoSceneBuilder
    {
        const string Root = "Assets/GuideDemo";
        const string DataDir = Root + "/Data";
        const string PrefabDir = Root + "/Prefabs";
        static string PackDir => Path.Combine(System.Environment.GetEnvironmentVariable("AIGD_ROOT")
            ?? Path.GetFullPath(Path.Combine(Application.dataPath, "../../..")), "data");
        static readonly (string key, string file, string scene)[] Packs =
        {
            ("Nikke", "pack_nikke.json", Root + "/Scenes/AIGuideDemo_Nikke.unity"),
            ("BlueArchive", "pack_bluearchive.json", Root + "/Scenes/AIGuideDemo_BlueArchive.unity"),
            ("Trickcal", "pack_trickcal.json", Root + "/Scenes/AIGuideDemo_Trickcal.unity"),
        };
        const string RapiPrefabSource = "Assets/RapiRAGDemo/Prefabs/RapiLobbyCharacter.prefab";
        const string FontPath = "Assets/RapiRAGDemo/Fonts/Pretendard-Regular.otf";
        const string ParticleSprites = "Assets/AssetKits/ParticleImage/Demo/Sprites";
        const string StepTitlePrefab = "Assets/Motion Titles Pack/Prefabs/15.prefab";

        static Font _font;

        [MenuItem("AIGuide/Build Demo Scene")]
        public static void Build()
        {
            foreach (var p in Packs) BuildFor(p.key);
            var list = new List<EditorBuildSettingsScene>();
            foreach (var p in Packs) list.Add(new EditorBuildSettingsScene(p.scene, true));
            EditorBuildSettings.scenes = list.ToArray();
        }

        [MenuItem("AIGuide/Build Demo Scene (Nikke only)")]
        public static void BuildNikke() => BuildFor("Nikke");

        static string _buildKey;
        static List<Image> _thPanels = new List<Image>(), _thButtons = new List<Image>(), _thShapeOnly = new List<Image>(), _thAccents = new List<Image>();
        const string UiShapes = Root + "/Art/ui";

        public static void BuildFor(string key)
        {
            var spec = System.Array.Find(Packs, p => p.key == key);
            _buildKey = key;
            foreach (var d in new[] { Root, DataDir, PrefabDir, Root + "/Scenes" })
                if (!AssetDatabase.IsValidFolder(d)) Directory.CreateDirectory(d);
            AssetDatabase.Refresh();
            _font = AssetDatabase.LoadAssetAtPath<Font>(FontPath) ?? Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");

            var pack = CreatePack(spec.key, spec.file);
            var rapi = CreateRapiProfile();
            var arona = CreateAronaProfile();
            var ner = CreateNerProfile();
            foreach (var profile in new[] { rapi, arona, ner })
            {
                string storyPath = Path.Combine(PackDir, "characters", profile.serverCharacterId, "story.json");
                var story = JsonUtility.FromJson<CharacterStory>(File.ReadAllText(storyPath));
                profile.storyChapters = new List<StoryChapter>(story.chapters);
                string questionsPath = Path.Combine(PackDir, "characters", profile.serverCharacterId, "suggestions.json");
                var bank = JsonUtility.FromJson<GuideQuestionBank>(File.ReadAllText(questionsPath));
                profile.suggestions = bank;
                EditorUtility.SetDirty(profile);
            }
            AssignSprites(rapi, Root + "/Art/rapi");
            AssignSprites(arona, Root + "/Art/arona");
            AssignSprites(ner, Root + "/Art/ner");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            BuildWorld(out Transform avatarAnchor);
            BuildUi(pack, new List<GuideCharacterProfile> { rapi, arona, ner }, avatarAnchor);
            EditorSceneManager.SaveScene(scene, spec.scene);
            AssetDatabase.SaveAssets();
            Debug.Log("[AIGuide] 데모 씬을 만들었습니다: " + spec.scene);
        }

        static GuideGamePack CreatePack(string key, string file)
        {
            string dst = DataDir + "/" + file;
            string src = Path.Combine(PackDir, file);
            if (File.Exists(src)) File.Copy(src, dst, true);
            AssetDatabase.ImportAsset(dst);
            var pack = LoadOrCreate<GuideGamePack>(DataDir + "/GuidePack_" + key + ".asset");
            pack.packJson = AssetDatabase.LoadAssetAtPath<TextAsset>(dst);
            EditorUtility.SetDirty(pack);
            return pack;
        }

        static GuideCharacterProfile CreateRapiProfile()
        {
            var p = LoadOrCreate<GuideCharacterProfile>(DataDir + "/GuideCharacter_Rapi.asset");
            p.homeScene = "AIGuideDemo_Nikke";
            p.serverCharacterId = "rapi"; p.displayName = "라피"; p.addressTerm = "지휘관"; p.modelKey = "adapter";
            p.nameColor = new Color(1f, 0.3f, 0.3f);
            Theme(p, "bg_rapi.png", "Cutout - 200ppu.png", "Cutout - 200ppu.png", 2.5f, 0.40f,
                  new Color(0.03f, 0.05f, 0.09f, 0.78f), new Color(0.10f, 0.16f, 0.26f, 0.92f), new Color(0.80f, 0.20f, 0.22f, 1f));
            p.highlightShape = null;
            p.avatarPrefab = MakeAvatarFromExisting(RapiPrefabSource, PrefabDir + "/GuideAvatar_Rapi.prefab");
            p.avatarPosition = new Vector3(1.15f, 0f, 0.25f);
            p.avatarEuler = Vector3.zero;
            p.emotions = new List<EmotionBinding>
            {
                new EmotionBinding { tag = "soft_smile", blendShapeKeywords = new[] { "smile", "笑", "にこ" }, weight = 35 },
                new EmotionBinding { tag = "gentle", blendShapeKeywords = new[] { "smile", "笑" }, weight = 25 },
                new EmotionBinding { tag = "embarrassed", blendShapeKeywords = new[] { "blush", "照", "赤" }, weight = 45 },
                new EmotionBinding { tag = "worried", blendShapeKeywords = new[] { "sad", "worry", "困", "不安" }, weight = 40 },
                new EmotionBinding { tag = "stern", blendShapeKeywords = new[] { "angry", "serious", "怒", "きり" }, weight = 30 },
                new EmotionBinding { tag = "relieved", blendShapeKeywords = new[] { "smile", "笑" }, weight = 20 },
            };
            p.motions = new List<MotionBinding>();
            p.thinkingLines = new List<string> { "확인하겠습니다.", "잠시만 기다려 주십시오, {address}.", "상황을 보겠습니다." };
            p.errorLines = new List<string> { "{address}, 지금은 통신이 원활하지 않습니다. 다시 말씀해 주십시오." };
            p.targetMissingLines = new List<string> { "{address}, 표시할 위치를 지금 화면에서 찾지 못했습니다. 로비로 돌아가 주십시오." };
            EditorUtility.SetDirty(p);
            return p;
        }

        static GuideCharacterProfile CreateAronaProfile()
        {
            var p = LoadOrCreate<GuideCharacterProfile>(DataDir + "/GuideCharacter_Arona.asset");
            p.homeScene = "AIGuideDemo_BlueArchive";
            p.serverCharacterId = "arona"; p.displayName = "아로나"; p.addressTerm = "선생님"; p.modelKey = "adapter";
            p.nameColor = new Color(0.35f, 0.8f, 1f);
            Theme(p, "bg_arona.png", "Rounded - 200ppu.png", "Rounded - 200ppu.png", 3f, 0.30f,
                  new Color(0.05f, 0.10f, 0.20f, 0.72f), new Color(0.16f, 0.40f, 0.70f, 0.92f), new Color(0.25f, 0.70f, 1f, 1f));
            p.highlightShape = AssetDatabase.LoadAssetAtPath<Sprite>(UiShapes + "/Semi Rounded - Outline - 6px - 300ppu.png");
            p.avatarPrefab = MakePlaceholderAvatar(PrefabDir + "/GuideAvatar_Placeholder.prefab");
            p.avatarPosition = new Vector3(1.15f, 0f, 0.25f);
            p.thinkingLines = new List<string> { "잠깐만요, 확인해 볼게요!", "{address}, 조금만 기다려 주세요!" };
            p.errorLines = new List<string> { "어라? 연결이 잘 안 되고 있어요. {address}, 한 번만 더 말씀해 주세요!" };
            p.targetMissingLines = new List<string> { "{address}, 그 버튼은 지금 화면에 없어요. 로비로 돌아가 볼까요?" };
            EditorUtility.SetDirty(p);
            return p;
        }

        static GuideCharacterProfile CreateNerProfile()
        {
            var p = LoadOrCreate<GuideCharacterProfile>(DataDir + "/GuideCharacter_Ner.asset");
            p.homeScene = "AIGuideDemo_Trickcal";
            p.serverCharacterId = "ner"; p.displayName = "네르"; p.addressTerm = "교주님"; p.modelKey = "adapter";
            p.nameColor = new Color(0.55f, 0.85f, 0.45f);
            Theme(p, "bg_ner.png", "Rounded - 200ppu.png", "Rounded - 200ppu.png", 2.5f, 0.25f,
                  new Color(0.08f, 0.13f, 0.08f, 0.72f), new Color(0.30f, 0.50f, 0.22f, 0.92f), new Color(0.90f, 0.66f, 0.20f, 1f));
            p.highlightShape = AssetDatabase.LoadAssetAtPath<Sprite>(UiShapes + "/Semi Rounded - Outline - 6px - 300ppu.png");
            p.avatarPrefab = MakePlaceholderAvatar(PrefabDir + "/GuideAvatar_Placeholder.prefab");
            p.avatarPosition = new Vector3(1.15f, 0f, 0.25f);
            p.thinkingLines = new List<string> { "잠시만요, 확인해 볼게요.", "{address}, 서류를 찾아볼게요." };
            p.errorLines = new List<string> { "{address}, 지금은 연결이 좋지 않네요. 한 번만 더 말씀해 주세요." };
            p.targetMissingLines = new List<string> { "{address}, 그 버튼은 지금 화면에 없어요. 로비로 돌아가 볼까요?" };
            EditorUtility.SetDirty(p);
            return p;
        }

        static GameObject MakeAvatarFromExisting(string sourcePrefab, string dst)
        {
            var src = AssetDatabase.LoadAssetAtPath<GameObject>(sourcePrefab);
            if (src == null) { Debug.LogWarning("[AIGuide] 원본 캐릭터 프리팹이 없습니다: " + sourcePrefab); return MakePlaceholderAvatar(dst); }
            var go = (GameObject)Object.Instantiate(src);
            go.name = Path.GetFileNameWithoutExtension(dst);
            foreach (var mb in go.GetComponentsInChildren<MonoBehaviour>(true)) Object.DestroyImmediate(mb);
            foreach (var c in go.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
            var accent = go.transform.Find("Rapi_Base_RedAccent");
            if (accent != null) Object.DestroyImmediate(accent.gameObject);
            go.transform.position = Vector3.zero;
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, dst);
            Object.DestroyImmediate(go);
            return prefab;
        }

        static GameObject MakePlaceholderAvatar(string dst)
        {
            var existing = AssetDatabase.LoadAssetAtPath<GameObject>(dst);
            if (existing != null) return existing;
            var root = new GameObject("GuideAvatar_Placeholder");
            var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            body.transform.SetParent(root.transform, false);
            body.transform.localPosition = new Vector3(0, 2.6f, 0);
            body.transform.localScale = new Vector3(0.9f, 1.3f, 0.9f);
            Object.DestroyImmediate(body.GetComponent<Collider>());
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, dst);
            Object.DestroyImmediate(root);
            return prefab;
        }

        [MenuItem("AIGuide/Assign Character Sprites")]
        public static void AssignAll()
        {
            var r = AssetDatabase.LoadAssetAtPath<GuideCharacterProfile>(DataDir + "/GuideCharacter_Rapi.asset");
            var a = AssetDatabase.LoadAssetAtPath<GuideCharacterProfile>(DataDir + "/GuideCharacter_Arona.asset");
            if (r) AssignSprites(r, Root + "/Art/rapi");
            if (a) AssignSprites(a, Root + "/Art/arona");
            var n = AssetDatabase.LoadAssetAtPath<GuideCharacterProfile>(DataDir + "/GuideCharacter_Ner.asset");
            if (n) AssignSprites(n, Root + "/Art/ner");
            AssetDatabase.SaveAssets();
        }

        static void AssignSprites(GuideCharacterProfile p, string folder)
        {
            if (!AssetDatabase.IsValidFolder(folder)) { Directory.CreateDirectory(folder); AssetDatabase.Refresh(); return; }
            p.poseSprites.Clear(); p.faceSprites.Clear(); p.fullSprites.Clear(); p.blinkFace = null; p.talkMouthOpen = null;
            int n = 0;
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { folder }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                var imp = (TextureImporter)AssetImporter.GetAtPath(path);
                if (imp.textureType != TextureImporterType.Sprite || imp.spriteImportMode != SpriteImportMode.Single)
                {
                    imp.textureType = TextureImporterType.Sprite; imp.spriteImportMode = SpriteImportMode.Single;
                    imp.mipmapEnabled = false; imp.alphaIsTransparency = true; imp.SaveAndReimport();
                }
                var sp = AssetDatabase.LoadAssetAtPath<Sprite>(path);
                string name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
                if (name.StartsWith("pose_")) p.poseSprites.Add(new SpriteBinding { key = name.Substring(5), sprite = sp });
                else if (name.StartsWith("face_")) p.faceSprites.Add(new SpriteBinding { key = name.Substring(5), sprite = sp });
                else if (name.StartsWith("full_")) p.fullSprites.Add(new SpriteBinding { key = name.Substring(5), sprite = sp });
                else if (name == "blink") p.blinkFace = sp;
                else if (name == "mouth_open") p.talkMouthOpen = sp;
                else continue;
                n++;
            }
            EditorUtility.SetDirty(p);
            Debug.Log($"[AIGuide] {p.displayName} 이미지 {n}장 연결 ({folder})");
        }

        static void Theme(GuideCharacterProfile p, string bg, string panel, string button, float scale, float dim, Color panelColor, Color buttonColor, Color accent)
        {
            var bgPath = Root + "/Art/bg/" + bg;
            var imp = AssetImporter.GetAtPath(bgPath) as TextureImporter;
            if (imp != null && (imp.textureType != TextureImporterType.Sprite || imp.spriteImportMode != SpriteImportMode.Single))
            {
                imp.textureType = TextureImporterType.Sprite; imp.spriteImportMode = SpriteImportMode.Single; imp.mipmapEnabled = false; imp.SaveAndReimport();
            }
            p.background = AssetDatabase.LoadAssetAtPath<Sprite>(bgPath);
            p.panelShape = AssetDatabase.LoadAssetAtPath<Sprite>(UiShapes + "/" + panel);
            p.buttonShape = AssetDatabase.LoadAssetAtPath<Sprite>(UiShapes + "/" + button);
            p.shapeScale = scale; p.backgroundDim = dim;
            p.panelColor = panelColor; p.buttonColor = buttonColor; p.accentColor = accent;
        }

        static T LoadOrCreate<T>(string path) where T : ScriptableObject
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            if (a != null) return a;
            a = ScriptableObject.CreateInstance<T>();
            AssetDatabase.CreateAsset(a, path);
            return a;
        }

        static void BuildWorld(out Transform avatarAnchor)
        {
            var cam = new GameObject("Main Camera");
            cam.tag = "MainCamera";
            cam.transform.position = new Vector3(0f, 3.2f, -4.75f);
            cam.transform.rotation = Quaternion.LookRotation(new Vector3(0f, 3.2f, 0.35f) - cam.transform.position);
            var c = cam.AddComponent<Camera>();
            c.fieldOfView = 24f; c.clearFlags = CameraClearFlags.SolidColor; c.backgroundColor = new Color(0.03f, 0.035f, 0.05f);
            cam.AddComponent<AudioListener>();

            var key = new GameObject("Key_Light").AddComponent<Light>();
            key.type = LightType.Directional; key.intensity = 1.3f; key.color = new Color(1f, 0.94f, 0.88f);
            key.transform.rotation = Quaternion.Euler(40f, -25f, 0f);
            var fill = new GameObject("Fill_Light").AddComponent<Light>();
            fill.type = LightType.Point; fill.intensity = 1.2f; fill.range = 8f; fill.transform.position = new Vector3(2.4f, 3.4f, -1.5f);

            avatarAnchor = new GameObject("AvatarAnchor").transform;
        }

        static void BuildUi(GuideGamePack pack, List<GuideCharacterProfile> characters, Transform avatarAnchor)
        {
            _thPanels.Clear(); _thButtons.Clear(); _thShapeOnly.Clear(); _thAccents.Clear();
            var es = new GameObject("EventSystem");
            es.AddComponent<EventSystem>();
            es.AddComponent<InputSystemUIInputModule>();

            var canvasGo = new GameObject("GuideCanvas");
            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();
            var ct = canvasGo.transform;

            var gameArea = Panel("GameArea", ct, new Color(0.06f, 0.08f, 0.11f, 0.92f), new Vector2(0.01f, 0.25f), new Vector2(0.42f, 0.98f));
            _thPanels.Add(gameArea.GetComponent<Image>());
            var gameGo = new GameObject("DemoGame");
            var adapter = gameGo.AddComponent<DemoOutpostAdapter>();
            adapter.pack = pack;

            var lobby = Panel("lobby", gameArea, new Color(0, 0, 0, 0), Vector2.zero, Vector2.one);
            Vector2 C(int col, int row) => new Vector2(0.03f + col * 0.32f, 0.05f + row * 0.175f);
            Vector2 C2(int col, int row) => C(col, row) + new Vector2(0.30f, 0.155f);
            var slots = new[] { (C(0, 0), C2(0, 0)), (C(2, 0), C2(2, 0)), (C(1, 1), C2(1, 1)), (C(1, 2), C2(1, 2)), (C(2, 2), C2(2, 2)) };
            var guideSystems = pack.Data.systems.FindAll(sy => !sy.info_only && !string.IsNullOrEmpty(sy.ui_target));
            for (int i = 0; i < guideSystems.Count && i < slots.Length; i++)
                SystemButton(lobby, adapter, guideSystems[i].id, guideSystems[i].name, guideSystems[i].ui_target, slots[i].Item1, slots[i].Item2);
            Decoy(lobby, adapter, "우편", "decoy_mail", C(0, 2), C2(0, 2));
            Decoy(lobby, adapter, "이벤트", "decoy_event", C(0, 1), C2(0, 1));
            Decoy(lobby, adapter, "설정", "decoy_settings", C(2, 1), C2(2, 1));

            var screens = new List<GameObject> { lobby.gameObject };
            foreach (var sy in guideSystems)
            {
                var st = pack.Data.tutorial_steps.Find(x => x.system == sy.id);
                if (st == null) continue;
                screens.Add(SubScreen(gameArea, adapter, sy.id, sy.name, st.action_label, st.ui_target));
            }
            adapter.screens = screens;

            var result = Panel("ResultOverlay", gameArea, new Color(0f, 0f, 0f, 0.82f), Vector2.zero, Vector2.one);
            Label(result, "임무 완료\n(화면을 누르면 넘어갑니다)", 44, TextAnchor.MiddleCenter, Color.white, Vector2.zero, Vector2.one);
            var skip = result.gameObject.AddComponent<Button>();
            UnityEventTools.AddPersistentListener(skip.onClick, adapter.SkipResult);
            result.gameObject.SetActive(false);
            adapter.resultOverlay = result.gameObject;

            adapter.statusText = Label(gameArea, "", 22, TextAnchor.UpperLeft, new Color(0.8f, 0.9f, 1f), new Vector2(0.04f, 0.62f), new Vector2(0.96f, 0.97f));
            MakeCollapsible(gameArea, GuideCollapsiblePanel.Side.Left);

            GameObject stepTitle = null;
            var mt = AssetDatabase.LoadAssetAtPath<GameObject>(StepTitlePrefab);
            if (mt != null)
            {
                var holder = new GameObject("StepTitle", typeof(RectTransform)).GetComponent<RectTransform>();
                holder.SetParent(gameArea, false);
                holder.anchorMin = holder.anchorMax = new Vector2(0.5f, 0.72f); holder.sizeDelta = Vector2.zero;
                stepTitle = (GameObject)PrefabUtility.InstantiatePrefab(mt, holder);
                stepTitle.transform.localScale = Vector3.one * 1.8f;
                stepTitle.SetActive(false);
            }

            var dlg = Panel("DialoguePanel", ct, new Color(0.02f, 0.025f, 0.035f, 0.9f), new Vector2(0.47f, 0.20f), new Vector2(0.99f, 0.42f));
            _thPanels.Add(dlg.GetComponent<Image>());
            var nameText = Label(dlg, "라피", 30, TextAnchor.UpperLeft, Color.red, new Vector2(0.04f, 0.70f), new Vector2(0.6f, 0.95f));
            nameText.fontStyle = FontStyle.Bold;
            var lineText = Label(dlg, "", 28, TextAnchor.UpperLeft, Color.white, new Vector2(0.04f, 0.06f), new Vector2(0.96f, 0.70f));
            var thinking = Label(dlg, "● ● ●", 26, TextAnchor.UpperRight, new Color(1f, 1f, 1f, 0.6f), new Vector2(0.6f, 0.72f), new Vector2(0.96f, 0.95f));

            var historyRoot = Panel("ConversationHistory", ct, new Color(.02f, .025f, .035f, .80f), new Vector2(.47f, .43f), new Vector2(.99f, .66f));
            Label(historyRoot, "대화 기록", 20, TextAnchor.MiddleLeft, Color.white, new Vector2(.025f, .88f), new Vector2(.97f, 1f));
            var viewport = Panel("Viewport", historyRoot, Color.clear, new Vector2(.01f, .02f), new Vector2(.99f, .87f));
            viewport.gameObject.AddComponent<RectMask2D>();
            var content = new GameObject("Content", typeof(RectTransform), typeof(VerticalLayoutGroup), typeof(ContentSizeFitter)).GetComponent<RectTransform>();
            content.SetParent(viewport, false);
            content.anchorMin = new Vector2(0, 1); content.anchorMax = Vector2.one;
            content.pivot = new Vector2(.5f, 1); content.sizeDelta = Vector2.zero;
            var layout = content.GetComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(6, 6, 4, 4); layout.spacing = 4;
            layout.childControlWidth = layout.childControlHeight = true;
            layout.childForceExpandWidth = true; layout.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            var historyScroll = historyRoot.gameObject.AddComponent<ScrollRect>();
            historyScroll.viewport = viewport; historyScroll.content = content;
            historyScroll.horizontal = false; historyScroll.vertical = true; historyScroll.scrollSensitivity = 30;
            historyScroll.movementType = ScrollRect.MovementType.Clamped;
            var history = historyRoot.gameObject.AddComponent<GuideConversationHistory>();
            history.content = content; history.scroll = historyScroll; history.font = _font;

            var inputBar = Panel("InputBar", ct, new Color(0.02f, 0.025f, 0.035f, 0.75f), new Vector2(0.47f, 0.03f), new Vector2(0.99f, 0.19f));
            _thPanels.Add(inputBar.GetComponent<Image>());
            var input = InputBox(inputBar, new Vector2(0.01f, 0.60f), new Vector2(0.75f, 0.96f));
            adapter.chatInput = input;
            var send = Btn(inputBar, "보내기", new Vector2(0.76f, 0.60f), new Vector2(0.99f, 0.96f), new Color(0.15f, 0.45f, 0.7f));
            _thAccents.Add(send.GetComponent<Image>());
            _thShapeOnly.Add(input.GetComponent<Image>());
            var voiceLabel = Label(inputBar, "V 키를 누르고 말하기", 16, TextAnchor.MiddleLeft, new Color(0.7f, 0.8f, 0.9f), new Vector2(0.02f, 0.01f), new Vector2(0.99f, 0.12f));
            var suggestionButtons = new Button[3];
            var suggestionLabels = new Text[3];
            var suggestionCategories = new Text[3];
            for (int i = 0; i < 3; i++)
            {
                float left = .01f + i * .33f;
                suggestionCategories[i] = Label(inputBar, "추천 질문", 15, TextAnchor.MiddleLeft, new Color(.75f, .85f, 1), new Vector2(left, .48f), new Vector2(left + .32f, .59f));
                var button = Btn(inputBar, "추천 질문", new Vector2(left, .14f), new Vector2(left + .32f, .47f), new Color(.12f, .20f, .29f));
                suggestionButtons[i] = button;
                suggestionLabels[i] = button.GetComponentInChildren<Text>();
                suggestionLabels[i].resizeTextForBestFit = true;
                suggestionLabels[i].resizeTextMinSize = 14; suggestionLabels[i].resizeTextMaxSize = 20;
            }
            MakeCollapsible(inputBar, GuideCollapsiblePanel.Side.Bottom);

            var topBar = Panel("ControlBar", ct, new Color(0.02f, 0.025f, 0.035f, 0.75f), new Vector2(0.01f, 0.02f), new Vector2(0.42f, 0.23f));
            _thPanels.Add(topBar.GetComponent<Image>());
            var ctrl = Panel("ControlPanel", topBar, new Color(0, 0, 0, 0), new Vector2(0f, 0.25f), new Vector2(1f, 1f));
            var modelLabel = Label(ctrl, "", 18, TextAnchor.UpperLeft, new Color(1f, 0.9f, 0.6f), new Vector2(0.02f, 0.80f), new Vector2(0.98f, 0.98f));
            var bBase = Btn(ctrl, "기본 모델", new Vector2(0.01f, 0.44f), new Vector2(0.24f, 0.76f), new Color(0.3f, 0.3f, 0.35f));
            var bLora = Btn(ctrl, "LoRA 모델", new Vector2(0.25f, 0.44f), new Vector2(0.48f, 0.76f), new Color(0.55f, 0.2f, 0.2f));
            var bRapi = Btn(ctrl, "라피", new Vector2(0.01f, 0.06f), new Vector2(0.15f, 0.38f), new Color(0.35f, 0.15f, 0.15f));
            var bArona = Btn(ctrl, "아로나", new Vector2(0.16f, 0.06f), new Vector2(0.32f, 0.38f), new Color(0.12f, 0.3f, 0.45f));
            var bNer = Btn(ctrl, "네르", new Vector2(0.33f, 0.06f), new Vector2(0.48f, 0.38f), new Color(0.25f, 0.35f, 0.15f));
            var bPolicy = Btn(ctrl, "규칙 정책", new Vector2(0.52f, 0.44f), new Vector2(0.75f, 0.76f), new Color(0.25f, 0.3f, 0.25f));
            var bCheat = Btn(ctrl, "임무 3회", new Vector2(0.76f, 0.44f), new Vector2(0.99f, 0.76f), new Color(0.3f, 0.25f, 0.15f));
            foreach (var b in new[] { bBase, bLora, bRapi, bArona, bNer, bPolicy, bCheat }) _thShapeOnly.Add(b.GetComponent<Image>());
            var aff = MakeSlider(ctrl, new Vector2(0.62f, 0.16f), new Vector2(0.99f, 0.28f));
            Label(ctrl, "호감도", 18, TextAnchor.MiddleLeft, new Color(0.8f, 0.85f, 0.9f), new Vector2(0.52f, 0.06f), new Vector2(0.62f, 0.38f));
            var storyLabel = Label(topBar, "스토리 진행도", 16, TextAnchor.MiddleLeft, Color.white, new Vector2(0.02f, 0.02f), new Vector2(0.46f, 0.24f));
            var storySlider = MakeSlider(topBar, new Vector2(0.47f, 0.08f), new Vector2(0.70f, 0.18f));
            storySlider.name = "StorySlider";
            storySlider.wholeNumbers = true;
            var explanationRoot = Panel("ExplanationMode", topBar, Color.clear, new Vector2(.74f, .015f), new Vector2(.99f, .24f));
            var toggleBox = Panel("Box", explanationRoot, new Color(.1f, .15f, .22f), new Vector2(0, .15f), new Vector2(.18f, .85f));
            var check = Panel("Check", toggleBox, new Color(.45f, .8f, 1), new Vector2(.18f, .18f), new Vector2(.82f, .82f));
            Label(explanationRoot, "설명 모드", 16, TextAnchor.MiddleLeft, Color.white, new Vector2(.23f, 0), Vector2.one);
            var explanationToggle = explanationRoot.gameObject.AddComponent<Toggle>();
            explanationToggle.targetGraphic = toggleBox.GetComponent<Image>();
            explanationToggle.graphic = check.GetComponent<Image>(); explanationToggle.isOn = true;
            MakeCollapsible(topBar, GuideCollapsiblePanel.Side.Bottom);

            var frame = new GameObject("HighlightFrame", typeof(RectTransform)).GetComponent<RectTransform>();
            frame.SetParent(ct, false);
            var bars = new GameObject("Bars", typeof(RectTransform)).GetComponent<RectTransform>();
            bars.SetParent(frame, false); bars.anchorMin = Vector2.zero; bars.anchorMax = Vector2.one; bars.offsetMin = bars.offsetMax = Vector2.zero;
            foreach (var (a0, a1) in new[] { (new Vector2(0, 0), new Vector2(1, 0)), (new Vector2(0, 1), new Vector2(1, 1)), (new Vector2(0, 0), new Vector2(0, 1)), (new Vector2(1, 0), new Vector2(1, 1)) })
            {
                var bar = new GameObject("Bar", typeof(RectTransform), typeof(Image)).GetComponent<RectTransform>();
                bar.SetParent(bars, false);
                bar.anchorMin = a0; bar.anchorMax = a1; bar.sizeDelta = new Vector2(a0.x == a1.x ? 6 : 0, a0.y == a1.y ? 6 : 0);
                var img = bar.GetComponent<Image>(); img.color = new Color(1f, 0.85f, 0.2f); img.raycastTarget = false;
            }
            frame.gameObject.AddComponent<Image>().color = new Color(1, 1, 1, 0);
            frame.GetComponent<Image>().raycastTarget = false;

            var sys = new GameObject("GuideSystem");
            var hl = sys.AddComponent<GuideHighlighter>(); hl.frame = frame;
            var api = sys.AddComponent<GuideApiClient>();
            var voice = sys.AddComponent<GuideVoiceInput>();
            var logger = sys.AddComponent<GuideTurnLogger>();
            logger.logPath = "";
            var portraitArea = Panel("PortraitArea", ct, new Color(0, 0, 0, 0), new Vector2(0.45f, 0.40f), new Vector2(0.99f, 0.99f));
            portraitArea.SetSiblingIndex(0);
            var bgDim = Panel("BackgroundDim", ct, new Color(0, 0, 0, 0.35f), Vector2.zero, Vector2.one);
            bgDim.GetComponent<Image>().raycastTarget = false;
            bgDim.SetSiblingIndex(0);
            var bgRoot = Panel("BackgroundRoot", ct, new Color(0, 0, 0, 0), Vector2.zero, Vector2.one);
            bgRoot.SetSiblingIndex(0);
            var bg = new GameObject("Background", typeof(RectTransform), typeof(Image), typeof(AspectRatioFitter)).GetComponent<Image>();
            bg.rectTransform.SetParent(bgRoot, false);
            bg.raycastTarget = false; bg.enabled = false;
            var fit = bg.GetComponent<AspectRatioFitter>(); fit.aspectMode = AspectRatioFitter.AspectMode.EnvelopeParent; fit.aspectRatio = 16f / 9f;
            var theme = sys.AddComponent<GuideUiTheme>();
            theme.background = bg; theme.backgroundDim = bgDim.GetComponent<Image>();
            theme.highlight = frame.GetComponent<Image>(); theme.highlightBars = bars.gameObject;
            theme.panels.AddRange(_thPanels); theme.buttons.AddRange(_thButtons); theme.shapeOnly.AddRange(_thShapeOnly); theme.accents.AddRange(_thAccents);
            var portraitRoot = new GameObject("Portrait", typeof(RectTransform)).GetComponent<RectTransform>();
            portraitRoot.SetParent(portraitArea, false);
            portraitRoot.anchorMin = Vector2.zero; portraitRoot.anchorMax = Vector2.one; portraitRoot.pivot = new Vector2(0.5f, 0f);
            portraitRoot.offsetMin = portraitRoot.offsetMax = Vector2.zero;
            Image Layer(string n)
            {
                var img = new GameObject(n, typeof(RectTransform), typeof(Image)).GetComponent<Image>();
                var rt = img.rectTransform; rt.SetParent(portraitRoot, false);
                rt.anchorMin = Vector2.zero; rt.anchorMax = Vector2.one; rt.pivot = new Vector2(0.5f, 0f);
                rt.offsetMin = rt.offsetMax = Vector2.zero;
                img.raycastTarget = false; img.preserveAspect = true; img.enabled = false;
                return img;
            }
            var presenter = sys.AddComponent<GuideSpritePresenter>();
            presenter.nameText = nameText; presenter.lineText = lineText; presenter.thinkingIndicator = thinking.gameObject;
            presenter.portraitRoot = portraitRoot; presenter.bodyImage = Layer("Body"); presenter.faceImage = Layer("Face"); presenter.mouthImage = Layer("Mouth");
            var director = sys.AddComponent<GuideDirector>();
            director.character = characters[Mathf.Clamp(System.Array.FindIndex(Packs, p => p.key == _buildKey), 0, characters.Count - 1)]; director.game = adapter; director.presenterBehaviour = presenter; director.highlighter = hl;
            director.api = api; director.voice = voice; director.logger = logger; director.theme = theme;
            if (stepTitle != null)
            {
                var banner = sys.AddComponent<AIGuide.Demo.GuideStepBanner>();
                banner.game = adapter; banner.title = stepTitle; banner.koreanFont = KoreanTmpFont();
            }

            var panel = sys.AddComponent<DemoControlPanel>();
            panel.director = director; panel.game = adapter; panel.input = input; panel.modelLabel = modelLabel; panel.voiceLabel = voiceLabel;
            panel.characters = characters;
            panel.history = history;
            panel.suggestionButtons = suggestionButtons; panel.suggestionLabels = suggestionLabels; panel.suggestionCategories = suggestionCategories;
            for (int i = 0; i < 3; i++) UnityEventTools.AddIntPersistentListener(suggestionButtons[i].onClick, panel.SendSuggestion, i);
            UnityEventTools.AddPersistentListener(explanationToggle.onValueChanged, panel.SetExplanationMode);
            panel.storySlider = storySlider; panel.storyLabel = storyLabel;
            UnityEventTools.AddPersistentListener(storySlider.onValueChanged, panel.SetStoryChapter);
            UnityEventTools.AddPersistentListener(send.onClick, panel.Send);
            UnityEventTools.AddPersistentListener(bBase.onClick, panel.UseBaseModel);
            UnityEventTools.AddPersistentListener(bLora.onClick, panel.UseLoraModel);
            UnityEventTools.AddIntPersistentListener(bRapi.onClick, panel.SwapCharacter, 0);
            UnityEventTools.AddIntPersistentListener(bArona.onClick, panel.SwapCharacter, 1);
            UnityEventTools.AddIntPersistentListener(bNer.onClick, panel.SwapCharacter, 2);
            UnityEventTools.AddPersistentListener(bPolicy.onClick, panel.TogglePolicy);
            UnityEventTools.AddPersistentListener(bCheat.onClick, panel.CheatThreeMissions);
            UnityEventTools.AddPersistentListener(aff.onValueChanged, panel.SetAffection);
            aff.value = adapter.affection;
        }

        static GuideCollapsiblePanel MakeCollapsible(RectTransform panel, GuideCollapsiblePanel.Side side)
        {
            var c = panel.gameObject.AddComponent<GuideCollapsiblePanel>();
            c.side = side;
            var tab = Panel("Tab_" + panel.name, panel, new Color(0.10f, 0.13f, 0.18f, 0.95f), Vector2.zero, Vector2.zero);
            bool vertical = side == GuideCollapsiblePanel.Side.Left || side == GuideCollapsiblePanel.Side.Right;
            Vector2 anchor, pivot;
            switch (side)
            {
                case GuideCollapsiblePanel.Side.Left: anchor = new Vector2(1f, 0.5f); pivot = new Vector2(0f, 0.5f); break;
                case GuideCollapsiblePanel.Side.Right: anchor = new Vector2(0f, 0.5f); pivot = new Vector2(1f, 0.5f); break;
                case GuideCollapsiblePanel.Side.Top: anchor = new Vector2(0.5f, 0f); pivot = new Vector2(0.5f, 1f); break;
                default: anchor = new Vector2(0.5f, 1f); pivot = new Vector2(0.5f, 0f); break;
            }
            tab.anchorMin = tab.anchorMax = anchor; tab.pivot = pivot; tab.anchoredPosition = Vector2.zero;
            tab.sizeDelta = vertical ? new Vector2(36f, 120f) : new Vector2(120f, 34f);
            c.toggle = tab.gameObject.AddComponent<Button>();
            _thShapeOnly.Add(tab.GetComponent<Image>());
            var arrow = new GameObject("Arrow", typeof(RectTransform), typeof(Image)).GetComponent<RectTransform>();
            arrow.SetParent(tab, false);
            arrow.anchorMin = arrow.anchorMax = new Vector2(0.5f, 0.5f); arrow.sizeDelta = new Vector2(22f, 22f);
            var img = arrow.GetComponent<Image>();
            img.sprite = AssetDatabase.LoadAssetAtPath<Sprite>(ParticleSprites + "/Arrow.png");
            img.color = new Color(0.85f, 0.9f, 1f); img.raycastTarget = false;
            c.arrow = arrow;
            return c;
        }

        static void AddSparkle(RectTransform frame)
        {
            HighlightSparkle.AddTo(frame, AssetDatabase.LoadAssetAtPath<Texture2D>(ParticleSprites + "/Star.png"));
        }

        static TMP_FontAsset KoreanTmpFont()
        {
            string path = DataDir + "/Pretendard_TMP.asset";
            var fa = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path);
            if (fa != null) return fa;
            var font = AssetDatabase.LoadAssetAtPath<Font>(FontPath);
            if (font == null) return null;
            fa = TMP_FontAsset.CreateFontAsset(font, 90, 9, UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA, 1024, 1024, AtlasPopulationMode.Dynamic, true);
            fa.name = "Pretendard_TMP";
            AssetDatabase.CreateAsset(fa, path);
            fa.atlasTextures[0].name = "Pretendard_TMP Atlas";
            AssetDatabase.AddObjectToAsset(fa.atlasTextures[0], fa);
            fa.material.name = "Pretendard_TMP Material";
            AssetDatabase.AddObjectToAsset(fa.material, fa);
            AssetDatabase.SaveAssets();
            return fa;
        }

        static RectTransform Panel(string name, Transform parent, Color color, Vector2 min, Vector2 max)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false); rt.anchorMin = min; rt.anchorMax = max; rt.offsetMin = rt.offsetMax = Vector2.zero;
            var img = go.GetComponent<Image>(); img.color = color; img.raycastTarget = color.a > 0.01f;
            return rt;
        }

        static Text Label(Transform parent, string text, int size, TextAnchor anchor, Color color, Vector2 min, Vector2 max)
        {
            var go = new GameObject("Text", typeof(RectTransform), typeof(Text));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false); rt.anchorMin = min; rt.anchorMax = max; rt.offsetMin = rt.offsetMax = Vector2.zero;
            var t = go.GetComponent<Text>();
            t.font = _font; t.text = text; t.fontSize = size; t.alignment = anchor; t.color = color; t.raycastTarget = false;
            t.horizontalOverflow = HorizontalWrapMode.Wrap; t.verticalOverflow = VerticalWrapMode.Overflow;
            return t;
        }

        static Button Btn(Transform parent, string text, Vector2 min, Vector2 max, Color color)
        {
            var rt = Panel("Btn_" + text, parent, color, min, max);
            var b = rt.gameObject.AddComponent<Button>();
            Label(rt, text, 24, TextAnchor.MiddleCenter, Color.white, Vector2.zero, Vector2.one);
            return b;
        }

        static void SystemButton(Transform parent, DemoOutpostAdapter adapter, string systemId, string label, string targetId, Vector2 min, Vector2 max)
        {
            var b = Btn(parent, label, min, max, new Color(0.16f, 0.24f, 0.34f));
            _thButtons.Add(b.GetComponent<Image>());
            b.gameObject.AddComponent<GuideUiTarget>().targetId = targetId;
            UnityEventTools.AddStringPersistentListener(b.onClick, adapter.OpenSystem, systemId);
        }

        static void Decoy(Transform parent, DemoOutpostAdapter adapter, string label, string id, Vector2 min, Vector2 max)
        {
            var b = Btn(parent, label, min, max, new Color(0.2f, 0.2f, 0.22f, 0.9f));
            _thShapeOnly.Add(b.GetComponent<Image>());
            UnityEventTools.AddStringPersistentListener(b.onClick, adapter.WrongClick, id);
        }

        static GameObject SubScreen(Transform parent, DemoOutpostAdapter adapter, string id, string title, string action, string targetId)
        {
            var p = Panel(id, parent, new Color(0, 0, 0, 0), Vector2.zero, Vector2.one);
            Label(p, title, 40, TextAnchor.UpperCenter, Color.white, new Vector2(0, 0.85f), new Vector2(1, 0.97f));
            var main = Btn(p, action, new Vector2(0.32f, 0.42f), new Vector2(0.68f, 0.56f), new Color(0.2f, 0.42f, 0.3f));
            main.gameObject.AddComponent<GuideUiTarget>().targetId = targetId;
            _thAccents.Add(main.GetComponent<Image>());
            UnityEventTools.AddStringPersistentListener(main.onClick, adapter.StepAction, id);
            var back = Btn(p, "뒤로", new Vector2(0.03f, 0.88f), new Vector2(0.16f, 0.97f), new Color(0.25f, 0.25f, 0.28f));
            back.gameObject.AddComponent<GuideUiTarget>().targetId = "btn_back";
            _thShapeOnly.Add(back.GetComponent<Image>());
            UnityEventTools.AddPersistentListener(back.onClick, adapter.Back);
            p.gameObject.SetActive(false);
            return p.gameObject;
        }

        static InputField InputBox(Transform parent, Vector2 min, Vector2 max)
        {
            var rt = Panel("ChatInput", parent, new Color(1f, 1f, 1f, 0.95f), min, max);
            var f = rt.gameObject.AddComponent<InputField>();
            var text = Label(rt, "", 24, TextAnchor.MiddleLeft, Color.black, new Vector2(0.03f, 0), new Vector2(0.97f, 1));
            text.supportRichText = false;
            var ph = Label(rt, "캐릭터에게 물어보기 (Enter)", 24, TextAnchor.MiddleLeft, new Color(0, 0, 0, 0.4f), new Vector2(0.03f, 0), new Vector2(0.97f, 1));
            f.textComponent = text; f.placeholder = ph; f.lineType = InputField.LineType.SingleLine;
            return f;
        }

        static UnityEngine.UI.Slider MakeSlider(Transform parent, Vector2 min, Vector2 max)
        {
            var rt = Panel("AffectionSlider", parent, new Color(0.15f, 0.15f, 0.18f), min, max);
            var fillArea = Panel("Fill", rt, new Color(0.8f, 0.35f, 0.35f), Vector2.zero, new Vector2(0.5f, 1));
            var handle = Panel("Handle", rt, Color.white, new Vector2(0.5f, 0), new Vector2(0.5f, 1));
            handle.sizeDelta = new Vector2(14, 0);
            var s = rt.gameObject.AddComponent<UnityEngine.UI.Slider>();
            s.fillRect = fillArea; s.handleRect = handle; s.minValue = 0; s.maxValue = 100; s.wholeNumbers = true;
            return s;
        }
    }
}
