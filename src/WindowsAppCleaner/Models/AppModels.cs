using System.Text.Json.Serialization;

namespace WindowsAppCleaner.Models;

public enum AppScope { Foreground, Background }
public enum CleanupStatus { Closed, PendingConfirmation, ForceClosed, Protected, AccessDenied, Failed }

public sealed class AppSnapshot
{
    public required string Id { get; init; }
    public required string ProcessName { get; init; }
    public string ExePath { get; init; } = "";
    public string DisplayTitle { get; set; } = "";
    public HashSet<int> ProcessIds { get; } = [];
    public List<nint> ForegroundWindows { get; } = [];
    public List<nint> BackgroundWindows { get; } = [];
    public bool IsProtected { get; set; }
    public bool IdentityConfirmed { get; set; } = true;
    public bool HasForeground => ForegroundWindows.Count > 0;
    public bool HasBackground => BackgroundWindows.Count > 0;
}

public sealed record ProcessIdentity(int ProcessId, long StartTimeUtcTicks, string ExePath);

public sealed class CleanupItemResult
{
    public required AppSnapshot App { get; init; }
    public required AppScope Scope { get; init; }
    public CleanupStatus Status { get; set; }
    public string Message { get; set; } = "";
    public List<ProcessIdentity> CapturedProcesses { get; } = [];
    public List<nint> TargetWindows { get; } = [];
}

public sealed class CleanupBatchResult
{
    public List<CleanupItemResult> Items { get; } = [];
    public int ClosedCount => Items.Count(x => x.Status is CleanupStatus.Closed or CleanupStatus.ForceClosed);
    public int PendingCount => Items.Count(x => x.Status == CleanupStatus.PendingConfirmation);
    public int FailureCount => Items.Count(x => x.Status is CleanupStatus.AccessDenied or CleanupStatus.Failed);
    public int ProtectedCount => Items.Count(x => x.Status == CleanupStatus.Protected);
}

public sealed class CleanerConfig
{
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; } = 2;
    [JsonPropertyName("hotkey")] public HotkeyConfig Hotkey { get; set; } = new();
    [JsonPropertyName("allowlist_process_names")] public List<string> AllowlistProcessNames { get; set; } = [];
    [JsonPropertyName("autostart_enabled")] public bool AutostartEnabled { get; set; }
    [JsonPropertyName("minimize_to_tray_on_launch")] public bool MinimizeToTrayOnLaunch { get; set; } = true;
    [JsonPropertyName("cleanup_mode")] public string CleanupMode { get; set; } = "foreground_and_background";
    [JsonPropertyName("floating_position")] public FloatingPositionConfig? FloatingPosition { get; set; }
    [JsonPropertyName("hide_in_fullscreen")] public bool HideInFullscreen { get; set; } = true;
}

public sealed class HotkeyConfig
{
    [JsonPropertyName("modifiers")] public uint Modifiers { get; set; }
    [JsonPropertyName("vk")] public uint VirtualKey { get; set; } = 0x73;
    [JsonPropertyName("display")] public string Display { get; set; } = "F4";
}

public sealed class FloatingPositionConfig
{
    [JsonPropertyName("device_name")] public string DeviceName { get; set; } = "";
    [JsonPropertyName("x_px")] public int X { get; set; }
    [JsonPropertyName("y_px")] public int Y { get; set; }
}
