namespace WindowsAppCleaner.Services;

public sealed class LocalLogService
{
    private readonly string _path;
    private readonly object _gate = new();

    public LocalLogService(ConfigService config)
    {
        var directory = Path.Combine(config.ConfigDirectory, "logs");
        Directory.CreateDirectory(directory);
        _path = Path.Combine(directory, "app.log");
    }

    public void Write(string message, Exception? exception = null)
    {
        lock (_gate)
        {
            Rotate();
            File.AppendAllText(_path, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} {message}{(exception is null ? "" : " | " + exception)}{Environment.NewLine}");
        }
    }

    private void Rotate()
    {
        if (!File.Exists(_path) || new FileInfo(_path).Length < 1024 * 1024) return;
        for (var index = 2; index >= 0; index--)
        {
            var source = index == 0 ? _path : _path + "." + index;
            var target = _path + "." + (index + 1);
            if (File.Exists(source)) File.Move(source, target, true);
        }
    }
}
