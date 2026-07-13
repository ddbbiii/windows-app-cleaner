using System.Drawing;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using WindowsAppCleaner.Interop;

namespace WindowsAppCleaner.Services;

public sealed class IconService
{
    private readonly Dictionary<string, ImageSource?> _cache = new(StringComparer.OrdinalIgnoreCase);

    public ImageSource? Get(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path)) return null;
        if (_cache.TryGetValue(path, out var cached)) return cached;
        try
        {
            using var icon = Icon.ExtractAssociatedIcon(path);
            if (icon is null) return _cache[path] = null;
            var source = Imaging.CreateBitmapSourceFromHIcon(icon.Handle, Int32Rect.Empty, BitmapSizeOptions.FromWidthAndHeight(32, 32));
            source.Freeze();
            return _cache[path] = source;
        }
        catch { return _cache[path] = null; }
    }
}
