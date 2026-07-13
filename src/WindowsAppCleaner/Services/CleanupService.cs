using System.ComponentModel;
using System.Diagnostics;
using WindowsAppCleaner.Interop;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class CleanupService
{
    public async Task<CleanupBatchResult> RequestCloseAsync(IEnumerable<AppSnapshot> apps, AppScope scope, CancellationToken cancellationToken = default)
    {
        var batch = new CleanupBatchResult();
        foreach (var app in apps)
        {
            var item = new CleanupItemResult { App = app, Scope = scope, Status = CleanupStatus.PendingConfirmation };
            batch.Items.Add(item);
            if (app.IsProtected || !app.IdentityConfirmed)
            {
                item.Status = CleanupStatus.Protected;
                item.Message = app.IsProtected ? "系统保护应用" : "无法确认应用身份";
                continue;
            }

            CaptureProcesses(app, item);
            var windows = scope == AppScope.Foreground
                ? app.ForegroundWindows.Where(NativeMethods.IsWindow)
                : app.ProcessIds.SelectMany(NativeMethods.EnumerateWindowsForProcess).Distinct();
            item.TargetWindows.AddRange(windows);
            foreach (var hwnd in item.TargetWindows) NativeMethods.PostMessageW(hwnd, NativeMethods.WmClose, 0, 0);
        }

        if (batch.Items.All(x => x.Status != CleanupStatus.PendingConfirmation)) return batch;
        await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
        foreach (var item in batch.Items.Where(x => x.Status == CleanupStatus.PendingConfirmation))
        {
            var completed = item.Scope == AppScope.Foreground
                ? item.TargetWindows.All(hwnd => !NativeMethods.IsWindow(hwnd))
                : item.CapturedProcesses.All(identity => !IsSameProcessAlive(identity));
            if (completed)
            {
                item.Status = CleanupStatus.Closed;
                item.Message = "已正常关闭";
            }
            else
            {
                item.Message = "正常关闭未完成";
            }
        }
        return batch;
    }

    public Task ForceCloseAsync(CleanupBatchResult batch)
    {
        foreach (var item in batch.Items.Where(x => x.Status == CleanupStatus.PendingConfirmation))
        {
            if (ProtectedAppPolicy.IsForceProtected(item.App.ProcessName))
            {
                item.Status = CleanupStatus.Protected;
                item.Message = "该应用只允许正常关闭";
                continue;
            }
            var failures = new List<CleanupStatus>();
            foreach (var identity in item.CapturedProcesses)
            {
                if (!IsSameProcessAlive(identity)) continue;
                try
                {
                    using var process = Process.GetProcessById(identity.ProcessId);
                    process.Kill(entireProcessTree: true);
                    process.WaitForExit(1500);
                }
                catch (Win32Exception ex) when (ex.NativeErrorCode == 5) { failures.Add(CleanupStatus.AccessDenied); }
                catch (Exception) { failures.Add(CleanupStatus.Failed); }
            }
            item.Status = failures.Contains(CleanupStatus.AccessDenied) ? CleanupStatus.AccessDenied
                : failures.Count > 0 ? CleanupStatus.Failed : CleanupStatus.ForceClosed;
            item.Message = item.Status switch
            {
                CleanupStatus.ForceClosed => "已强制结束",
                CleanupStatus.AccessDenied => "权限不足，需要管理员权限",
                _ => "强制结束失败",
            };
        }
        return Task.CompletedTask;
    }

    public static bool IsSameProcessAlive(ProcessIdentity identity)
    {
        try
        {
            using var process = Process.GetProcessById(identity.ProcessId);
            var path = process.MainModule?.FileName ?? "";
            return process.StartTime.ToUniversalTime().Ticks == identity.StartTimeUtcTicks &&
                string.Equals(ProcessQuery.NormalizePath(path), ProcessQuery.NormalizePath(identity.ExePath), StringComparison.OrdinalIgnoreCase);
        }
        catch { return false; }
    }

    private static void CaptureProcesses(AppSnapshot app, CleanupItemResult item)
    {
        foreach (var pid in app.ProcessIds)
        {
            try
            {
                using var process = Process.GetProcessById(pid);
                var path = process.MainModule?.FileName ?? app.ExePath;
                item.CapturedProcesses.Add(new ProcessIdentity(pid, process.StartTime.ToUniversalTime().Ticks, path));
            }
            catch { }
        }
    }
}
