using System.Windows.Threading;
using WindowsAppCleaner.Interop;

namespace WindowsAppCleaner.Services;

public sealed class FullscreenGuardService : IDisposable
{
    private readonly Dispatcher _dispatcher;
    private readonly Func<nint> _ownWindow;
    private readonly NativeMethods.WinEventProc _callback;
    private readonly DispatcherTimer _fallback;
    private nint _hook;
    private bool _last;

    public FullscreenGuardService(Dispatcher dispatcher, Func<nint> ownWindow)
    {
        _dispatcher = dispatcher;
        _ownWindow = ownWindow;
        _callback = (_, _, _, _, _, _, _) => _dispatcher.BeginInvoke(Check);
        _hook = NativeMethods.SetWinEventHook(NativeMethods.EventSystemForeground, NativeMethods.EventSystemForeground,
            0, _callback, 0, 0, NativeMethods.WineventOutOfContext);
        _fallback = new DispatcherTimer(TimeSpan.FromSeconds(1), DispatcherPriority.Background, (_, _) => Check(), dispatcher);
        _fallback.Start();
    }

    public event Action<bool>? FullscreenChanged;

    public void Check()
    {
        var foreground = NativeMethods.GetForegroundWindow();
        var fullscreen = foreground != 0 && foreground != _ownWindow() && IsFullscreen(foreground);
        if (fullscreen == _last) return;
        _last = fullscreen;
        FullscreenChanged?.Invoke(fullscreen);
    }

    private static bool IsFullscreen(nint hwnd)
    {
        if (!NativeMethods.IsWindowVisible(hwnd) || !NativeMethods.GetWindowRect(hwnd, out var rect)) return false;
        var info = NativeMethods.GetMonitorInfoForWindow(hwnd);
        const int tolerance = 3;
        return rect.Left <= info.Monitor.Left + tolerance && rect.Top <= info.Monitor.Top + tolerance &&
            rect.Right >= info.Monitor.Right - tolerance && rect.Bottom >= info.Monitor.Bottom - tolerance;
    }

    public void Dispose()
    {
        _fallback.Stop();
        if (_hook != 0) NativeMethods.UnhookWinEvent(_hook);
    }
}
