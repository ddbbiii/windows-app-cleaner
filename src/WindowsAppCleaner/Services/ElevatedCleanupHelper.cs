using System.Diagnostics;
using System.Text.Json;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public static class ElevatedCleanupHelper
{
    public static async Task<bool> RunElevatedAsync(IEnumerable<CleanupItemResult> items, string directory)
    {
        var request = items.SelectMany(x => x.CapturedProcesses).Distinct().ToList();
        if (request.Count == 0) return true;
        Directory.CreateDirectory(directory);
        var path = Path.Combine(directory, "force-" + Guid.NewGuid().ToString("N") + ".json");
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(request));
        try
        {
            var process = Process.Start(new ProcessStartInfo
            {
                FileName = Environment.ProcessPath!,
                Arguments = $"--elevated-force \"{path}\"",
                UseShellExecute = true,
                Verb = "runas",
            });
            if (process is null) return false;
            await process.WaitForExitAsync();
            return process.ExitCode == 0;
        }
        catch { return false; }
        finally { try { File.Delete(path); } catch { } }
    }

    public static int Execute(string requestPath)
    {
        try
        {
            var identities = JsonSerializer.Deserialize<List<ProcessIdentity>>(File.ReadAllText(requestPath)) ?? [];
            foreach (var identity in identities)
            {
                if (!CleanupService.IsSameProcessAlive(identity)) continue;
                var name = Path.GetFileName(identity.ExePath);
                if (ProtectedAppPolicy.IsForceProtected(name)) continue;
                using var process = Process.GetProcessById(identity.ProcessId);
                process.Kill(entireProcessTree: true);
                process.WaitForExit(2000);
            }
            return 0;
        }
        catch { return 1; }
    }
}
