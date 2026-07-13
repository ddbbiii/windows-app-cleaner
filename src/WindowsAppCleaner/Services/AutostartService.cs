using Microsoft.Win32;

namespace WindowsAppCleaner.Services;

public sealed class AutostartService
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "WindowsAppCleaner";

    public bool IsEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey);
        return key?.GetValue(ValueName) is string value && !string.IsNullOrWhiteSpace(value);
    }

    public void SetEnabled(bool enabled)
    {
        using var key = Registry.CurrentUser.CreateSubKey(RunKey, true);
        if (enabled) key.SetValue(ValueName, $"\"{Environment.ProcessPath}\" --minimized", RegistryValueKind.String);
        else key.DeleteValue(ValueName, false);
        RemoveLegacyStartupFile();
    }

    public static void RemoveLegacyStartupFile()
    {
        var startup = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Startup), "desktop-app-cleaner.vbs");
        if (!File.Exists(startup)) return;
        try
        {
            var content = File.ReadAllText(startup);
            if (content.Contains("main.py", StringComparison.OrdinalIgnoreCase) || content.Contains("pythonw", StringComparison.OrdinalIgnoreCase))
                File.Delete(startup);
        }
        catch { }
    }
}
