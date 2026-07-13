using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class AppInventoryService(TaskbarWindowProvider taskbar, NotificationAreaProvider notificationArea)
{
    public IReadOnlyList<AppSnapshot> GetSnapshot()
    {
        var self = Environment.ProcessId;
        var merged = new Dictionary<string, AppSnapshot>(StringComparer.OrdinalIgnoreCase);
        foreach (var source in taskbar.Enumerate(self).Concat(notificationArea.Enumerate(self)))
        {
            if (!merged.TryGetValue(source.Id, out var target))
            {
                merged[source.Id] = source;
                continue;
            }
            target.ProcessIds.UnionWith(source.ProcessIds);
            foreach (var hwnd in source.ForegroundWindows.Where(x => !target.ForegroundWindows.Contains(x))) target.ForegroundWindows.Add(hwnd);
            foreach (var hwnd in source.BackgroundWindows.Where(x => !target.BackgroundWindows.Contains(x))) target.BackgroundWindows.Add(hwnd);
            if (string.IsNullOrWhiteSpace(target.DisplayTitle)) target.DisplayTitle = source.DisplayTitle;
            target.IsProtected |= source.IsProtected;
            target.IdentityConfirmed &= source.IdentityConfirmed;
        }

        return merged.Values
            .OrderBy(x => x.HasForeground ? 0 : 1)
            .ThenBy(x => x.ProcessName, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }
}
