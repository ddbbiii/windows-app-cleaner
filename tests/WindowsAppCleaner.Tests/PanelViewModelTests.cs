using WindowsAppCleaner.Models;
using WindowsAppCleaner.Services;
using WindowsAppCleaner.ViewModels;

namespace WindowsAppCleaner.Tests;

public sealed class PanelViewModelTests
{
    [Fact]
    public void KeepsDualScopeRowsAdjacentAndSharesAllowlistRule()
    {
        var dual = App("dual.exe", foreground: true, background: true);
        var foreground = App("front.exe", foreground: true, background: false);
        var background = App("tray.exe", foreground: false, background: true);
        var config = new CleanerConfig { AllowlistProcessNames = ["dual.exe"] };
        var model = new PanelViewModel();

        model.Update([dual, foreground, background], config, new IconService());

        Assert.Collection(model.Rows,
            row => { Assert.Equal("dual.exe", row.App.ProcessName); Assert.Equal(AppScope.Foreground, row.Scope); Assert.True(row.IsAllowed); },
            row => { Assert.Equal("dual.exe", row.App.ProcessName); Assert.Equal(AppScope.Background, row.Scope); Assert.True(row.IsAllowed); },
            row => Assert.Equal("front.exe", row.App.ProcessName),
            row => Assert.Equal("tray.exe", row.App.ProcessName));
        Assert.Equal(2, model.CleanableCount);
        Assert.Equal(1, model.ForegroundCount);
        Assert.Equal(1, model.BackgroundCount);
    }

    private static AppSnapshot App(string name, bool foreground, bool background)
    {
        var app = new AppSnapshot { Id = name, ProcessName = name, ExePath = "", IdentityConfirmed = true };
        if (foreground) app.ForegroundWindows.Add(1);
        if (background) app.BackgroundWindows.Add(2);
        return app;
    }
}
