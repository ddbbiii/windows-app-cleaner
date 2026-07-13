using System.Drawing;
using System.Drawing.Drawing2D;
using WindowsAppCleaner.Interop;

namespace WindowsAppCleaner.Services;

internal static class TrayIconFactory
{
    internal static Icon Create()
    {
        using var bitmap = new Bitmap(64, 64);
        using (var graphics = Graphics.FromImage(bitmap))
        {
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            graphics.Clear(Color.Transparent);
            using var teal = new SolidBrush(Color.FromArgb(13, 148, 136));
            using var tealLight = new SolidBrush(Color.FromArgb(55, 190, 181));
            using var white = new SolidBrush(Color.White);
            using var orange = new SolidBrush(Color.FromArgb(255, 138, 19));
            graphics.FillEllipse(teal, 3, 3, 58, 58);
            graphics.FillEllipse(tealLight, 9, 9, 46, 46);
            graphics.FillPolygon(white, [new PointF(36, 13), new PointF(48, 16), new PointF(45, 28), new PointF(27, 46), new PointF(18, 37), new PointF(36, 19)]);
            graphics.FillPolygon(white, [new PointF(22, 28), new PointF(12, 27), new PointF(9, 36), new PointF(18, 38)]);
            graphics.FillPolygon(white, [new PointF(34, 42), new PointF(36, 53), new PointF(46, 48), new PointF(44, 36)]);
            graphics.FillEllipse(teal, 34, 20, 7, 7);
            graphics.FillPolygon(orange, [new PointF(22, 42), new PointF(13, 53), new PointF(28, 46)]);
        }
        var handle = bitmap.GetHicon();
        try { using var temporary = Icon.FromHandle(handle); return (Icon)temporary.Clone(); }
        finally { NativeMethods.DestroyIcon(handle); }
    }
}
