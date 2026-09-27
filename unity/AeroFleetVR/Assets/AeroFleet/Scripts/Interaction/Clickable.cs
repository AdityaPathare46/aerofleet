using System;
using UnityEngine;

namespace AeroFleet.VR.Interaction
{
    /// <summary>
    /// Anything the operator can point at and press: drones, board buttons, depots. Driven by
    /// VrPointer in the headset (controller trigger or hand pinch) and DesktopPointer with a mouse,
    /// so the same scene works either way. Needs a collider for the ray to hit.
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class Clickable : MonoBehaviour
    {
        public Action OnClick;
        /// <summary>Same press, with where the ray hit (world space) — the table surface uses it to drop a destination.</summary>
        public Action<Vector3> OnClickAt;
        public Action<bool> OnHover;
    }
}
