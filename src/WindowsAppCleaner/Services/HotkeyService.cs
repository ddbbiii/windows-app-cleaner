using System.Globalization;
using System.Windows.Interop;
using WindowsAppCleaner.Interop;
using WindowsAppCleaner.Models;

namespace WindowsAppCleaner.Services;

public sealed class HotkeyService : IDisposable
{
    private const int HotkeyId = 0xAC11;
    private HwndSource? _source;
    private HotkeyConfig? _registered;
    private Action? _handler;

    public void Attach(nint hwnd, HotkeyConfig config, Action handler)
    {
        _source = HwndSource.FromHwnd(hwnd);
        _source.AddHook(WndProc);
        _handler = handler;
        if (!TryRegister(config)) throw new InvalidOperationException($"快捷键 {config.Display} 已被其他程序占用。");
    }

    public bool Change(HotkeyConfig config)
    {
        if (_source is null) return false;
        var previous = _registered;
        if (previous is not null) NativeMethods.UnregisterHotKey(_source.Handle, HotkeyId);
        if (TryRegister(config)) return true;
        if (previous is not null) TryRegister(previous);
        return false;
    }

    public static bool TryParse(string text, out HotkeyConfig config)
    {
        config = new HotkeyConfig();
        var tokens = text.Split('+', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (tokens.Length == 0) return false;
        uint modifiers = 0;
        foreach (var token in tokens[..^1])
            modifiers |= token.ToUpperInvariant() switch { "CTRL" or "CONTROL" => 2u, "ALT" => 1u, "SHIFT" => 4u, "WIN" => 8u, _ => 0x80000000u };
        if ((modifiers & 0x80000000) != 0) return false;
        var key = tokens[^1].ToUpperInvariant();
        uint vk;
        if (key.StartsWith('F') && int.TryParse(key[1..], NumberStyles.None, CultureInfo.InvariantCulture, out var f) && f is >= 1 and <= 24)
            vk = (uint)(0x6F + f);
        else if (key.Length == 1 && char.IsLetterOrDigit(key[0]) && modifiers != 0) vk = key[0];
        else return false;
        config = new HotkeyConfig { Modifiers = modifiers, VirtualKey = vk, Display = string.Join('+', tokens.Select(NormalizeToken)) };
        return true;
    }

    private static string NormalizeToken(string value) => value.ToUpperInvariant() switch
    {
        "CTRL" or "CONTROL" => "Ctrl", "ALT" => "Alt", "SHIFT" => "Shift", "WIN" => "Win", _ => value.ToUpperInvariant(),
    };

    private bool TryRegister(HotkeyConfig config)
    {
        if (_source is null || !NativeMethods.RegisterHotKey(_source.Handle, HotkeyId, config.Modifiers, config.VirtualKey)) return false;
        _registered = config;
        return true;
    }

    private nint WndProc(nint hwnd, int message, nint wParam, nint lParam, ref bool handled)
    {
        if (message == NativeMethods.WmHotkey && wParam.ToInt32() == HotkeyId)
        {
            handled = true;
            _handler?.Invoke();
        }
        return 0;
    }

    public void Dispose()
    {
        if (_source is not null)
        {
            NativeMethods.UnregisterHotKey(_source.Handle, HotkeyId);
            _source.RemoveHook(WndProc);
        }
    }
}
