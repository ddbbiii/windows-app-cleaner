using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;
using WindowsAppCleaner.Models;
using WindowsAppCleaner.Services;
using WindowsAppCleaner.ViewModels;
using WindowsAppCleaner.Views;

namespace WindowsAppCleaner;

public sealed class AppHost : IDisposable
{
    private readonly ConfigService _config;
    private readonly LocalLogService _log;
    private readonly AutostartService _autostart = new();
    private readonly AppInventoryService _inventory = new(new TaskbarWindowProvider(), new NotificationAreaProvider());
    private readonly CleanupService _cleanup = new();
    private readonly IconService _icons = new();
    private readonly PanelViewModel _viewModel = new();
    private readonly WindowPlacementService _placement;
    private readonly OrbWindow _orb = new();
    private PanelWindow? _panel;
    private SettingsWindow? _settings;
    private readonly HotkeyService _hotkey = new();
    private readonly DispatcherTimer _refreshTimer;
    private TrayService? _tray;
    private FullscreenGuardService? _fullscreen;
    private WindowChangeMonitorService? _windowChanges;
    private IReadOnlyList<AppSnapshot> _apps = [];
    private int _refreshing;
    private bool _exiting;

    public AppHost(ConfigService config, LocalLogService log)
    {
        _config = config;
        _log = log;
        _placement = new WindowPlacementService(config);
        _orb.ToggleRequested += TogglePanel;
        _orb.PositionCommitted += () => { _placement.Clamp(_orb, true); if (_panel?.IsVisible == true) _placement.PlacePanel(_panel, _orb); };
        _refreshTimer = new DispatcherTimer(TimeSpan.FromSeconds(60), DispatcherPriority.Background, async (_, _) => await RefreshAsync(), _orb.Dispatcher);
    }

    public void Start()
    {
        if (_config.Current.AutostartEnabled && !_autostart.IsEnabled())
        {
            _autostart.SetEnabled(true);
            _config.Save();
        }
        _orb.SourceInitialized += (_, _) =>
        {
            _placement.RestoreOrb(_orb);
            try { _hotkey.Attach(new WindowInteropHelper(_orb).Handle, _config.Current.Hotkey, () => _ = CleanDefaultAsync()); }
            catch (Exception ex) { _log.Write("全局快捷键注册失败", ex); }
            _fullscreen = new FullscreenGuardService(_orb.Dispatcher, () => new WindowInteropHelper(_orb).Handle);
            _windowChanges = new WindowChangeMonitorService(_orb.Dispatcher, () => _ = RefreshAsync());
            _fullscreen.FullscreenChanged += hidden =>
            {
                if (!_config.Current.HideInFullscreen) return;
                if (hidden) { _panel?.Hide(); _orb.Hide(); } else if (!_exiting) _orb.Show();
            };
        };
        _orb.Show();
        _tray = new TrayService(TogglePanel, () => _ = CleanDefaultAsync(), () => _ = CleanAsync(AppScope.Foreground, null),
            () => _ = CleanAsync(AppScope.Background, null), OpenSettings, ToggleAutostart, Exit,
            _autostart.IsEnabled);
        _config.Current.AutostartEnabled = _autostart.IsEnabled();
        _refreshTimer.Start();
        _ = InitialRefreshAsync();
    }

    public void ActivateFromSecondInstance() => _orb.Dispatcher.BeginInvoke(TogglePanel);

    private async Task InitialRefreshAsync()
    {
        await RefreshAsync();
        await Task.Delay(1000);
        WorkingSetService.Trim();
    }

    private async Task RefreshAsync()
    {
        if (Interlocked.Exchange(ref _refreshing, 1) != 0) return;
        try
        {
            var snapshot = await Task.Run(_inventory.GetSnapshot);
            _apps = snapshot;
            if (_panel is not null)
            {
                _viewModel.Update(snapshot, _config.Current, _icons);
                _orb.SetCount(_viewModel.CleanableCount);
            }
            else
            {
                var allowed = AllowedSet();
                _orb.SetCount(snapshot.Count(x => !allowed.Contains(x.ProcessName)));
            }
        }
        catch (Exception ex) { _log.Write("应用列表刷新失败", ex); _viewModel.StatusText = "应用列表刷新失败"; }
        finally { Interlocked.Exchange(ref _refreshing, 0); }
    }

    private async void TogglePanel()
    {
        if (_panel?.IsVisible == true) { _panel.Hide(); _refreshTimer.Interval = TimeSpan.FromSeconds(60); return; }
        await RefreshAsync();
        var panel = GetPanel();
        _viewModel.Update(_apps, _config.Current, _icons);
        panel.ShowAnimated();
        panel.UpdateLayout();
        _placement.PlacePanel(panel, _orb);
        _refreshTimer.Interval = TimeSpan.FromSeconds(5);
    }

    private async Task CleanDefaultAsync()
    {
        if (_viewModel.IsBusy) return;
        if (_config.Current.CleanupMode == "foreground_only") { await CleanAsync(AppScope.Foreground, null); return; }
        var allowed = AllowedSet();
        var foregroundOnly = _apps.Where(x => x.HasForeground && !x.HasBackground && !allowed.Contains(x.ProcessName)).ToList();
        var background = _apps.Where(x => x.HasBackground && !allowed.Contains(x.ProcessName)).ToList();
        await ExecuteBatchesAsync([
            (_cleanup.RequestCloseAsync(foregroundOnly, AppScope.Foreground)),
            (_cleanup.RequestCloseAsync(background, AppScope.Background)),
        ]);
    }

