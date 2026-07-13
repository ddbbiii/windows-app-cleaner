using System.Drawing;
using System.Windows.Forms;

namespace WindowsAppCleaner.Services;

public sealed class TrayService : IDisposable
{
    private readonly NotifyIcon _icon;
    private readonly Icon _ownedIcon;
    private readonly ToolStripMenuItem _autostart;
    private readonly Func<bool> _autostartState;

    public TrayService(Action togglePanel, Action cleanDefault, Action cleanForeground, Action cleanBackground,
        Action openSettings, Action toggleAutostart, Action exit, Func<bool> autostartState)
    {
        _autostartState = autostartState;
        _autostart = new ToolStripMenuItem();
        _autostart.Click += (_, _) => { toggleAutostart(); UpdateLabels(); };
        var menu = new ContextMenuStrip();
        menu.Items.Add("按默认范围清理", null, (_, _) => cleanDefault());
        menu.Items.Add("清理前台", null, (_, _) => cleanForeground());
        menu.Items.Add("清理后台", null, (_, _) => cleanBackground());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("打开设置", null, (_, _) => openSettings());
        menu.Items.Add(_autostart);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("退出", null, (_, _) => exit());
        _ownedIcon = TrayIconFactory.Create();
        _icon = new NotifyIcon
        {
            Icon = _ownedIcon,
            Text = "Windows 应用清理器",
            ContextMenuStrip = menu,
            Visible = true,
        };
        _icon.MouseClick += (_, e) => { if (e.Button == MouseButtons.Left) togglePanel(); };
        UpdateLabels();
    }

    public void UpdateLabels() => _autostart.Text = _autostartState() ? "关闭开机启动" : "启用开机启动";

    public void Dispose()
    {
        _icon.Visible = false;
        _icon.ContextMenuStrip?.Dispose();
        _icon.Dispose();
        _ownedIcon.Dispose();
    }
}
