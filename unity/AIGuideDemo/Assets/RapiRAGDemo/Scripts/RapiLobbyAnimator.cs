using System.Collections;
using UnityEngine;

namespace RapiRAGDemo
{
    [DisallowMultipleComponent]
    public class RapiLobbyAnimator : MonoBehaviour
    {
        public Transform modelRoot;
        public Light emotionLight;
        public Renderer[] accentRenderers;

        [Header("Idle")]
        public float idleYawDegrees = 1.4f;
        public float idleBobAmount = 0.015f;
        public float idleSpeed = 0.75f;

        [Header("Pose")]
        public bool useNaturalPose = true;
        [Range(0f, 1f)] public float naturalPoseWeight = 1f;
        public float armDropDegrees = 30f;
        public float breathingDegrees = 1.1f;

        [Header("Interaction Hitbox")]
        public bool ensureInteractionHitbox = true;
        public Vector3 hitboxCenter = new Vector3(0f, 2.05f, 0f);
        public float hitboxRadius = 0.48f;
        public float hitboxHeight = 4.1f;

        private Vector3 baseLocalPosition;
        private Quaternion baseLocalRotation;
        private Vector3 motionLocalOffset;
        private Quaternion motionLocalRotation = Quaternion.identity;
        private SkinnedMeshRenderer[] skinnedMeshes;
        private LocalPoseBone[] localPoseBones;
        private ArmPose[] armPoses;
        private Coroutine motionRoutine;
        private MaterialPropertyBlock accentProperties;

        private void Awake()
        {
            if (modelRoot == null)
            {
                modelRoot = transform;
            }

            baseLocalPosition = modelRoot.localPosition;
            baseLocalRotation = modelRoot.localRotation;
            skinnedMeshes = modelRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            CachePoseBones();
            EnsureInteractionHitbox();
            ApplyTags("neutral", "idle");
        }

        private void Update()
        {
            if (modelRoot == null)
            {
                return;
            }

            float time = Time.time * idleSpeed;
            Vector3 bob = Vector3.up * (Mathf.Sin(time * 2.1f) * idleBobAmount);
            Quaternion yaw = Quaternion.Euler(0f, Mathf.Sin(time) * idleYawDegrees, 0f);
            modelRoot.localPosition = baseLocalPosition + bob + motionLocalOffset;
            modelRoot.localRotation = baseLocalRotation * yaw * motionLocalRotation;

            ApplyNaturalPose(time);
        }

        public void ApplyTags(string emotion, string motion)
        {
            ApplyEmotion(emotion);

            if (motionRoutine != null)
            {
                StopCoroutine(motionRoutine);
            }

            motionLocalOffset = Vector3.zero;
            motionLocalRotation = Quaternion.identity;

            if (motion == "nod")
            {
                motionRoutine = StartCoroutine(NodRoutine());
            }
            else if (motion == "look_away")
            {
                motionRoutine = StartCoroutine(LookAwayRoutine());
            }
            else if (motion == "salute" || motion == "battle_ready")
            {
                motionRoutine = StartCoroutine(EmphasisRoutine());
            }
        }

        private void CachePoseBones()
        {
            if (modelRoot == null)
            {
                localPoseBones = new LocalPoseBone[0];
                armPoses = new ArmPose[0];
                return;
            }

            localPoseBones = new[]
            {
                new LocalPoseBone(FindBone("上半身", "Spine", "spine"), new Vector3(-1.0f, 0f, 0f), new Vector3(0.25f, 0f, 0.15f), 0.0f),
                new LocalPoseBone(FindBone("上半身2", "Chest", "UpperChest", "chest"), new Vector3(-1.6f, 0f, 0f), new Vector3(0.45f, 0.15f, 0.2f), 0.4f),
                new LocalPoseBone(FindBone("首", "Neck", "neck"), new Vector3(0.8f, 0f, 0f), new Vector3(0.45f, 0.25f, 0.15f), 0.9f),
                new LocalPoseBone(FindBone("頭", "Head", "head"), new Vector3(0.4f, 0f, 0f), new Vector3(0.35f, 0.35f, 0.12f), 1.2f)
            };

            armPoses = new[]
            {
                new ArmPose(
                    FindBone("腕.L", "UpperArm.L", "LeftUpperArm", "Left Arm", "L UpperArm"),
                    FindBone("ひじ.L", "ForeArm.L", "LowerArm.L", "LeftLowerArm", "Left ForeArm", "L ForeArm"),
                    FindBone("手首.L", "Hand.L", "Wrist.L", "LeftHand", "Left Wrist", "L Hand"),
                    -1),
                new ArmPose(
                    FindBone("腕.R", "UpperArm.R", "RightUpperArm", "Right Arm", "R UpperArm"),
                    FindBone("ひじ.R", "ForeArm.R", "LowerArm.R", "RightLowerArm", "Right ForeArm", "R ForeArm"),
                    FindBone("手首.R", "Hand.R", "Wrist.R", "RightHand", "Right Wrist", "R Hand"),
                    1)
            };
        }

