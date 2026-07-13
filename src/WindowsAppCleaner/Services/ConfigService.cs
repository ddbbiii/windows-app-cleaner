using System.Text.Json;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class ConfigService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };

    public ConfigService()
    {
        IsPortable = File.Exists(Path.Combine(AppContext.BaseDirectory, "portable.flag"));
        ConfigDirectory = IsPortable ? AppContext.BaseDirectory : Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WindowsAppCleaner");
        ConfigPath = Path.Combine(ConfigDirectory, "config.json");
    }

    public bool IsPortable { get; }
    public string ConfigDirectory { get; }
    public string ConfigPath { get; }
    public CleanerConfig Current { get; private set; } = new();

    public CleanerConfig Load()
    {
        Directory.CreateDirectory(ConfigDirectory);
        ImportLegacyConfigIfNeeded();
        if (!File.Exists(ConfigPath))
        {
            Save();
            return Current;
        }
        try
        {
            Current = JsonSerializer.Deserialize<CleanerConfig>(File.ReadAllText(ConfigPath), JsonOptions) ?? new CleanerConfig();
        }
        catch (JsonException)
        {
            File.Copy(ConfigPath, ConfigPath + ".broken-" + DateTime.Now.ToString("yyyyMMddHHmmss"), true);
            Current = new CleanerConfig();
        }
        Normalize(Current);
        Save();
        return Current;
    }

    public void Save()
    {
        Normalize(Current);
        Directory.CreateDirectory(ConfigDirectory);
        var temporary = ConfigPath + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(Current, JsonOptions));
        File.Move(temporary, ConfigPath, true);
    }

    private void ImportLegacyConfigIfNeeded()
    {
        if (File.Exists(ConfigPath)) return;
        foreach (var directory in CandidateLegacyDirectories())
        {
            var candidate = Path.Combine(directory, "config.json");
            if (!File.Exists(candidate) || string.Equals(candidate, ConfigPath, StringComparison.OrdinalIgnoreCase)) continue;
            try { File.Copy(candidate, ConfigPath, false); return; }
            catch (IOException) { }
        }
    }

    private static IEnumerable<string> CandidateLegacyDirectories()
    {
        yield return Environment.CurrentDirectory;
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        for (var index = 0; directory is not null && index < 7; index++, directory = directory.Parent)
            if (File.Exists(Path.Combine(directory.FullName, "main.py"))) yield return directory.FullName;
    }

    private static void Normalize(CleanerConfig config)
    {
        config.SchemaVersion = 2;
        config.Hotkey ??= new HotkeyConfig();
        if (config.Hotkey.VirtualKey == 0) config.Hotkey = new HotkeyConfig();
        config.AllowlistProcessNames = config.AllowlistProcessNames.Where(x => !string.IsNullOrWhiteSpace(x))
            .Select(x => x.Trim()).Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
        if (config.CleanupMode is not ("foreground_only" or "foreground_and_background"))
            config.CleanupMode = "foreground_and_background";
    }
}
