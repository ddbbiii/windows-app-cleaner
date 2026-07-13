using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using WindowsAppCleaner.Interop;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class WindowPlacementService(ConfigService config)
{
    public void RestoreOrb(Window window)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        var saved = config.Current.FloatingPosition;
        if (saved is not null)
            NativeMethods.SetWindowPos(hwnd, 0, saved.X, saved.Y, 0, 0, NativeMethods.SwpNoActivate | NativeMethods.SwpNoZOrder | NativeMethods.SwpNoSize);
        else
        {
            var info = NativeMethods.GetMonitorInfoForWindow(hwnd);
            NativeMethods.GetWindowRect(hwnd, out var rect);
            NativeMethods.SetWindowPos(hwnd, 0, info.Work.Right - rect.Width - 28, info.Work.Top + 150, 0, 0,
                NativeMethods.SwpNoActivate | NativeMethods.SwpNoZOrder | NativeMethods.SwpNoSize);
        }
        Clamp(window);
    }

    public void Clamp(Window window, bool persist = false)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        if (!NativeMethods.GetWindowRect(hwnd, out var rect)) return;
        var info = NativeMethods.GetMonitorInfoForWindow(hwnd);
        var x = Math.Clamp(rect.Left, info.Work.Left, Math.Max(info.Work.Left, info.Work.Right - rect.Width));
        var y = Math.Clamp(rect.Top, info.Work.Top, Math.Max(info.Work.Top, info.Work.Bottom - rect.Height));
        NativeMethods.SetWindowPos(hwnd, 0, x, y, 0, 0, NativeMethods.SwpNoActivate | NativeMethods.SwpNoZOrder | NativeMethods.SwpNoSize);
        if (!persist) return;
        config.Current.FloatingPosition = new FloatingPositionConfig { DeviceName = info.DeviceName, X = x, Y = y };
        config.Save();
    }

    public void PlacePanel(Window panel, Window orb)
    {
        var orbHwnd = new WindowInteropHelper(orb).Handle;
        var panelHwnd = new WindowInteropHelper(panel).Handle;
        NativeMethods.GetWindowRect(orbHwnd, out var orbRect);
        NativeMethods.GetWindowRect(panelHwnd, out var panelRect);
        var info = NativeMethods.GetMonitorInfoForWindow(orbHwnd);
        var gap = 10;
        var left = orbRect.Left - panelRect.Width - gap;
        if (left < info.Work.Left) left = orbRect.Right + gap;
        var top = orbRect.Top + orbRect.Height / 2 - panelRect.Height / 2;
        top = Math.Clamp(top, info.Work.Top + 8, Math.Max(info.Work.Top + 8, info.Work.Bottom - panelRect.Height - 8));
        left = Math.Clamp(left, info.Work.Left + 8, Math.Max(info.Work.Left + 8, info.Work.Right - panelRect.Width - 8));
        NativeMethods.SetWindowPos(panelHwnd, 0, left, top, 0, 0, NativeMethods.SwpNoActivate | NativeMethods.SwpNoZOrder | NativeMethods.SwpNoSize);
    }
}
