using System.Diagnostics;
using System.Text.Json;
using WindowsAppCleaner.Models;
using WindowsAppCleaner.Services;

namespace WindowsAppCleaner.Tests;

public sealed class SafetyTests
{
    [Fact]
    public void ExplorerAllowsWindowCloseButNeverForceClose()
    {
        Assert.False(ProtectedAppPolicy.IsProtected("explorer.exe"));
        Assert.True(ProtectedAppPolicy.IsForceProtected("explorer.exe"));
        Assert.True(ProtectedAppPolicy.IsProtected("dwm.exe"));
    }

    [Fact]
    public void RevalidatesPidStartTimeAndPath()
    {
        using var process = Process.GetCurrentProcess();
        var path = process.MainModule!.FileName!;
        var valid = new ProcessIdentity(process.Id, process.StartTime.ToUniversalTime().Ticks, path);
        var stale = valid with { StartTimeUtcTicks = valid.StartTimeUtcTicks - 1 };
        Assert.True(CleanupService.IsSameProcessAlive(valid));
        Assert.False(CleanupService.IsSameProcessAlive(stale));
    }

    [Fact]
    public void KeepsStableSnakeCaseConfigContract()
    {
        var json = JsonSerializer.Serialize(new CleanerConfig());
        Assert.Contains("schema_version", json);
        Assert.Contains("allowlist_process_names", json);
        Assert.Contains("floating_position", json);
        Assert.Contains("hide_in_fullscreen", json);
    }
}
