using System;
using System.Collections.Generic;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR;

namespace AeroFleet.VR.Interaction
{
    /// <summary>
    /// Point-and-trigger for both hands in the headset. The XRI starter rig maps "select" to the grip
    /// button, so boards and drones never responded to the trigger (found in the first Quest test);
    /// this pointer reads the controllers' aim pose and the trigger directly — or a pinch with hand
    /// tracking — and drives the same Clickable components the mouse uses on the desktop.
    /// A ray and a hit dot show what you're pointing at; a short haptic tick confirms a click.
    /// </summary>
    public class VrPointer : MonoBehaviour
    {
        public const float MaxDistance = 12f;

        class Hand
        {
            public XRNode Node;
            public InputAction Position, Rotation, Press;
            public LineRenderer Ray;
            public Transform Dot;
            public Clickable Hovered;
            public bool WasDown;
        }

        readonly List<Hand> hands = new List<Hand>();
        Transform trackingSpace;

        void Start()
        {
            var origin = FindFirstObjectByType<XROrigin>();
            trackingSpace = origin != null && origin.CameraFloorOffsetObject != null ? origin.CameraFloorOffsetObject.transform
                          : origin != null ? origin.transform : null;
            DisableRigInteractors();
            hands.Add(MakeHand(XRNode.LeftHand, "LeftHand"));
            hands.Add(MakeHand(XRNode.RightHand, "RightHand"));
        }

        /// <summary>The starter rig's near/far interactors would draw a second ray per hand and grab
        /// with the grip — switch them off; locomotion (thumbstick move/turn) stays.</summary>
        static void DisableRigInteractors()
        {
            foreach (var b in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
            {
                string n = b.GetType().Name;
                if (n == "NearFarInteractor" || n == "XRRayInteractor" || n == "XRPokeInteractor" || n == "XRDirectInteractor")
                    b.gameObject.SetActive(false);
            }
        }

        static InputAction Action(string name, InputActionType type, params string[] bindings)
        {
            var a = new InputAction(name, type);
            foreach (var b in bindings) a.AddBinding(b);
            a.Enable();
            return a;
        }

        Hand MakeHand(XRNode node, string side)
        {
            var h = new Hand
            {
                Node = node,
                // Aim pose first (controllers, then the hand-interaction profile), device pose as a fallback.
                Position = Action(side + "AimPos", InputActionType.Value,
                    $"<XRController>{{{side}}}/pointerPosition", $"<HandInteraction>{{{side}}}/pointerPosition",
                    $"<XRController>{{{side}}}/devicePosition"),
                Rotation = Action(side + "AimRot", InputActionType.Value,
                    $"<XRController>{{{side}}}/pointerRotation", $"<HandInteraction>{{{side}}}/pointerRotation",
                    $"<XRController>{{{side}}}/deviceRotation"),
                Press = Action(side + "Press", InputActionType.Button,
                    $"<XRController>{{{side}}}/{{TriggerButton}}", $"<HandInteraction>{{{side}}}/pointerActivated"),
            };
            var go = new GameObject(side + " Pointer");
            go.transform.SetParent(transform, false);
            h.Ray = go.AddComponent<LineRenderer>();
            h.Ray.useWorldSpace = true;
            h.Ray.positionCount = 2;
            h.Ray.widthMultiplier = 0.004f;
            h.Ray.numCapVertices = 2;
            h.Ray.sharedMaterial = View.Draw.Unlit(Color.white);
            h.Ray.startColor = View.Palette.WithAlpha(View.Palette.Accent, 0.9f);
            h.Ray.endColor = View.Palette.WithAlpha(View.Palette.Accent, 0.1f);
            h.Ray.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            h.Dot = View.Draw.Prim(PrimitiveType.Sphere, go.transform, Vector3.zero, Vector3.one * 0.012f,
                                   View.Draw.Solid(View.Palette.Text), "Dot").transform;
            return h;
        }

        void Update()
        {
            foreach (var h in hands) Tick(h);
        }

        void Tick(Hand h)
        {
            Quaternion q = h.Rotation.ReadValue<Quaternion>();
            bool tracked = q != default && Mathf.Abs(q.w) + Mathf.Abs(q.x) + Mathf.Abs(q.y) + Mathf.Abs(q.z) > 0.1f;
            h.Ray.enabled = tracked;
            h.Dot.gameObject.SetActive(false);
            if (!tracked) { SetHover(h, null); return; }

            Vector3 p = h.Position.ReadValue<Vector3>();
            Vector3 origin = trackingSpace != null ? trackingSpace.TransformPoint(p) : p;
            Vector3 dir = (trackingSpace != null ? trackingSpace.rotation * q : q) * Vector3.forward;

            bool hit = Physics.Raycast(origin, dir, out var info, MaxDistance, ~0, QueryTriggerInteraction.Ignore);
            Vector3 end = hit ? info.point : origin + dir * 3f;
            h.Ray.SetPosition(0, origin);
            h.Ray.SetPosition(1, end);
            var clickable = hit ? info.collider.GetComponentInParent<Clickable>() : null;
            SetHover(h, clickable);
            if (hit)
            {
                h.Dot.gameObject.SetActive(true);
                h.Dot.position = info.point;
            }

            bool down = h.Press.IsPressed();
            if (down && !h.WasDown && clickable != null)
            {
                Press(clickable, info.point);
                Haptic(h.Node);
            }
            h.WasDown = down;
        }

        public static void Press(Clickable c, Vector3 point)
        {
            c.OnClick?.Invoke();
            c.OnClickAt?.Invoke(point);
        }

        static void SetHover(Hand h, Clickable c)
        {
            if (c == h.Hovered) return;
            h.Hovered?.OnHover?.Invoke(false);
            h.Hovered = c;
            h.Hovered?.OnHover?.Invoke(true);
        }

        static void Haptic(XRNode node)
        {
            var device = InputDevices.GetDeviceAtXRNode(node);
            if (device.isValid) device.SendHapticImpulse(0, 0.35f, 0.04f);
        }

        void OnDestroy()
        {
            foreach (var h in hands) { h.Position.Dispose(); h.Rotation.Dispose(); h.Press.Dispose(); }
        }

        // ── for verification without a headset (editor/tests) ─────────────────────────────

        /// <summary>Cast from a world-space ray exactly as a controller would, optionally "pressing".</summary>
        public static Clickable ClickAlong(Vector3 origin, Vector3 dir, bool press)
        {
            if (!Physics.Raycast(origin, dir, out var info, MaxDistance, ~0, QueryTriggerInteraction.Ignore)) return null;
            var c = info.collider.GetComponentInParent<Clickable>();
            if (press && c != null) Press(c, info.point);
            return c;
        }
    }
}
