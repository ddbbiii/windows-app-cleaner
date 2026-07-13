using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using WindowsAppCleaner.Interop;

namespace WindowsAppCleaner.Views;

public partial class OrbWindow : Window
{
    private System.Windows.Point _pressPoint;
    private bool _moving;
    private HwndSource? _source;

    public OrbWindow()
    {
        InitializeComponent();
        if (Environment.GetEnvironmentVariable("APP_CLEANER_DEBUG_TASKBAR") == "1") ShowInTaskbar = true;
        SourceInitialized += (_, _) =>
        {
            _source = HwndSource.FromHwnd(new WindowInteropHelper(this).Handle);
            _source.AddHook(WndProc);
        };
        Closed += (_, _) => _source?.RemoveHook(WndProc);
    }

    public event Action? ToggleRequested;
    public event Action? PositionCommitted;
    public void SetCount(int count) => CountText.Text = count > 99 ? "99+" : count.ToString();

    private void OnMouseDown(object sender, MouseButtonEventArgs e)
    {
        _pressPoint = e.GetPosition(this);
        _moving = false;
        CaptureMouse();
    }

    private void OnMouseMove(object sender, System.Windows.Input.MouseEventArgs e)
    {
        if (e.LeftButton != MouseButtonState.Pressed || _moving) return;
        var point = e.GetPosition(this);
        if (Math.Abs(point.X - _pressPoint.X) < 4 && Math.Abs(point.Y - _pressPoint.Y) < 4) return;
        _moving = true;
        ReleaseMouseCapture();
        var hwnd = new WindowInteropHelper(this).Handle;
        NativeMethods.ReleaseCapture();
        NativeMethods.SendMessageW(hwnd, NativeMethods.WmNcLButtonDown, NativeMethods.HtCaption, 0);
        PositionCommitted?.Invoke();
    }

    private void OnMouseUp(object sender, MouseButtonEventArgs e)
    {
        ReleaseMouseCapture();
        if (!_moving) ToggleRequested?.Invoke();
    }

    private nint WndProc(nint hwnd, int message, nint wParam, nint lParam, ref bool handled)
    {
        if (message == NativeMethods.WmExitSizeMove) PositionCommitted?.Invoke();
        return 0;
    }
}
