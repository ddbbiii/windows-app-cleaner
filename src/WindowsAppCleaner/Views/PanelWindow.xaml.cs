using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using WindowsAppCleaner.Models;
using WindowsAppCleaner.ViewModels;

namespace WindowsAppCleaner.Views;

public partial class PanelWindow : Window
{
    public PanelWindow(PanelViewModel viewModel)
    {
        InitializeComponent();
        var debugTaskbar = Environment.GetEnvironmentVariable("APP_CLEANER_DEBUG_TASKBAR") == "1";
        if (debugTaskbar) ShowInTaskbar = true;
        ViewModel = viewModel;
        DataContext = viewModel;
        Deactivated += (_, _) => { if (!SuppressLightDismiss && !debugTaskbar) Hide(); };
    }

    public PanelViewModel ViewModel { get; }
    public bool SuppressLightDismiss { get; set; }
    public event Func<AppScope, AppSnapshot?, Task>? CleanRequested;
    public event Action<AppSnapshot>? ToggleAllowRequested;
    public event Action? SettingsRequested;

    public void ShowAnimated()
    {
        Height = Math.Clamp(214 + Math.Min(ViewModel.Rows.Count, 6) * 52, 350, 528);
        var animated = SystemParameters.ClientAreaAnimation;
        var transforms = (TransformGroup)PanelSurface.RenderTransform;
        var scale = (ScaleTransform)transforms.Children[0];
        var translate = (TranslateTransform)transforms.Children[1];

        BeginAnimation(OpacityProperty, null);
        scale.BeginAnimation(ScaleTransform.ScaleXProperty, null);
        scale.BeginAnimation(ScaleTransform.ScaleYProperty, null);
        translate.BeginAnimation(TranslateTransform.YProperty, null);

        Opacity = animated ? 0 : 1;
        scale.ScaleX = scale.ScaleY = animated ? 0.975 : 1;
        translate.Y = animated ? 8 : 0;
        Show();
        Activate();

        if (!animated) return;

        var duration = TimeSpan.FromMilliseconds(160);
        var easing = new CubicEase { EasingMode = EasingMode.EaseOut };
        BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, duration) { EasingFunction = easing });
        scale.BeginAnimation(ScaleTransform.ScaleXProperty, new DoubleAnimation(0.975, 1, duration) { EasingFunction = easing });
        scale.BeginAnimation(ScaleTransform.ScaleYProperty, new DoubleAnimation(0.975, 1, duration) { EasingFunction = easing });
        translate.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(8, 0, duration) { EasingFunction = easing });
    }

    private async void OnCleanForeground(object sender, RoutedEventArgs e) => await RaiseClean(AppScope.Foreground, null);
    private async void OnCleanBackground(object sender, RoutedEventArgs e) => await RaiseClean(AppScope.Background, null);
    private async void OnCleanOne(object sender, RoutedEventArgs e)
    {
        if ((sender as System.Windows.Controls.Button)?.Tag is AppRowViewModel row) await RaiseClean(row.Scope, row.App);
    }
    private void OnToggleAllow(object sender, RoutedEventArgs e)
    {
        if ((sender as System.Windows.Controls.Button)?.Tag is AppRowViewModel row) ToggleAllowRequested?.Invoke(row.App);
    }
    private void OnSettings(object sender, RoutedEventArgs e) => SettingsRequested?.Invoke();
    private async Task RaiseClean(AppScope scope, AppSnapshot? app)
    {
        if (CleanRequested is not null) await CleanRequested(scope, app);
    }
}
