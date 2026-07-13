using WindowsAppCleaner.Services;

namespace WindowsAppCleaner.Tests;

public sealed class HotkeyServiceTests
{
    [Theory]
    [InlineData("F4", 0u, 0x73u, "F4")]
    [InlineData("Ctrl+Alt+K", 3u, 0x4Bu, "Ctrl+Alt+K")]
    public void ParsesSupportedHotkeys(string text, uint modifiers, uint key, string display)
    {
        Assert.True(HotkeyService.TryParse(text, out var config));
        Assert.Equal(modifiers, config.Modifiers);
        Assert.Equal(key, config.VirtualKey);
        Assert.Equal(display, config.Display);
    }

    [Theory]
    [InlineData("K")]
    [InlineData("Ctrl+NoSuchKey")]
    [InlineData("F25")]
    public void RejectsUnsafeOrUnknownHotkeys(string text) => Assert.False(HotkeyService.TryParse(text, out _));
}
