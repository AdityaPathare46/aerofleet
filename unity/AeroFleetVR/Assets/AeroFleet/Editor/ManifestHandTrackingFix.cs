using System.IO;
using System.Xml;
using UnityEditor;
using UnityEditor.Android;

public class ManifestHandTrackingFix : IPostGenerateGradleAndroidProject
{
    public int callbackOrder { get { return 1; } }

    public void OnPostGenerateGradleAndroidProject(string path)
    {
        string manifestPath = path + "/src/main/AndroidManifest.xml";
        
        XmlDocument doc = new XmlDocument();
        doc.Load(manifestPath);

        XmlElement manifestNode = doc.DocumentElement;
        XmlNode applicationNode = manifestNode.SelectSingleNode("application");

        // Add the Hand Tracking Permission
        XmlElement permissionElement = doc.CreateElement("uses-permission");
        permissionElement.SetAttribute("name", "http://schemas.android.com/apk/res/android", "com.oculus.permission.HAND_TRACKING");
        manifestNode.InsertBefore(permissionElement, applicationNode);

        // Add the Hand Tracking Feature (Required = false, so it allows both controllers and hands)
        XmlElement featureElement = doc.CreateElement("uses-feature");
        featureElement.SetAttribute("name", "http://schemas.android.com/apk/res/android", "oculus.software.handtracking");
        featureElement.SetAttribute("required", "http://schemas.android.com/apk/res/android", "false");
        manifestNode.InsertBefore(featureElement, applicationNode);

        doc.Save(manifestPath);
        UnityEngine.Debug.Log("Successfully injected Quest Hand Tracking permissions into AndroidManifest.xml!");
    }
}
