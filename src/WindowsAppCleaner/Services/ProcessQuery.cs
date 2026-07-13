using System.Diagnostics;

namespace WindowsAppCleaner.Services;

internal static class ProcessQuery
{
    internal static string GetPath(int processId)
    {
        try { using var process = Process.GetProcessById(processId); return process.MainModule?.FileName ?? ""; }
        catch { return ""; }
    }

    internal static string NormalizePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return "";
        try { return Path.GetFullPath(Environment.ExpandEnvironmentVariables(path)).TrimEnd(Path.DirectorySeparatorChar); }
        catch { return path.Trim(); }
    }

    internal static string AppId(string processName, string path) =>
        string.IsNullOrWhiteSpace(path) ? processName.ToLowerInvariant() : NormalizePath(path).ToLowerInvariant();
}
