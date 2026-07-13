namespace WindowsAppCleaner.Services;

public static class ProtectedAppPolicy
{
    private static readonly HashSet<string> ProtectedNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "WindowsAppCleaner.exe", "dwm.exe", "winlogon.exe", "csrss.exe", "lsass.exe", "services.exe",
        "svchost.exe", "smss.exe", "fontdrvhost.exe", "ShellExperienceHost.exe", "StartMenuExperienceHost.exe",
        "SearchHost.exe", "sihost.exe", "taskhostw.exe", "TextInputHost.exe", "ApplicationFrameHost.exe",
    };

    public static bool IsProtected(string processName) => ProtectedNames.Contains(processName);
    public static bool IsForceProtected(string processName) => IsProtected(processName) ||
        processName.Equals("explorer.exe", StringComparison.OrdinalIgnoreCase);
}
