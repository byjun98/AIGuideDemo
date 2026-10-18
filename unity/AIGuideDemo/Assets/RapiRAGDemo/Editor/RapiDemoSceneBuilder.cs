using System.IO;
using System.Text;
using RapiRAGDemo;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace RapiRAGDemo.Editor
{
    public static class RapiDemoSceneBuilder
    {
        private const string RootFolder = "Assets/RapiRAGDemo";
        private const string ModelPath = RootFolder + "/Models/NIKKE_Rapi/NIKKE_Rapi.fbx";
        private const string PrefabPath = RootFolder + "/Prefabs/RapiLobbyCharacter.prefab";
        private const string ScenePath = RootFolder + "/Scenes/RapiLobbyDemo.unity";
        private const string FontPath = RootFolder + "/Fonts/Pretendard-Regular.otf";
        private const string CommanderRoomTexturePath = RootFolder + "/Textures/Backgrounds/CommanderRoom.png";

        [MenuItem("Rapi RAG Demo/Build Lobby Demo Scene")]
        public static void BuildDemoScene()
        {
            EnsureFolders();
            ConfigureModelImporter();
            ConfigureBackgroundTextureImporter();
            AssetDatabase.Refresh();

            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            Material darkMetal = CreateMaterial("Rapi_DarkMetal", new Color(0.025f, 0.028f, 0.034f), 0f);
            Material redGlow = CreateMaterial("Rapi_RedGlow", new Color(0.95f, 0.08f, 0.08f), 2.4f);

            CreateEnvironment(darkMetal);
            Camera mainCamera = CreateCamera();
            RapiLobbyAnimator characterAnimator = CreateCharacter(redGlow);
            CreateLighting(characterAnimator);
            CreateHud(characterAnimator);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            AddSceneToBuildSettings(ScenePath);
            Selection.activeObject = AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath);
            Debug.Log("Rapi RAG demo scene built: " + ScenePath + " using " + mainCamera.name);
        }

        private static void EnsureFolders()
        {
            string[] folders =
            {
                RootFolder,
                RootFolder + "/Models",
                RootFolder + "/Prefabs",
                RootFolder + "/Scenes",
                RootFolder + "/Materials",
                RootFolder + "/Materials/Model",
                RootFolder + "/Textures",
                RootFolder + "/Textures/Backgrounds",
                RootFolder + "/Fonts",
                RootFolder + "/Scripts",
                RootFolder + "/Editor"
            };

            foreach (string folder in folders)
            {
                if (!AssetDatabase.IsValidFolder(folder))
                {
                    string parent = Path.GetDirectoryName(folder).Replace("\\", "/");
                    string name = Path.GetFileName(folder);
                    AssetDatabase.CreateFolder(parent, name);
                }
            }
        }

        private static void ConfigureModelImporter()
        {
            ModelImporter importer = AssetImporter.GetAtPath(ModelPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogWarning("Rapi FBX not found yet: " + ModelPath);
                return;
            }

            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.animationType = ModelImporterAnimationType.Generic;
            importer.importBlendShapes = true;
            importer.importVisibility = false;
            importer.importCameras = false;
            importer.importLights = false;
            importer.SaveAndReimport();
        }

        private static void ConfigureBackgroundTextureImporter()
        {
            TextureImporter importer = AssetImporter.GetAtPath(CommanderRoomTexturePath) as TextureImporter;
            if (importer == null)
            {
                return;
            }

            importer.textureType = TextureImporterType.Default;
            importer.sRGBTexture = true;
            importer.mipmapEnabled = false;
            importer.alphaSource = TextureImporterAlphaSource.None;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.SaveAndReimport();
        }

        private static Material CreateMaterial(string name, Color color, float emission)
        {
            string path = RootFolder + "/Materials/" + name + ".mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null)
                {
                    shader = Shader.Find("Standard");
                }

                material = new Material(shader);
                AssetDatabase.CreateAsset(material, path);
            }

            SetMaterialColor(material, color);
            if (emission > 0f)
            {
                material.EnableKeyword("_EMISSION");
                if (material.HasProperty("_EmissionColor"))
                {
                    material.SetColor("_EmissionColor", color * emission);
                }
            }

            EditorUtility.SetDirty(material);
            return material;
        }

        private static void SetMaterialColor(Material material, Color color)
        {
            if (material.HasProperty("_BaseColor"))
            {
                material.SetColor("_BaseColor", color);
            }
            else if (material.HasProperty("_Color"))
            {
                material.SetColor("_Color", color);
            }
        }

        private static void CreateEnvironment(Material darkMetal)
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.42f, 0.43f, 0.48f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = new Color(0.015f, 0.017f, 0.024f);
            RenderSettings.fogDensity = 0.025f;

            GameObject environment = new GameObject("NikkeStyle_Lobby_Set");

            CreateCommanderRoomBackdrop(environment.transform);
            CreateCube("Floor_BlackDeck", environment.transform, new Vector3(0f, -0.08f, 0.8f), new Vector3(10.5f, 0.12f, 6.8f), darkMetal);
        }

        private static GameObject CreateCube(string name, Transform parent, Vector3 position, Vector3 scale, Material material)
        {
            GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = name;
            cube.transform.SetParent(parent, false);
            cube.transform.position = position;
            cube.transform.localScale = scale;
            Renderer renderer = cube.GetComponent<Renderer>();
            renderer.sharedMaterial = material;
            Object.DestroyImmediate(cube.GetComponent<Collider>());
            return cube;
        }

        private static void CreateCommanderRoomBackdrop(Transform parent)
        {
            Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(CommanderRoomTexturePath);
            if (texture == null)
            {
                Debug.LogWarning("Commander room background not found: " + CommanderRoomTexturePath);
                return;
            }

            const float width = 15.5f;
            const float height = 8.75f;
            GameObject backdrop = GameObject.CreatePrimitive(PrimitiveType.Quad);
            backdrop.name = "CommanderRoom_Backdrop";
            backdrop.transform.SetParent(parent, false);
            backdrop.transform.position = new Vector3(0f, 3.0f, 3.2f);
            backdrop.transform.rotation = Quaternion.identity;
            backdrop.transform.localScale = new Vector3(width, height, 1f);

            Renderer renderer = backdrop.GetComponent<Renderer>();
            renderer.sharedMaterial = CreateCommanderRoomMaterial(texture, width / height);
            Object.DestroyImmediate(backdrop.GetComponent<Collider>());
        }

        private static Material CreateCommanderRoomMaterial(Texture2D texture, float planeAspect)
        {
            string path = RootFolder + "/Materials/Rapi_CommanderRoomBackdrop.mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Unlit");
                if (shader == null)
                {
                    shader = Shader.Find("Unlit/Texture");
                }

                if (shader == null)
                {
                    shader = Shader.Find("Standard");
                }

                material = new Material(shader);
                AssetDatabase.CreateAsset(material, path);
            }

            if (material.HasProperty("_BaseMap"))
            {
                material.SetTexture("_BaseMap", texture);
            }

            if (material.HasProperty("_MainTex"))
            {
                material.SetTexture("_MainTex", texture);
            }

            SetMaterialColor(material, Color.white);
            ApplyCoverTextureScale(material, texture, planeAspect, "_BaseMap");
            ApplyCoverTextureScale(material, texture, planeAspect, "_MainTex");
            EditorUtility.SetDirty(material);
            return material;
        }

        private static void ApplyCoverTextureScale(Material material, Texture2D texture, float planeAspect, string property)
        {
            if (!material.HasProperty(property) || texture.height <= 0)
            {
                return;
            }

            float textureAspect = (float)texture.width / texture.height;
            Vector2 scale = Vector2.one;
            Vector2 offset = Vector2.zero;

            if (planeAspect > textureAspect)
            {
                scale.y = textureAspect / planeAspect;
                offset.y = (1f - scale.y) * 0.5f;
            }
            else
            {
                scale.x = planeAspect / textureAspect;
                offset.x = (1f - scale.x) * 0.5f;
            }

            material.SetTextureScale(property, scale);
            material.SetTextureOffset(property, offset);
        }

        private static Camera CreateCamera()
        {
            GameObject cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0f, 3.2f, -4.75f);
            LookAt(cameraObject.transform, new Vector3(0f, 3.2f, 0.35f));

            Camera camera = cameraObject.AddComponent<Camera>();
            camera.fieldOfView = 24f;
            camera.nearClipPlane = 0.05f;
            camera.farClipPlane = 100f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.015f, 0.017f, 0.024f);
            cameraObject.AddComponent<AudioListener>();
            return camera;
        }

        private static void CreateLighting(RapiLobbyAnimator animator)
        {
            GameObject key = new GameObject("Key_Light");
            Light keyLight = key.AddComponent<Light>();
            keyLight.type = LightType.Directional;
            keyLight.color = new Color(1f, 0.92f, 0.86f);
            keyLight.intensity = 1.35f;
            key.transform.rotation = Quaternion.Euler(42f, -28f, 0f);

            GameObject rim = new GameObject("Rapi_Emotion_RimLight");
            Light rimLight = rim.AddComponent<Light>();
            rimLight.type = LightType.Point;
            rimLight.color = new Color(1f, 0.36f, 0.32f);
            rimLight.intensity = 1.4f;
            rimLight.range = 7f;
            rim.transform.position = new Vector3(1.8f, 2.2f, -1.0f);
            animator.emotionLight = rimLight;
        }

        private static RapiLobbyAnimator CreateCharacter(Material redGlow)
        {
            GameObject modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ModelPath);
            GameObject root = new GameObject("Rapi_LobbyCharacter");
            root.transform.position = new Vector3(0f, 0f, 0.25f);

            RapiLobbyAnimator animator = root.AddComponent<RapiLobbyAnimator>();
            ConfigureCharacterHitbox(root);

            if (modelAsset == null)
            {
                GameObject fallback = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                fallback.name = "Rapi_Model_Missing_Fallback";
                fallback.transform.SetParent(root.transform, false);
                fallback.transform.localPosition = new Vector3(0f, 1.8f, 0f);
                fallback.transform.localScale = new Vector3(0.65f, 1.8f, 0.65f);
                animator.modelRoot = fallback.transform;
                SaveCharacterPrefab(root);
                return animator;
            }

            GameObject modelInstance = PrefabUtility.InstantiatePrefab(modelAsset) as GameObject;
            modelInstance.name = "Rapi_OfficialMMD_FBX";
            modelInstance.transform.SetParent(root.transform, false);
            modelInstance.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            NormalizeModel(modelInstance.transform, 4.2f);
            TuneModelMaterials(modelInstance);

            animator.modelRoot = modelInstance.transform;
            animator.accentRenderers = new[]
            {
                CreateCube("Rapi_Base_RedAccent", root.transform, new Vector3(0f, 0.05f, -0.05f), new Vector3(1.05f, 0.035f, 1.05f), redGlow).GetComponent<Renderer>()
            };

            SaveCharacterPrefab(root);
            return animator;
        }

        private static void ConfigureCharacterHitbox(GameObject root)
        {
            CapsuleCollider hitbox = root.GetComponent<CapsuleCollider>();
            if (hitbox == null)
            {
                hitbox = root.AddComponent<CapsuleCollider>();
            }

            hitbox.isTrigger = true;
            hitbox.direction = 1;
            hitbox.center = new Vector3(0f, 2.05f, 0f);
            hitbox.radius = 0.48f;
            hitbox.height = 4.1f;
        }

        private static void SaveCharacterPrefab(GameObject root)
        {
            PrefabUtility.SaveAsPrefabAssetAndConnect(root, PrefabPath, InteractionMode.AutomatedAction);
            AssetDatabase.SaveAssets();
        }

        private static void NormalizeModel(Transform model, float targetHeight)
        {
            Bounds bounds = CalculateBounds(model.gameObject);
            if (bounds.size.y <= 0.001f)
            {
                return;
            }

            float scale = targetHeight / bounds.size.y;
            model.localScale = Vector3.one * scale;

            bounds = CalculateBounds(model.gameObject);
            Vector3 offset = model.position - bounds.center;
            offset.y = -bounds.min.y;
            model.position += offset;
        }

        private static Bounds CalculateBounds(GameObject root)
        {
            Renderer[] renderers = root.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0)
            {
                return new Bounds(root.transform.position, Vector3.one);
            }

            Bounds bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++)
            {
                bounds.Encapsulate(renderers[i].bounds);
            }

            return bounds;
        }

        private static void TuneModelMaterials(GameObject model)
        {
            Renderer[] renderers = model.GetComponentsInChildren<Renderer>(true);

            foreach (Renderer renderer in renderers)
            {
                Material[] materials = renderer.sharedMaterials;
                for (int i = 0; i < materials.Length; i++)
                {
                    Material sourceMaterial = materials[i];
                    if (sourceMaterial == null)
                    {
                        continue;
                    }

                    materials[i] = CreateModelMaterial(sourceMaterial.name);
                }

                renderer.sharedMaterials = materials;
            }
        }

        private static Material CreateModelMaterial(string sourceName)
        {
            string path = RootFolder + "/Materials/Model/Rapi_Model_" + SanitizeFileName(sourceName) + ".mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                Shader shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null)
                {
                    shader = Shader.Find("Standard");
                }

                material = new Material(shader);
                AssetDatabase.CreateAsset(material, path);
            }

            Texture texture = PickTextureForMaterial(sourceName);
            if (texture != null)
            {
                if (material.HasProperty("_BaseMap"))
                {
                    material.SetTexture("_BaseMap", texture);
                }

                if (material.HasProperty("_MainTex"))
                {
                    material.SetTexture("_MainTex", texture);
                }
            }

            SetMaterialColor(material, Color.white);
            if (material.HasProperty("_Smoothness"))
            {
                material.SetFloat("_Smoothness", 0.42f);
            }

            EditorUtility.SetDirty(material);
            return material;
        }

        private static Texture2D PickTextureForMaterial(string sourceName)
        {
            string name = sourceName.ToLowerInvariant();

            if (name.Contains("weapon"))
            {
                return LoadModelTexture("Weapon_addon_BC.png");
            }

            if (name.Contains("hair_backinside"))
            {
                return LoadModelTexture("Hair_BackInSide_BC.png");
            }

            if (name.Contains("hair_back"))
            {
                return LoadModelTexture("Hair_Back_BC.png");
            }

            if (name.Contains("hair_front"))
            {
                return LoadModelTexture("Hair_Front_BC.png");
            }

            if (name.Contains("hair_side"))
            {
                return LoadModelTexture("Hair_Side_BC.png");
            }

            if (name.Contains("eye"))
            {
                return LoadModelTexture("Eye_BC.png");
            }

            if (name.Contains("head") || name.Contains("新規"))
            {
                return LoadModelTexture("Head_BC.png");
            }

            if (name.Contains("stocking") || name.Contains("shoes"))
            {
                return LoadModelTexture("Bottom_BC.png");
            }

            if (name.Contains("garniture") || name.Contains("hat"))
            {
                return LoadModelTexture("Coat_addon_BC.png");
            }

            if (name.Contains("clothes6") || name.Contains("clothes4"))
            {
                return LoadModelTexture("Coat_BC.png");
            }

            if (name.Contains("clothes3") || name.Contains("clothes2"))
            {
                return LoadModelTexture("Tops_addon_BC.png");
            }

            if (name.Contains("clothes1") || name == "clothes")
            {
                return LoadModelTexture("Shirt_BC.png");
            }

            if (name.Contains("body") || name.Contains("glove"))
            {
                return LoadModelTexture("Body_BC.png");
            }

            return LoadModelTexture("Body_BC.png");
        }

        private static Texture2D LoadModelTexture(string fileName)
        {
            return AssetDatabase.LoadAssetAtPath<Texture2D>(RootFolder + "/Models/NIKKE_Rapi/" + fileName);
        }

        private static string SanitizeFileName(string value)
        {
            StringBuilder builder = new StringBuilder(value.Length);
            foreach (char character in value)
            {
                if (char.IsLetterOrDigit(character) || character == '_' || character == '-')
                {
                    builder.Append(character);
                }
                else
                {
                    builder.Append('_');
                }
            }

            return builder.ToString();
        }

        private static void CreateHud(RapiLobbyAnimator characterAnimator)
        {
            Font font = AssetDatabase.LoadAssetAtPath<Font>(FontPath);
            if (font == null)
            {
                font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            }

            GameObject canvasObject = new GameObject("RapiDemoCanvas");
            Canvas canvas = canvasObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 10;
            CanvasScaler scaler = canvasObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.62f;
            canvasObject.AddComponent<GraphicRaycaster>();

            GameObject dialoguePanel = CreatePanel("GeneratedDialoguePanel", canvasObject.transform, new Color(0.015f, 0.022f, 0.03f, 0.86f), new Vector2(0.14f, 0.405f), new Vector2(0.86f, 0.545f), Vector2.zero, Vector2.zero);
            CreatePanel("GeneratedDialoguePanel_LeftLine", dialoguePanel.transform, new Color(0.1f, 0.48f, 0.72f, 0.95f), new Vector2(0f, 0.08f), new Vector2(0.012f, 0.92f), Vector2.zero, Vector2.zero);
            Text speaker = CreateText("SpeakerText", dialoguePanel.transform, font, "라피", 28, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(1f, 0.22f, 0.22f), new Vector2(0.045f, 0.58f), new Vector2(0.22f, 0.92f), Vector2.zero, Vector2.zero);
            Text mode = CreateText("ModeText", dialoguePanel.transform, font, "호감도 화면", 22, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.86f, 0.96f, 1f), new Vector2(0.20f, 0.58f), new Vector2(0.42f, 0.92f), Vector2.zero, Vector2.zero);
            Text status = CreateText("StatusText", dialoguePanel.transform, font, "선물하기 또는 상담하기를 선택해 주세요.", 22, FontStyle.Normal, TextAnchor.MiddleRight, new Color(0.7f, 0.85f, 0.92f), new Vector2(0.42f, 0.58f), new Vector2(0.94f, 0.92f), Vector2.zero, Vector2.zero);
            Text line = CreateText("DialogueText", dialoguePanel.transform, font, "지휘관, 오늘은 어떤 일부터 확인할까요?", 32, FontStyle.Normal, TextAnchor.MiddleLeft, Color.white, new Vector2(0.045f, 0.12f), new Vector2(0.94f, 0.6f), Vector2.zero, Vector2.zero);

            GameObject bondCard = CreatePanel("BondCard", canvasObject.transform, new Color(1f, 1f, 1f, 0.9f), new Vector2(0.09f, 0.055f), new Vector2(0.91f, 0.385f), Vector2.zero, Vector2.zero);
            CreatePanel("BondCard_RedTopLine", bondCard.transform, new Color(0.94f, 0.08f, 0.08f, 0.96f), new Vector2(0.04f, 0.93f), new Vector2(0.76f, 0.96f), Vector2.zero, Vector2.zero);
            CreatePanel("BondCard_RedBadge", bondCard.transform, new Color(0.94f, 0.08f, 0.08f, 0.96f), new Vector2(0.035f, 0.75f), new Vector2(0.115f, 0.92f), Vector2.zero, Vector2.zero);
            CreateText("BondBadgeIcon", bondCard.transform, font, "★", 34, FontStyle.Bold, TextAnchor.MiddleCenter, Color.white, new Vector2(0.035f, 0.75f), new Vector2(0.115f, 0.92f), Vector2.zero, Vector2.zero);
            Text rankText = CreateText("RankText", bondCard.transform, font, "♥ 호감도 22", 45, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.94f, 0.08f, 0.08f), new Vector2(0.13f, 0.78f), new Vector2(0.49f, 0.94f), Vector2.zero, Vector2.zero);
            CreateText("NameText", bondCard.transform, font, "라피", 50, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.2f, 0.2f, 0.23f), new Vector2(0.06f, 0.56f), new Vector2(0.46f, 0.78f), Vector2.zero, Vector2.zero);
            CreatePanel("BondGauge_Back", bondCard.transform, new Color(0.82f, 0.82f, 0.84f, 0.95f), new Vector2(0.06f, 0.49f), new Vector2(0.64f, 0.53f), Vector2.zero, Vector2.zero);
            CreatePanel("BondGauge_Fill", bondCard.transform, new Color(0.94f, 0.08f, 0.08f, 0.98f), new Vector2(0.06f, 0.49f), new Vector2(0.64f, 0.53f), Vector2.zero, Vector2.zero);
            CreateText("BondGaugeMax", bondCard.transform, font, "최대", 21, FontStyle.Bold, TextAnchor.MiddleRight, new Color(0.94f, 0.08f, 0.08f), new Vector2(0.57f, 0.53f), new Vector2(0.64f, 0.64f), Vector2.zero, Vector2.zero);
            Text nextEpisodeText = CreateText("NextEpisodeText", bondCard.transform, font, "특별 상담 필요 호감도 25", 18, FontStyle.Normal, TextAnchor.MiddleLeft, new Color(0.46f, 0.46f, 0.5f), new Vector2(0.065f, 0.42f), new Vector2(0.58f, 0.5f), Vector2.zero, Vector2.zero);

            GameObject statePanel = CreatePanel("StateControlPanel", canvasObject.transform, new Color(0.015f, 0.022f, 0.03f, 0.82f), new Vector2(0.04f, 0.57f), new Vector2(0.31f, 0.75f), Vector2.zero, Vector2.zero);
            CreatePanel("StateControlPanel_Top", statePanel.transform, new Color(0.94f, 0.08f, 0.08f, 0.92f), new Vector2(0f, 0.94f), new Vector2(1f, 1f), Vector2.zero, Vector2.zero);
            CreateText("StateControlTitle", statePanel.transform, font, "데모 상태 설정", 19, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.95f, 0.97f, 1f), new Vector2(0.06f, 0.76f), new Vector2(0.94f, 0.94f), Vector2.zero, Vector2.zero);
            Button rankDownButton = CreateButton("RankDownButton", statePanel.transform, font, "－", 21, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.06f, 0.55f), new Vector2(0.18f, 0.73f));
            Text stateSummaryText = CreateText("StateSummaryText", statePanel.transform, font, "관계 단계 신뢰", 18, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.86f, 0.96f, 1f), new Vector2(0.21f, 0.55f), new Vector2(0.79f, 0.73f), Vector2.zero, Vector2.zero);
            Button rankUpButton = CreateButton("RankUpButton", statePanel.transform, font, "＋", 21, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.82f, 0.55f), new Vector2(0.94f, 0.73f));

            Button chapterDownButton = CreateButton("ChapterDownButton", statePanel.transform, font, "＜", 18, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.06f, 0.31f), new Vector2(0.18f, 0.49f));
            Text storyProgressText = CreateText("StoryProgressText", statePanel.transform, font, "스토리 4지역까지", 18, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.86f, 0.96f, 1f), new Vector2(0.21f, 0.31f), new Vector2(0.79f, 0.49f), Vector2.zero, Vector2.zero);
            Button chapterUpButton = CreateButton("ChapterUpButton", statePanel.transform, font, "＞", 18, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.82f, 0.31f), new Vector2(0.94f, 0.49f));

            Button scenePrevButton = CreateButton("ScenePrevButton", statePanel.transform, font, "＜", 18, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.06f, 0.07f), new Vector2(0.18f, 0.25f));
            Text sceneText = CreateText("SceneText", statePanel.transform, font, "장면 상담", 18, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.86f, 0.96f, 1f), new Vector2(0.21f, 0.07f), new Vector2(0.79f, 0.25f), Vector2.zero, Vector2.zero);
            Button sceneNextButton = CreateButton("SceneNextButton", statePanel.transform, font, "＞", 18, new Color(0.12f, 0.16f, 0.19f, 0.95f), new Color(0.22f, 0.28f, 0.33f, 1f), new Color(0.06f, 0.09f, 0.11f, 1f), Color.white, new Vector2(0.82f, 0.07f), new Vector2(0.94f, 0.25f));

            GameObject episodeCard = CreatePanel("EpisodeCard", bondCard.transform, new Color(1f, 1f, 1f, 0.92f), new Vector2(0.69f, 0.49f), new Vector2(0.91f, 0.92f), Vector2.zero, Vector2.zero);
            CreatePanel("EpisodeCard_RedCorner", episodeCard.transform, new Color(0.94f, 0.08f, 0.08f, 0.96f), new Vector2(0f, 0f), new Vector2(0.22f, 0.22f), Vector2.zero, Vector2.zero);
            CreateText("EpisodeCardIcon", episodeCard.transform, font, "▣", 36, FontStyle.Bold, TextAnchor.MiddleCenter, Color.white, new Vector2(0f, 0f), new Vector2(0.22f, 0.22f), Vector2.zero, Vector2.zero);
            CreateText("EpisodeCardText", episodeCard.transform, font, "에피소드\n보기", 26, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.35f, 0.35f, 0.38f), new Vector2(0.2f, 0.22f), new Vector2(0.94f, 0.86f), Vector2.zero, Vector2.zero);

            Button giftButton = CreateButton(
                "GiftButton",
                bondCard.transform,
                font,
                "선물하기",
                34,
                new Color(1f, 0.55f, 0.04f, 0.98f),
                new Color(1f, 0.68f, 0.12f, 1f),
                new Color(0.83f, 0.35f, 0.02f, 1f),
                Color.white,
                new Vector2(0.08f, 0.08f),
                new Vector2(0.42f, 0.36f));
            CreateText("GiftIcon", giftButton.transform, font, "□", 42, FontStyle.Bold, TextAnchor.MiddleCenter, Color.white, new Vector2(0.07f, 0.5f), new Vector2(0.3f, 0.9f), Vector2.zero, Vector2.zero);

            Button adviseButton = CreateButton(
                "AdviseButton",
                bondCard.transform,
                font,
                "상담하기",
                31,
                new Color(0.48f, 0.48f, 0.5f, 0.94f),
                new Color(0.62f, 0.62f, 0.64f, 1f),
                new Color(0.33f, 0.33f, 0.35f, 1f),
                new Color(0.94f, 0.94f, 0.95f),
                new Vector2(0.50f, 0.08f),
                new Vector2(0.84f, 0.36f));
            CreateText("AdviseCount", adviseButton.transform, font, "상담 횟수 0/8", 18, FontStyle.Bold, TextAnchor.LowerCenter, new Color(0.96f, 0.96f, 0.96f), new Vector2(0.05f, 0.06f), new Vector2(0.95f, 0.34f), Vector2.zero, Vector2.zero);

            Button statButton = CreateButton(
                "BonusStatButton",
                bondCard.transform,
                font,
                "추가 능력치",
                22,
                new Color(0.96f, 0.12f, 0.1f, 0.95f),
                new Color(1f, 0.25f, 0.18f, 1f),
                new Color(0.72f, 0.03f, 0.03f, 1f),
                Color.white,
                new Vector2(0.69f, 0.37f),
                new Vector2(0.91f, 0.48f));
            statButton.interactable = false;

            Text risk = CreateText("RiskText", bondCard.transform, font, "대기 중", 18, FontStyle.Bold, TextAnchor.MiddleRight, new Color(0.94f, 0.08f, 0.08f), new Vector2(0.70f, 0.40f), new Vector2(0.91f, 0.48f), Vector2.zero, Vector2.zero);

            GameObject adviceOverlay = CreatePanel("AdviceChoiceOverlay", canvasObject.transform, new Color(0f, 0f, 0f, 0.68f), Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            GameObject choiceFrame = CreatePanel("AdviceChoiceFrame", adviceOverlay.transform, new Color(0.015f, 0.026f, 0.035f, 0.88f), new Vector2(0.07f, 0.10f), new Vector2(0.66f, 0.79f), Vector2.zero, Vector2.zero);
            CreatePanel("AdviceChoiceFrame_Top", choiceFrame.transform, new Color(0.08f, 0.42f, 0.62f, 0.95f), new Vector2(0f, 0.96f), new Vector2(1f, 1f), Vector2.zero, Vector2.zero);
            CreateText("AdviceTitle", choiceFrame.transform, font, "상담 선택", 30, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.86f, 0.96f, 1f), new Vector2(0.06f, 0.83f), new Vector2(0.72f, 0.96f), Vector2.zero, Vector2.zero);
            Button closeAdviceButton = CreateButton(
                "CloseAdviceButton",
                choiceFrame.transform,
                font,
                "닫기",
                21,
                new Color(0.18f, 0.24f, 0.28f, 0.94f),
                new Color(0.26f, 0.34f, 0.38f, 1f),
                new Color(0.11f, 0.16f, 0.19f, 1f),
                new Color(0.86f, 0.96f, 1f),
                new Vector2(0.78f, 0.82f),
                new Vector2(0.95f, 0.94f));
            Button adviceAllTabButton = CreateButton("AdviceAllTabButton", choiceFrame.transform, font, "전체", 18, new Color(0.08f, 0.62f, 0.94f, 0.98f), new Color(0.16f, 0.72f, 1f, 1f), new Color(0.03f, 0.42f, 0.66f, 1f), Color.white, new Vector2(0.06f, 0.745f), new Vector2(0.20f, 0.81f));
            Button adviceMissionTabButton = CreateButton("AdviceMissionTabButton", choiceFrame.transform, font, "임무", 18, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.215f, 0.745f), new Vector2(0.355f, 0.81f));
            Button adviceDailyTabButton = CreateButton("AdviceDailyTabButton", choiceFrame.transform, font, "일상", 18, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.37f, 0.745f), new Vector2(0.51f, 0.81f));
            Button adviceMemoryTabButton = CreateButton("AdviceMemoryTabButton", choiceFrame.transform, font, "기억", 18, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.525f, 0.745f), new Vector2(0.665f, 0.81f));
            Button adviceStoryTabButton = CreateButton("AdviceStoryTabButton", choiceFrame.transform, font, "스토리", 18, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.68f, 0.745f), new Vector2(0.82f, 0.81f));
            Button adviceSpecialTabButton = CreateButton("AdviceSpecialTabButton", choiceFrame.transform, font, "특별", 18, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.835f, 0.745f), new Vector2(0.94f, 0.81f));
            Button choiceOneButton = CreateChoiceButton(choiceFrame.transform, font, "임무 상태를 먼저 확인한다.", new Vector2(0.06f, 0.625f), new Vector2(0.94f, 0.715f));
            Button choiceTwoButton = CreateChoiceButton(choiceFrame.transform, font, "오늘 작전 우선순위를 묻는다.", new Vector2(0.06f, 0.515f), new Vector2(0.94f, 0.605f));
            Button choiceThreeButton = CreateChoiceButton(choiceFrame.transform, font, "내 컨디션을 물어본다.", new Vector2(0.06f, 0.405f), new Vector2(0.94f, 0.495f));
            Button choiceFourButton = CreateChoiceButton(choiceFrame.transform, font, "전초기지 생활에 대해 묻는다.", new Vector2(0.06f, 0.295f), new Vector2(0.94f, 0.385f));
            Button choiceFiveButton = CreateChoiceButton(choiceFrame.transform, font, "지금까지 쌓인 기억.", new Vector2(0.06f, 0.185f), new Vector2(0.94f, 0.275f));
            Button choiceSixButton = CreateChoiceButton(choiceFrame.transform, font, "최근 작전의 의미를 묻는다.", new Vector2(0.06f, 0.075f), new Vector2(0.94f, 0.165f));
            Text adviceFooterText = CreateText("AdviceFooter", choiceFrame.transform, font, "현재 조건  호감도 22 · 신뢰 · 챕터 4까지 · 장면 상담 · 전체 6개", 17, FontStyle.Normal, TextAnchor.MiddleLeft, new Color(0.7f, 0.82f, 0.88f), new Vector2(0.06f, 0.01f), new Vector2(0.94f, 0.06f), Vector2.zero, Vector2.zero);
            adviceOverlay.SetActive(false);

            GameObject giftOverlay = CreatePanel("GiftChoiceOverlay", canvasObject.transform, new Color(0f, 0f, 0f, 0.66f), Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            GameObject giftFrame = CreatePanel("GiftChoiceFrame", giftOverlay.transform, new Color(0.96f, 0.97f, 0.96f, 0.98f), new Vector2(0.24f, 0.13f), new Vector2(0.76f, 0.88f), Vector2.zero, Vector2.zero);
            CreatePanel("GiftChoiceFrame_Top", giftFrame.transform, new Color(1f, 0.48f, 0.02f, 0.98f), new Vector2(0f, 0.91f), new Vector2(1f, 1f), Vector2.zero, Vector2.zero);
            Text giftTitleText = CreateText("GiftTitleText", giftFrame.transform, font, "♥ 선물하기", 30, FontStyle.Bold, TextAnchor.MiddleCenter, Color.white, new Vector2(0.18f, 0.915f), new Vector2(0.82f, 0.995f), Vector2.zero, Vector2.zero);
            Button closeGiftButton = CreateButton(
                "CloseGiftButton",
                giftFrame.transform,
                font,
                "×",
                32,
                new Color(1f, 0.48f, 0.02f, 0.98f),
                new Color(1f, 0.6f, 0.14f, 1f),
                new Color(0.8f, 0.32f, 0.02f, 1f),
                Color.white,
                new Vector2(0.91f, 0.915f),
                new Vector2(0.985f, 0.995f));

            GameObject giftPortrait = CreatePanel("GiftRapiPortrait", giftFrame.transform, new Color(0.92f, 0.93f, 0.94f, 1f), new Vector2(0.045f, 0.70f), new Vector2(0.245f, 0.875f), Vector2.zero, Vector2.zero);
            CreateText("GiftPortraitName", giftPortrait.transform, font, "라피", 34, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.23f, 0.23f, 0.26f), new Vector2(0.05f, 0.12f), new Vector2(0.95f, 0.9f), Vector2.zero, Vector2.zero);

            GameObject giftInfo = CreatePanel("GiftRankPreview", giftFrame.transform, new Color(1f, 1f, 1f, 0.98f), new Vector2(0.27f, 0.70f), new Vector2(0.955f, 0.875f), Vector2.zero, Vector2.zero);
            CreateText("GiftTargetName", giftInfo.transform, font, "라피", 30, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.22f, 0.22f, 0.24f), new Vector2(0.05f, 0.53f), new Vector2(0.94f, 0.92f), Vector2.zero, Vector2.zero);
            Text giftRankText = CreateText("GiftRankText", giftInfo.transform, font, "RANK 22  >  RANK 24", 26, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.36f, 0.36f, 0.39f), new Vector2(0.05f, 0.25f), new Vector2(0.78f, 0.55f), Vector2.zero, Vector2.zero);
            Text giftGaugeText = CreateText("GiftGaugeText", giftInfo.transform, font, "22/30", 18, FontStyle.Bold, TextAnchor.MiddleRight, new Color(1f, 0.2f, 0.2f), new Vector2(0.74f, 0.04f), new Vector2(0.95f, 0.24f), Vector2.zero, Vector2.zero);
            CreatePanel("GiftGauge_Back", giftInfo.transform, new Color(0.84f, 0.84f, 0.86f, 0.98f), new Vector2(0.05f, 0.08f), new Vector2(0.95f, 0.13f), Vector2.zero, Vector2.zero);
            CreatePanel("GiftGauge_Fill", giftInfo.transform, new Color(1f, 0.18f, 0.2f, 0.98f), new Vector2(0.05f, 0.08f), new Vector2(0.76f, 0.13f), Vector2.zero, Vector2.zero);

            CreateText("GiftSelectLabel", giftFrame.transform, font, "선물을 선택하세요.", 18, FontStyle.Normal, TextAnchor.MiddleLeft, new Color(0.35f, 0.35f, 0.38f), new Vector2(0.045f, 0.62f), new Vector2(0.25f, 0.67f), Vector2.zero, Vector2.zero);
            Button giftAllTabButton = CreateButton("GiftAllTabButton", giftFrame.transform, font, "모두", 17, new Color(0.08f, 0.62f, 0.94f, 0.98f), new Color(0.16f, 0.72f, 1f, 1f), new Color(0.03f, 0.42f, 0.66f, 1f), Color.white, new Vector2(0.30f, 0.615f), new Vector2(0.43f, 0.67f));
            Button giftFavoriteTabButton = CreateButton("GiftFavoriteTabButton", giftFrame.transform, font, "최애", 17, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.45f, 0.615f), new Vector2(0.58f, 0.67f));
            Button giftPremiumTabButton = CreateButton("GiftPremiumTabButton", giftFrame.transform, font, "고급", 17, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.60f, 0.615f), new Vector2(0.73f, 0.67f));
            Button giftCommonTabButton = CreateButton("GiftCommonTabButton", giftFrame.transform, font, "공용", 17, new Color(0.12f, 0.13f, 0.15f, 0.96f), new Color(0.22f, 0.23f, 0.25f, 1f), new Color(0.06f, 0.07f, 0.08f, 1f), Color.white, new Vector2(0.75f, 0.615f), new Vector2(0.88f, 0.67f));

            GameObject giftGrid = CreatePanel("GiftItemGrid", giftFrame.transform, new Color(1f, 1f, 1f, 0.98f), new Vector2(0.045f, 0.24f), new Vector2(0.955f, 0.60f), Vector2.zero, Vector2.zero);
            Button[] giftItemButtons = new Button[6];
            Text[] giftItemNameLabels = new Text[6];
            Text[] giftItemMetaLabels = new Text[6];
            Image[] giftItemFrames = new Image[6];
            for (int i = 0; i < giftItemButtons.Length; i++)
            {
                float left = 0.035f + i * 0.16f;
                float right = left + 0.13f;
                giftItemButtons[i] = CreateGiftItemButton(giftGrid.transform, font, "GiftItemButton_" + i, new Vector2(left, 0.54f), new Vector2(right, 0.92f), out giftItemNameLabels[i], out giftItemMetaLabels[i], out giftItemFrames[i]);
            }

            Text giftHintText = CreateText("GiftHintText", giftFrame.transform, font, "선물을 선택하면 예상 상승량이 표시됩니다.", 21, FontStyle.Bold, TextAnchor.MiddleLeft, new Color(0.2f, 0.2f, 0.23f), new Vector2(0.055f, 0.13f), new Vector2(0.56f, 0.20f), Vector2.zero, Vector2.zero);
            Button giftConfirmButton = CreateButton(
                "GiftConfirmButton",
                giftFrame.transform,
                font,
                "선물하기",
                27,
                new Color(0.08f, 0.62f, 0.94f, 0.98f),
                new Color(0.16f, 0.72f, 1f, 1f),
                new Color(0.03f, 0.42f, 0.66f, 1f),
                Color.white,
                new Vector2(0.62f, 0.095f),
                new Vector2(0.94f, 0.19f));
            giftOverlay.SetActive(false);

            GameObject dialogueSystem = new GameObject("DialogueSystem");
            RapiDialogueApiClient client = dialogueSystem.AddComponent<RapiDialogueApiClient>();
            client.speakerText = speaker;
            client.lineText = line;
            client.statusText = status;
            client.riskText = risk;
            client.modeText = mode;
            client.rankText = rankText;
            client.stateSummaryText = stateSummaryText;
            client.storyProgressText = storyProgressText;
            client.sceneText = sceneText;
            client.adviceFooterText = adviceFooterText;
            client.nextEpisodeText = nextEpisodeText;
            client.giftButton = giftButton;
            client.adviseButton = adviseButton;
            client.closeAdviceButton = closeAdviceButton;
            client.adviceAllTabButton = adviceAllTabButton;
            client.adviceMissionTabButton = adviceMissionTabButton;
            client.adviceDailyTabButton = adviceDailyTabButton;
            client.adviceMemoryTabButton = adviceMemoryTabButton;
            client.adviceStoryTabButton = adviceStoryTabButton;
            client.adviceSpecialTabButton = adviceSpecialTabButton;
            client.giftOverlay = giftOverlay;
            client.giftTitleText = giftTitleText;
            client.giftRankText = giftRankText;
            client.giftGaugeText = giftGaugeText;
            client.giftHintText = giftHintText;
            client.closeGiftButton = closeGiftButton;
            client.giftAllTabButton = giftAllTabButton;
            client.giftFavoriteTabButton = giftFavoriteTabButton;
            client.giftPremiumTabButton = giftPremiumTabButton;
            client.giftCommonTabButton = giftCommonTabButton;
            client.giftConfirmButton = giftConfirmButton;
            client.giftItemButtons = giftItemButtons;
            client.giftItemNameLabels = giftItemNameLabels;
            client.giftItemMetaLabels = giftItemMetaLabels;
            client.giftItemFrames = giftItemFrames;
            client.choiceButtons = new[] { choiceOneButton, choiceTwoButton, choiceThreeButton, choiceFourButton, choiceFiveButton, choiceSixButton };
            client.choiceButtonLabels = new[]
            {
                choiceOneButton.GetComponentInChildren<Text>(true),
                choiceTwoButton.GetComponentInChildren<Text>(true),
                choiceThreeButton.GetComponentInChildren<Text>(true),
                choiceFourButton.GetComponentInChildren<Text>(true),
                choiceFiveButton.GetComponentInChildren<Text>(true),
                choiceSixButton.GetComponentInChildren<Text>(true)
            };
            client.rankDownButton = rankDownButton;
            client.rankUpButton = rankUpButton;
            client.chapterDownButton = chapterDownButton;
            client.chapterUpButton = chapterUpButton;
            client.scenePrevButton = scenePrevButton;
            client.sceneNextButton = sceneNextButton;
            client.adviceOverlay = adviceOverlay;
            client.characterAnimator = characterAnimator;
            client.autoRequestOnStart = false;

            if (Object.FindAnyObjectByType<EventSystem>() == null)
            {
                GameObject eventSystem = new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
                eventSystem.transform.SetAsLastSibling();
            }
        }

        private static GameObject CreatePanel(string name, Transform parent, Color color, Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPosition, Vector2 sizeDelta)
        {
            GameObject panel = new GameObject(name, typeof(RectTransform), typeof(Image));
            panel.transform.SetParent(parent, false);
            RectTransform rect = panel.GetComponent<RectTransform>();
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = sizeDelta;
            Image image = panel.GetComponent<Image>();
            image.color = color;
            return panel;
        }

        private static Text CreateText(string name, Transform parent, Font font, string value, int size, FontStyle style, TextAnchor alignment, Color color, Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPosition, Vector2 sizeDelta)
        {
            GameObject textObject = new GameObject(name, typeof(RectTransform), typeof(Text));
            textObject.transform.SetParent(parent, false);
            RectTransform rect = textObject.GetComponent<RectTransform>();
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = sizeDelta;

            Text text = textObject.GetComponent<Text>();
            text.font = font;
            text.text = value;
            text.fontSize = size;
            text.fontStyle = style;
            text.alignment = alignment;
            text.color = color;
            text.resizeTextForBestFit = true;
            text.resizeTextMinSize = Mathf.Max(12, size - 10);
            text.resizeTextMaxSize = size;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Truncate;
            return text;
        }

        private static Button CreateGiftItemButton(Transform parent, Font font, string name, Vector2 anchorMin, Vector2 anchorMax, out Text nameLabel, out Text metaLabel, out Image frame)
        {
            Button button = CreateButton(
                name,
                parent,
                font,
                "",
                18,
                new Color(0.88f, 0.88f, 0.9f, 0.98f),
                new Color(1f, 1f, 1f, 1f),
                new Color(0.72f, 0.72f, 0.74f, 1f),
                Color.white,
                anchorMin,
                anchorMax);
            frame = button.GetComponent<Image>();
            CreatePanel("GiftItem_IconPlate", button.transform, new Color(1f, 1f, 1f, 0.84f), new Vector2(0.14f, 0.48f), new Vector2(0.86f, 0.9f), Vector2.zero, Vector2.zero);
            nameLabel = CreateText("GiftItemName", button.transform, font, "선물", 17, FontStyle.Bold, TextAnchor.MiddleCenter, new Color(0.18f, 0.18f, 0.2f), new Vector2(0.05f, 0.46f), new Vector2(0.95f, 0.72f), Vector2.zero, Vector2.zero);
            metaLabel = CreateText("GiftItemMeta", button.transform, font, "+0", 14, FontStyle.Bold, TextAnchor.MiddleCenter, Color.white, new Vector2(0.05f, 0.07f), new Vector2(0.95f, 0.42f), Vector2.zero, Vector2.zero);
            return button;
        }

        private static Button CreateChoiceButton(Transform parent, Font font, string value, Vector2 anchorMin, Vector2 anchorMax)
        {
            Button button = CreateButton(
                value.Replace(" ", "_"),
                parent,
                font,
                value,
                22,
                new Color(0.02f, 0.05f, 0.07f, 0.92f),
                new Color(0.04f, 0.18f, 0.25f, 0.98f),
                new Color(0.01f, 0.03f, 0.04f, 1f),
                Color.white,
                anchorMin,
                anchorMax);
            CreatePanel("Choice_LeftLine", button.transform, new Color(0.1f, 0.48f, 0.72f, 0.98f), new Vector2(0f, 0.1f), new Vector2(0.012f, 0.9f), Vector2.zero, Vector2.zero);
            return button;
        }

        private static Button CreateButton(string name, Transform parent, Font font, string value, Vector2 anchorMin, Vector2 anchorMax)
        {
            return CreateButton(
                name,
                parent,
                font,
                value,
                24,
                new Color(0.86f, 0.06f, 0.08f, 0.95f),
                new Color(1f, 0.18f, 0.2f, 1f),
                new Color(0.58f, 0.02f, 0.04f, 1f),
                Color.white,
                anchorMin,
                anchorMax);
        }

        private static Button CreateButton(string name, Transform parent, Font font, string value, int size, Color normalColor, Color highlightedColor, Color pressedColor, Color textColor, Vector2 anchorMin, Vector2 anchorMax)
        {
            GameObject buttonObject = CreatePanel(name, parent, normalColor, anchorMin, anchorMax, Vector2.zero, Vector2.zero);
            Button button = buttonObject.AddComponent<Button>();
            ColorBlock colors = button.colors;
            colors.normalColor = normalColor;
            colors.highlightedColor = highlightedColor;
            colors.pressedColor = pressedColor;
            colors.disabledColor = new Color(0.18f, 0.18f, 0.2f, 0.65f);
            button.colors = colors;

            CreateText("Label", buttonObject.transform, font, value, size, FontStyle.Bold, TextAnchor.MiddleCenter, textColor, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            return button;
        }

        private static void AddSceneToBuildSettings(string scenePath)
        {
            EditorBuildSettingsScene[] current = EditorBuildSettings.scenes;
            foreach (EditorBuildSettingsScene entry in current)
            {
                if (entry.path == scenePath)
                {
                    entry.enabled = true;
                    EditorBuildSettings.scenes = current;
                    return;
                }
            }

            EditorBuildSettingsScene[] next = new EditorBuildSettingsScene[current.Length + 1];
            for (int i = 0; i < current.Length; i++)
            {
                next[i] = current[i];
            }

            next[next.Length - 1] = new EditorBuildSettingsScene(scenePath, true);
            EditorBuildSettings.scenes = next;
        }

        private static void LookAt(Transform transform, Vector3 target)
        {
            Vector3 direction = target - transform.position;
            if (direction.sqrMagnitude > 0.001f)
            {
                transform.rotation = Quaternion.LookRotation(direction.normalized, Vector3.up);
            }
        }
    }
}
