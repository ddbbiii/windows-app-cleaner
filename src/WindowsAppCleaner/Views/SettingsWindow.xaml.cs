using System.Reflection;
using System.Windows;
using WindowsAppCleaner.Models;
using WindowsAppCleaner.Services;

namespace WindowsAppCleaner.Views;

public partial class SettingsWindow : Window
{
    private readonly ConfigService _config;
    private readonly AutostartService _autostart;
    private readonly Func<IReadOnlyList<AppSnapshot>> _apps;
    private readonly Func<HotkeyConfig, bool> _changeHotkey;
    private readonly Action _changed;
    private bool _closingPermanently;

    public SettingsWindow(ConfigService config, AutostartService autostart, Func<IReadOnlyList<AppSnapshot>> apps,
        Func<HotkeyConfig, bool> changeHotkey, Action changed)
    {
        InitializeComponent();
        _config = config;
        _autostart = autostart;
        _apps = apps;
        _changeHotkey = changeHotkey;
        _changed = changed;
        Closing += (_, e) => { if (!_closingPermanently) { e.Cancel = true; Hide(); } };
    }

    public void Open()
    {
        Reload();
        Show();
        WindowState = WindowState.Normal;
        Activate();
    }

    private void Reload()
    {
        var config = _config.Current;
        HotkeyBox.Text = config.Hotkey.Display;
        BothMode.IsChecked = config.CleanupMode == "foreground_and_background";
        ForegroundMode.IsChecked = !BothMode.IsChecked;
        AutostartCheck.IsChecked = _autostart.IsEnabled();
        MinimizedCheck.IsChecked = config.MinimizeToTrayOnLaunch;
        FullscreenCheck.IsChecked = config.HideInFullscreen;
        CurrentAppsList.ItemsSource = _apps().OrderBy(x => x.ProcessName, StringComparer.OrdinalIgnoreCase).ToList();
        RefreshAllowlist();
        VersionText.Text = $"Windows 应用清理器 {Assembly.GetExecutingAssembly().GetName().Version?.ToString(3)}";
    }

    private void RefreshAllowlist()
    {
        AllowlistList.ItemsSource = null;
        AllowlistList.ItemsSource = _config.Current.AllowlistProcessNames.ToList();
    }

    private void OnAddAllow(object sender, RoutedEventArgs e)
    {
        foreach (AppSnapshot app in CurrentAppsList.SelectedItems)
            if (!_config.Current.AllowlistProcessNames.Contains(app.ProcessName, StringComparer.OrdinalIgnoreCase))
                _config.Current.AllowlistProcessNames.Add(app.ProcessName);
        RefreshAllowlist();
    }

    private void OnRemoveAllow(object sender, RoutedEventArgs e)
    {
        var selected = AllowlistList.SelectedItems.Cast<string>().ToHashSet(StringComparer.OrdinalIgnoreCase);
        _config.Current.AllowlistProcessNames.RemoveAll(selected.Contains);
        RefreshAllowlist();
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        if (!HotkeyService.TryParse(HotkeyBox.Text, out var hotkey))
        {
            System.Windows.MessageBox.Show(this, "快捷键格式无效。请输入 F4 或 Ctrl+Alt+K。", "快捷键无效", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        if (!_changeHotkey(hotkey))
        {
            System.Windows.MessageBox.Show(this, $"快捷键 {hotkey.Display} 已被其他程序占用，原快捷键保持不变。", "快捷键冲突", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        _config.Current.Hotkey = hotkey;
        _config.Current.CleanupMode = BothMode.IsChecked == true ? "foreground_and_background" : "foreground_only";
        _config.Current.MinimizeToTrayOnLaunch = MinimizedCheck.IsChecked == true;
        _config.Current.HideInFullscreen = FullscreenCheck.IsChecked == true;
        _config.Current.AutostartEnabled = AutostartCheck.IsChecked == true;
        _autostart.SetEnabled(_config.Current.AutostartEnabled);
        _config.Save();
        _changed();
        Hide();
    }

    private void OnCancel(object sender, RoutedEventArgs e) => Hide();

    public void ClosePermanently()
    {
        _closingPermanently = true;
        Close();
    }
}
