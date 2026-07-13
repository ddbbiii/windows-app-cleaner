using WindowsAppCleaner.Interop;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class TaskbarWindowProvider
{
    private static readonly HashSet<string> ExcludedClasses = new(StringComparer.OrdinalIgnoreCase)
    {
        "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "DV2ControlHost",
        "Windows.UI.Core.CoreWindow", "DesktopAppCleanerTrayWindow",
    };

    public IReadOnlyList<AppSnapshot> Enumerate(int selfProcessId)
    {
        var apps = new Dictionary<string, AppSnapshot>(StringComparer.OrdinalIgnoreCase);
        var shell = NativeMethods.GetShellWindow();
        NativeMethods.EnumWindows((hwnd, _) =>
        {
            if (!IsTaskbarCandidate(hwnd, shell)) return true;
            NativeMethods.GetWindowThreadProcessId(hwnd, out var rawPid);
            var pid = (int)rawPid;
            if (pid == 0 || pid == selfProcessId) return true;
            var title = NativeMethods.GetWindowText(hwnd);
            var path = ProcessQuery.GetPath(pid);
            var processName = string.IsNullOrWhiteSpace(path) ? $"pid-{pid}" : Path.GetFileName(path);
            if (ProtectedAppPolicy.IsProtected(processName)) return true;
            var id = ProcessQuery.AppId(processName, path);
            if (!apps.TryGetValue(id, out var app))
            {
                app = new AppSnapshot
                {
                    Id = id,
                    ProcessName = processName,
                    ExePath = path,
                    DisplayTitle = title,
                    IsProtected = ProtectedAppPolicy.IsProtected(processName),
                    IdentityConfirmed = !string.IsNullOrWhiteSpace(path),
                };
                apps.Add(id, app);
            }
            app.ProcessIds.Add(pid);
            app.ForegroundWindows.Add(hwnd);
            return true;
        }, 0);
        return apps.Values.ToList();
    }

    internal static bool IsTaskbarCandidate(nint hwnd, nint shellWindow)
    {
        if (hwnd == shellWindow || !NativeMethods.IsWindowVisible(hwnd) || NativeMethods.IsCloaked(hwnd)) return false;
        if (ExcludedClasses.Contains(NativeMethods.GetClassName(hwnd))) return false;
        if (string.IsNullOrWhiteSpace(NativeMethods.GetWindowText(hwnd))) return false;
        var exStyle = unchecked((uint)NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GwlExStyle).ToInt64());
        if ((exStyle & NativeMethods.WsExToolWindow) != 0 && (exStyle & NativeMethods.WsExAppWindow) == 0) return false;
        var owner = NativeMethods.GetWindow(hwnd, NativeMethods.GwOwner);
        return owner == 0 || (exStyle & NativeMethods.WsExAppWindow) != 0;
    }
}
