using UnityEngine;
using UnityEngine.InputSystem;

namespace AeroFleet.VR.Interaction
{
    /// <summary>Orbit/zoom a camera around the table when running without a headset.</summary>
    public class DesktopOrbit : MonoBehaviour
    {
        public Vector3 target = new Vector3(0f, 0.9f, 0.8f);
        public float distance = 1.7f, yaw = 0f, pitch = 38f;

        void LateUpdate()
        {
            var mouse = Mouse.current;
            if (mouse != null)
            {
                if (mouse.rightButton.isPressed)
                {
                    Vector2 d = mouse.delta.ReadValue();
                    yaw += d.x * 0.25f;
                    pitch = Mathf.Clamp(pitch - d.y * 0.25f, 8f, 85f);
                }
                float scroll = mouse.scroll.ReadValue().y;
                if (Mathf.Abs(scroll) > 0.01f) distance = Mathf.Clamp(distance * (scroll > 0 ? 0.9f : 1.1f), 0.35f, 4f);
            }
            Quaternion rot = Quaternion.Euler(pitch, yaw, 0f);
            transform.position = target + rot * new Vector3(0f, 0f, -distance);
            transform.rotation = rot;
        }
    }
}
