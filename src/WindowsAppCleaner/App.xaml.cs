using System.Windows;
using WindowsAppCleaner.Services;

namespace WindowsAppCleaner;

public partial class App : System.Windows.Application
{
    private SingleInstanceService? _singleInstance;
    private AppHost? _host;
    private LocalLogService? _log;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        if (e.Args.Length == 2 && e.Args[0] == "--elevated-force")
        {
            Shutdown(ElevatedCleanupHelper.Execute(e.Args[1]));
            return;
        }

        ShutdownMode = ShutdownMode.OnExplicitShutdown;
        var config = new ConfigService();
        config.Load();
        _log = new LocalLogService(config);
        _singleInstance = new SingleInstanceService();
        if (!_singleInstance.TryAcquire(() => Dispatcher.BeginInvoke(() => _host?.ActivateFromSecondInstance())))
        {
            Shutdown();
            return;
        }

        DispatcherUnhandledException += (_, args) =>
        {
            _log.Write("未处理的界面异常", args.Exception);
            args.Handled = true;
        };
        _host = new AppHost(config, _log);
        _host.Start();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _host?.Dispose();
        _singleInstance?.Dispose();
        base.OnExit(e);
    }
}
