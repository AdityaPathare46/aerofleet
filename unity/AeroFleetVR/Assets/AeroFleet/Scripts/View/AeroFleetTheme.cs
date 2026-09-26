using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    [CreateAssetMenu(menuName = "AeroFleet/Theme")]
    public class AeroFleetTheme : ScriptableObject
    {
        [Tooltip("URP/Lit — solid geometry")] public Material lit;
        [Tooltip("Sprites/Default — unlit, vertex-coloured, alpha-blended (lines, volumes, overlays)")] public Material unlit;
        [Tooltip("URP/Unlit, opaque — panel backgrounds and bars (writes depth, so text in front never mis-sorts)")] public Material solid;
        public TMP_FontAsset font;
    }
}
