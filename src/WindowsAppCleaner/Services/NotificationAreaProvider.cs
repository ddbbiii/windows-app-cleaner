using System.Diagnostics;
using Microsoft.Win32;
using WindowsAppCleaner.Interop;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class NotificationAreaProvider
{
    private const string RegistryPath = @"Control Panel\NotifyIconSettings";

    public IReadOnlyList<AppSnapshot> Enumerate(int selfProcessId)
    {
        var apps = new Dictionary<string, AppSnapshot>(StringComparer.OrdinalIgnoreCase);
        var registrations = new List<(string Path, string Name, string Title)>();
        using var root = Registry.CurrentUser.OpenSubKey(RegistryPath);
        if (root is null) return [];

        foreach (var subKeyName in root.GetSubKeyNames())
        {
            using var subKey = root.OpenSubKey(subKeyName);
            if (subKey?.GetValue("IsPromoted") is not int promoted || promoted != 1) continue;
            var configuredPath = ResolveShellPath(subKey.GetValue("ExecutablePath")?.ToString() ?? "");
            if (string.IsNullOrWhiteSpace(configuredPath)) continue;
            var name = Path.GetFileName(configuredPath);
            registrations.Add((configuredPath, name, subKey.GetValue("InitialTooltip")?.ToString()?.Trim() ?? name));
        }

        var names = registrations.Select(x => Path.GetFileNameWithoutExtension(x.Name)).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var running = new List<(int Pid, string Name, string Path)>();
        foreach (var process in Process.GetProcesses())
        {
            using (process)
            {
                if (!names.Contains(process.ProcessName)) continue;
                running.Add((process.Id, process.ProcessName + ".exe", ProcessQuery.GetPath(process.Id)));
            }
        }

        foreach (var registration in registrations)
        {
            foreach (var candidate in running.Where(x => x.Pid != selfProcessId &&
                         x.Name.Equals(registration.Name, StringComparison.OrdinalIgnoreCase) && PathsMatch(registration.Path, x.Path)))
            {
                if (ProtectedAppPolicy.IsProtected(registration.Name)) continue;
                var id = ProcessQuery.AppId(registration.Name, candidate.Path);
                if (!apps.TryGetValue(id, out var app))
                {
                    app = new AppSnapshot
                    {
                        Id = id,
                        ProcessName = registration.Name,
                        ExePath = candidate.Path,
                        DisplayTitle = registration.Title,
                        IsProtected = ProtectedAppPolicy.IsProtected(registration.Name),
                        IdentityConfirmed = true,
                    };
                    apps.Add(id, app);
                }
                app.ProcessIds.Add(candidate.Pid);
                foreach (var hwnd in NativeMethods.EnumerateWindowsForProcess(candidate.Pid).Where(x => !NativeMethods.IsWindowVisible(x)))
                    app.BackgroundWindows.Add(hwnd);
                if (app.BackgroundWindows.Count == 0) app.BackgroundWindows.Add(0);
            }
        }
        return apps.Values.ToList();
    }

    private static bool PathsMatch(string configured, string running)
    {
        if (string.IsNullOrWhiteSpace(running)) return false;
        return string.Equals(ProcessQuery.NormalizePath(configured), ProcessQuery.NormalizePath(running), StringComparison.OrdinalIgnoreCase);
    }

    private static string ResolveShellPath(string raw)
    {
        var path = raw.Trim();
        if (path.Length == 0) return "";
        var known = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["{6D809377-6AF0-444B-8957-A3773F02200E}"] = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            ["{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}"] = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            ["{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}"] = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32"),
            ["{F38BF404-1D43-42F2-9305-67DE0B28FC23}"] = Environment.GetFolderPath(Environment.SpecialFolder.Windows),
        };
        foreach (var pair in known)
            if (path.StartsWith(pair.Key, StringComparison.OrdinalIgnoreCase))
                path = Path.Combine(pair.Value, path[(pair.Key.Length + 1)..]);
        return ProcessQuery.NormalizePath(path);
    }
}
