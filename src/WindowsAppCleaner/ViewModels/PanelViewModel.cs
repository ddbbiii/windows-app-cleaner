using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Media;
using WindowsAppCleaner.Models;
using WindowsAppCleaner.Services;

namespace WindowsAppCleaner.ViewModels;

public sealed class PanelViewModel : INotifyPropertyChanged
{
    private int _foregroundCount;
    private int _backgroundCount;
    private int _cleanableCount;
    private bool _isBusy;
    private string _statusText = "准备就绪";

    public ObservableCollection<AppRowViewModel> Rows { get; } = [];
    public IReadOnlyList<AppSnapshot> Apps { get; private set; } = [];
    public int ForegroundCount { get => _foregroundCount; private set => Set(ref _foregroundCount, value); }
    public int BackgroundCount { get => _backgroundCount; private set => Set(ref _backgroundCount, value); }
    public int CleanableCount { get => _cleanableCount; private set => Set(ref _cleanableCount, value); }
    public bool IsBusy { get => _isBusy; set => Set(ref _isBusy, value); }
    public string StatusText { get => _statusText; set => Set(ref _statusText, value); }

    public void Update(IReadOnlyList<AppSnapshot> apps, CleanerConfig config, IconService icons)
    {
        Apps = apps;
        var allowed = config.AllowlistProcessNames.ToHashSet(StringComparer.OrdinalIgnoreCase);
        ForegroundCount = apps.Count(x => x.HasForeground && !allowed.Contains(x.ProcessName));
        BackgroundCount = apps.Count(x => x.HasBackground && !allowed.Contains(x.ProcessName));
        CleanableCount = apps.Count(x => !allowed.Contains(x.ProcessName));
        Rows.Clear();
        foreach (var app in apps.Where(x => x.HasForeground).Concat(apps.Where(x => !x.HasForeground && x.HasBackground)))
        {
            if (app.HasForeground) Rows.Add(new AppRowViewModel(app, AppScope.Foreground, allowed.Contains(app.ProcessName), icons.Get(app.ExePath)));
            if (app.HasBackground) Rows.Add(new AppRowViewModel(app, AppScope.Background, allowed.Contains(app.ProcessName), icons.Get(app.ExePath)));
        }
        OnPropertyChanged(nameof(Rows));
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void Set<T>(ref T field, T value, [CallerMemberName] string name = "")
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return;
        field = value;
        OnPropertyChanged(name);
    }
    private void OnPropertyChanged([CallerMemberName] string name = "") => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public sealed class AppRowViewModel(AppSnapshot app, AppScope scope, bool isAllowed, ImageSource? icon)
{
    public AppSnapshot App { get; } = app;
    public AppScope Scope { get; } = scope;
    public bool IsAllowed { get; } = isAllowed;
    public ImageSource? Icon { get; } = icon;
    public string ScopeLabel => Scope == AppScope.Foreground ? "前台" : "后台";
    public string Tooltip => $"{App.ProcessName}\n{App.DisplayTitle}\n{(string.IsNullOrWhiteSpace(App.ExePath) ? "路径不可读取" : App.ExePath)}";
}