    private async Task CleanAsync(AppScope scope, AppSnapshot? selected)
    {
        if (_viewModel.IsBusy) return;
        var allowed = AllowedSet();
        var targets = selected is not null ? [selected] : _apps.Where(x =>
            (scope == AppScope.Foreground ? x.HasForeground : x.HasBackground) && !allowed.Contains(x.ProcessName)).ToList();
        await ExecuteBatchesAsync([_cleanup.RequestCloseAsync(targets, scope)]);
    }

    private async Task ExecuteBatchesAsync(IEnumerable<Task<CleanupBatchResult>> tasks)
    {
        if (_viewModel.IsBusy) return;
        _viewModel.IsBusy = true;
        _viewModel.StatusText = "正在正常关闭应用…";
        try
        {
            var batches = await Task.WhenAll(tasks);
            var batch = new CleanupBatchResult();
            foreach (var item in batches.SelectMany(x => x.Items)) batch.Items.Add(item);
            if (batch.PendingCount > 0)
            {
                var owner = _panel?.IsVisible == true ? (Window)_panel : _orb;
                if (_panel is not null) _panel.SuppressLightDismiss = true;
                var names = string.Join("、", batch.Items.Where(x => x.Status == CleanupStatus.PendingConfirmation).Select(x => x.App.ProcessName).Distinct());
                var answer = System.Windows.MessageBox.Show(owner,
                    $"以下应用未完成正常关闭：\n\n{names}\n\n强制结束可能导致未保存内容丢失，是否继续？",
                    "确认强制结束", MessageBoxButton.YesNo, MessageBoxImage.Warning);
                if (answer == MessageBoxResult.Yes) await _cleanup.ForceCloseAsync(batch);
                if (_panel is not null) _panel.SuppressLightDismiss = false;
            }
            if (batch.Items.Any(x => x.Status == CleanupStatus.AccessDenied))
            {
                var owner = _panel?.IsVisible == true ? (Window)_panel : _orb;
                if (_panel is not null) _panel.SuppressLightDismiss = true;
                var elevate = System.Windows.MessageBox.Show(owner, "部分应用需要管理员权限。是否仅为本次强制结束请求管理员权限？",
                    "权限不足", MessageBoxButton.YesNo, MessageBoxImage.Question);
                if (elevate == MessageBoxResult.Yes)
                {
                    var denied = batch.Items.Where(x => x.Status == CleanupStatus.AccessDenied).ToList();
                    if (await ElevatedCleanupHelper.RunElevatedAsync(denied, _config.ConfigDirectory))
                        foreach (var item in denied) { item.Status = CleanupStatus.ForceClosed; item.Message = "已通过管理员权限强制结束"; }
                }
                if (_panel is not null) _panel.SuppressLightDismiss = false;
            }
            _viewModel.StatusText = $"已关闭 {batch.ClosedCount} · 待处理 {batch.PendingCount} · 失败 {batch.FailureCount} · 保护 {batch.ProtectedCount}";
            _log.Write(_viewModel.StatusText);
            await RefreshAsync();
        }
        catch (Exception ex) { _log.Write("清理失败", ex); _viewModel.StatusText = "清理失败，请查看本地日志"; }
        finally { _viewModel.IsBusy = false; }
    }

    private HashSet<string> AllowedSet() => _config.Current.AllowlistProcessNames.ToHashSet(StringComparer.OrdinalIgnoreCase);

    private void ToggleAllow(AppSnapshot app)
    {
        var names = _config.Current.AllowlistProcessNames;
        var existing = names.FindIndex(x => x.Equals(app.ProcessName, StringComparison.OrdinalIgnoreCase));
        if (existing >= 0) names.RemoveAt(existing); else names.Add(app.ProcessName);
        _config.Save();
        _viewModel.Update(_apps, _config.Current, _icons);
        _orb.SetCount(_viewModel.CleanableCount);
        _viewModel.StatusText = existing >= 0 ? $"已取消保留 {app.ProcessName}" : $"已保留 {app.ProcessName}";
    }

    private bool ChangeHotkey(HotkeyConfig hotkey) => _hotkey.Change(hotkey);
    private void OnSettingsChanged()
    {
        _tray?.UpdateLabels();
        if (_panel is not null) _viewModel.Update(_apps, _config.Current, _icons);
    }
    private void OpenSettings() { _panel?.Hide(); GetSettings().Open(); }

    private PanelWindow GetPanel()
    {
        if (_panel is not null) return _panel;
        _panel = new PanelWindow(_viewModel);
        _panel.CleanRequested += CleanAsync;
        _panel.ToggleAllowRequested += ToggleAllow;
        _panel.SettingsRequested += OpenSettings;
        _panel.Deactivated += async (_, _) =>
        {
            _refreshTimer.Interval = TimeSpan.FromSeconds(60);
            await Task.Delay(1000);
            WorkingSetService.Trim();
        };
        return _panel;
    }

    private SettingsWindow GetSettings() => _settings ??= new SettingsWindow(
        _config, _autostart, () => _apps, ChangeHotkey, OnSettingsChanged);
    private void ToggleAutostart()
    {
        var enabled = !_autostart.IsEnabled();
        _autostart.SetEnabled(enabled);
        _config.Current.AutostartEnabled = enabled;
        _config.Save();
    }

    public void Exit()
    {
        _exiting = true;
        System.Windows.Application.Current.Shutdown();
    }

    public void Dispose()
    {
        _refreshTimer.Stop();
        _fullscreen?.Dispose();
        _windowChanges?.Dispose();
        _hotkey.Dispose();
        _tray?.Dispose();
        _panel?.Close();
        _settings?.ClosePermanently();
        _orb.Close();
    }
}
