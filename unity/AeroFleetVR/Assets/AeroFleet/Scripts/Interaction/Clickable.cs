using System;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AeroFleet.VR.Interaction
{
    /// <summary>
    /// Anything the operator can point at and press: drones, board buttons. Works with Quest
    /// controller rays / hands (XR Interaction Toolkit) and with the mouse (DesktopPointer), so the
    /// same scene is usable in the editor and on the desktop mirror without a headset.
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class Clickable : MonoBehaviour
    {
        public Action OnClick;
        public Action<bool> OnHover;

        void Awake()
        {
            var xr = gameObject.AddComponent<XRSimpleInteractable>();
            xr.selectEntered.AddListener(_ => OnClick?.Invoke());
            xr.hoverEntered.AddListener(_ => OnHover?.Invoke(true));
            xr.hoverExited.AddListener(_ => OnHover?.Invoke(false));
        }
    }
}
