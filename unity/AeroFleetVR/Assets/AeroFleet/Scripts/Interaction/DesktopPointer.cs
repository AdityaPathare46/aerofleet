using UnityEngine;
using UnityEngine.InputSystem;

namespace AeroFleet.VR.Interaction
{
    /// <summary>Mouse picking for Clickables when no headset is active.</summary>
    public class DesktopPointer : MonoBehaviour
    {
        Clickable hovered;

        void Update()
        {
            var cam = Camera.main;
            var mouse = Mouse.current;
            if (cam == null || mouse == null) return;

            Ray ray = cam.ScreenPointToRay(mouse.position.ReadValue());
            Clickable hit = null;
            if (Physics.Raycast(ray, out var info, 20f)) hit = info.collider.GetComponentInParent<Clickable>();

            if (hit != hovered)
            {
                hovered?.OnHover?.Invoke(false);
                hovered = hit;
                hovered?.OnHover?.Invoke(true);
            }
            if (hovered != null && mouse.leftButton.wasPressedThisFrame) hovered.OnClick?.Invoke();
        }
    }
}
