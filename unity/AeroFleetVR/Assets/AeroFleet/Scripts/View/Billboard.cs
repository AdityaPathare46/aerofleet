using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>Keeps a label facing the viewer (headset or desktop camera).</summary>
    public class Billboard : MonoBehaviour
    {
        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            Vector3 d = transform.position - cam.transform.position;
            if (d.sqrMagnitude > 1e-8f) transform.rotation = Quaternion.LookRotation(d, Vector3.up);
        }
    }
}
