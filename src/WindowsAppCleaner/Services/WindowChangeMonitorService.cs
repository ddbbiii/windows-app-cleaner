using System.Windows.Threading;
using WindowsAppCleaner.Interop;

namespace WindowsAppCleaner.Services;

public sealed class WindowChangeMonitorService : IDisposable
{
    private readonly Dispatcher _dispatcher;
    private readonly NativeMethods.WinEventProc _callback;
    private readonly DispatcherTimer _debounce;
    private nint _hook;

    public WindowChangeMonitorService(Dispatcher dispatcher, Action changed)
    {
        _dispatcher = dispatcher;
        _debounce = new DispatcherTimer(DispatcherPriority.Background, dispatcher) { Interval = TimeSpan.FromMilliseconds(300) };
        _debounce.Tick += (_, _) =>
        {
            _debounce.Stop();
            changed();
        };
        _debounce.Stop();
        _callback = (_, _, hwnd, objectId, childId, _, _) =>
        {
            if (hwnd == 0 || objectId != 0 || childId != 0) return;
            if (NativeMethods.GetWindow(hwnd, NativeMethods.GwOwner) != 0 || string.IsNullOrWhiteSpace(NativeMethods.GetWindowText(hwnd))) return;
            _dispatcher.BeginInvoke(() => { _debounce.Stop(); _debounce.Start(); });
        };
        _hook = NativeMethods.SetWinEventHook(NativeMethods.EventObjectShow, NativeMethods.EventObjectHide, 0,
            _callback, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
    }

    public void Dispose()
    {
        _debounce.Stop();
        if (_hook != 0) NativeMethods.UnhookWinEvent(_hook);
    }
}