        private void ApplyNaturalPose(float time)
        {
            if (!useNaturalPose || naturalPoseWeight <= 0f)
            {
                return;
            }

            float breath = Mathf.Sin(time * 1.45f);
            float weight = Mathf.Clamp01(naturalPoseWeight);

            foreach (LocalPoseBone bone in localPoseBones)
            {
                if (!bone.IsValid)
                {
                    continue;
                }

                Vector3 idle = bone.IdleEuler * (Mathf.Sin(time * 1.45f + bone.Phase) * breathingDegrees);
                bone.Transform.localRotation = bone.BaseRotation * Quaternion.Euler((bone.RestEuler + idle) * weight);
            }

            foreach (ArmPose arm in armPoses)
            {
                ApplyArmPose(arm, weight, breath);
            }
        }

        private void ApplyArmPose(ArmPose arm, float weight, float breath)
        {
            if (!arm.IsValid || modelRoot == null)
            {
                return;
            }

            arm.Reset();

            Vector3 upperDirection = arm.LowerArm.position - arm.UpperArm.position;
            if (upperDirection.sqrMagnitude <= 0.0001f)
            {
                return;
            }

            Vector3 localDirection = modelRoot.InverseTransformDirection(upperDirection.normalized);
            float relaxedDrop = armDropDegrees + breath * 1.5f;
            localDirection = Quaternion.AngleAxis(-arm.SideSign * relaxedDrop * weight, Vector3.forward) * localDirection;

            Vector3 targetDirection = modelRoot.TransformDirection(localDirection.normalized);
            arm.UpperArm.rotation = Quaternion.FromToRotation(upperDirection.normalized, targetDirection) * arm.UpperArm.rotation;

            float lowerArmSoftness = arm.SideSign * (5f + breath * 0.6f) * weight;
            arm.LowerArm.localRotation = arm.LowerArm.localRotation * Quaternion.Euler(0f, 0f, lowerArmSoftness);
        }

        private Transform FindBone(params string[] names)
        {
            if (modelRoot == null || names == null)
            {
                return null;
            }

            Transform[] transforms = modelRoot.GetComponentsInChildren<Transform>(true);

            foreach (string targetName in names)
            {
                if (string.IsNullOrEmpty(targetName))
                {
                    continue;
                }

                foreach (Transform candidate in transforms)
                {
                    if (candidate.name == targetName)
                    {
                        return candidate;
                    }
                }
            }

            foreach (string targetName in names)
            {
                if (string.IsNullOrEmpty(targetName))
                {
                    continue;
                }

                foreach (Transform candidate in transforms)
                {
                    if (candidate.name.EndsWith(targetName))
                    {
                        return candidate;
                    }
                }
            }

            return null;
        }

        private void EnsureInteractionHitbox()
        {
            if (!ensureInteractionHitbox)
            {
                return;
            }

            CapsuleCollider hitbox = GetComponent<CapsuleCollider>();
            if (hitbox == null)
            {
                hitbox = gameObject.AddComponent<CapsuleCollider>();
            }

            hitbox.isTrigger = true;
            hitbox.direction = 1;
            hitbox.center = hitboxCenter;
            hitbox.radius = hitboxRadius;
            hitbox.height = hitboxHeight;
        }

        private void ApplyEmotion(string emotion)
        {
            ResetBlendShapes();

            Color lightColor = new Color(0.8f, 0.95f, 1f);
            float intensity = 1.0f;

            switch (emotion)
            {
                case "soft_smile":
                case "gentle":
                case "relieved":
                    SetBlendShapeByKeywords(35f, "smile", "happy", "笑", "にこ");
                    lightColor = new Color(1f, 0.82f, 0.72f);
                    intensity = 1.35f;
                    break;
                case "embarrassed":
                    SetBlendShapeByKeywords(45f, "blush", "照", "赤", "embarrass");
                    SetBlendShapeByKeywords(25f, "smile", "笑");
                    lightColor = new Color(1f, 0.52f, 0.58f);
                    intensity = 1.45f;
                    break;
                case "worried":
                    SetBlendShapeByKeywords(40f, "sad", "worry", "困", "不安");
                    lightColor = new Color(0.62f, 0.78f, 1f);
                    intensity = 1.2f;
                    break;
                case "stern":
                case "determined":
                    SetBlendShapeByKeywords(30f, "angry", "serious", "怒", "きり");
                    lightColor = new Color(1f, 0.38f, 0.32f);
                    intensity = 1.55f;
                    break;
            }

            if (emotionLight != null)
            {
                emotionLight.color = lightColor;
                emotionLight.intensity = intensity;
            }

            if (accentRenderers == null)
            {
                return;
            }

            foreach (Renderer accent in accentRenderers)
            {
                if (accent == null || accent.sharedMaterial == null)
                {
                    continue;
                }

                if (accentProperties == null) accentProperties = new MaterialPropertyBlock();
                accent.GetPropertyBlock(accentProperties);
                accentProperties.SetColor("_EmissionColor", lightColor * 1.8f);
                accent.SetPropertyBlock(accentProperties);
            }
        }

        private void ResetBlendShapes()
        {
            if (skinnedMeshes == null)
            {
                return;
            }

            foreach (SkinnedMeshRenderer mesh in skinnedMeshes)
            {
                Mesh sharedMesh = mesh.sharedMesh;
                if (sharedMesh == null)
                {
                    continue;
                }

                for (int i = 0; i < sharedMesh.blendShapeCount; i++)
                {
                    mesh.SetBlendShapeWeight(i, 0f);
                }
            }
        }

        private void SetBlendShapeByKeywords(float weight, params string[] keywords)
        {
            if (skinnedMeshes == null)
            {
                return;
            }

            foreach (SkinnedMeshRenderer mesh in skinnedMeshes)
            {
                Mesh sharedMesh = mesh.sharedMesh;
                if (sharedMesh == null)
                {
                    continue;
                }

                for (int i = 0; i < sharedMesh.blendShapeCount; i++)
                {
                    string shapeName = sharedMesh.GetBlendShapeName(i).ToLowerInvariant();
                    foreach (string keyword in keywords)
                    {
                        if (!string.IsNullOrEmpty(keyword) && shapeName.Contains(keyword.ToLowerInvariant()))
                        {
                            mesh.SetBlendShapeWeight(i, weight);
                            break;
                        }
                    }
                }
            }
        }

        private IEnumerator NodRoutine()
        {
            float duration = 0.5f;
            for (float t = 0f; t < duration; t += Time.deltaTime)
            {
                float curve = Mathf.Sin((t / duration) * Mathf.PI);
                motionLocalRotation = Quaternion.Euler(curve * 5f, 0f, 0f);
                yield return null;
            }

            motionLocalRotation = Quaternion.identity;
        }

        private IEnumerator LookAwayRoutine()
        {
            float duration = 1.2f;
            for (float t = 0f; t < duration; t += Time.deltaTime)
            {
                float curve = Mathf.Sin((t / duration) * Mathf.PI);
                motionLocalRotation = Quaternion.Euler(0f, curve * -9f, 0f);
                yield return null;
            }

            motionLocalRotation = Quaternion.identity;
        }

        private IEnumerator EmphasisRoutine()
        {
            float duration = 0.45f;
            for (float t = 0f; t < duration; t += Time.deltaTime)
            {
                float curve = Mathf.Sin((t / duration) * Mathf.PI);
                motionLocalOffset = Vector3.forward * (curve * 0.06f);
                yield return null;
            }

            motionLocalOffset = Vector3.zero;
        }

        private class LocalPoseBone
        {
            public readonly Transform Transform;
            public readonly Quaternion BaseRotation;
            public readonly Vector3 RestEuler;
            public readonly Vector3 IdleEuler;
            public readonly float Phase;

            public bool IsValid
            {
                get { return Transform != null; }
            }

            public LocalPoseBone(Transform transform, Vector3 restEuler, Vector3 idleEuler, float phase)
            {
                Transform = transform;
                BaseRotation = transform != null ? transform.localRotation : Quaternion.identity;
                RestEuler = restEuler;
                IdleEuler = idleEuler;
                Phase = phase;
            }
        }

        private class ArmPose
        {
            public readonly Transform UpperArm;
            public readonly Transform LowerArm;
            public readonly Transform Hand;
            public readonly int SideSign;

            private readonly Quaternion upperBaseRotation;
            private readonly Quaternion lowerBaseRotation;
            private readonly Quaternion handBaseRotation;

            public bool IsValid
            {
                get { return UpperArm != null && LowerArm != null; }
            }

            public ArmPose(Transform upperArm, Transform lowerArm, Transform hand, int sideSign)
            {
                UpperArm = upperArm;
                LowerArm = lowerArm;
                Hand = hand;
                SideSign = sideSign;
                upperBaseRotation = upperArm != null ? upperArm.localRotation : Quaternion.identity;
                lowerBaseRotation = lowerArm != null ? lowerArm.localRotation : Quaternion.identity;
                handBaseRotation = hand != null ? hand.localRotation : Quaternion.identity;
            }

            public void Reset()
            {
                UpperArm.localRotation = upperBaseRotation;
                LowerArm.localRotation = lowerBaseRotation;

                if (Hand != null)
                {
                    Hand.localRotation = handBaseRotation;
                }
            }
        }
    }
}
