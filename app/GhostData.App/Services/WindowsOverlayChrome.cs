using System.Runtime.InteropServices;
using Avalonia.Controls;
using Avalonia.Platform;

namespace GhostData.App.Services;

public static class WindowsOverlayChrome
{
    // Windows 11 native rounded corners without layered-window transparency.
    // This keeps the reliable opaque compositor path established after the Qt failure.
    public static void Apply(Window window)
    {
        if (!OperatingSystem.IsWindows())
            return;
        try
        {
            var handle = window.TryGetPlatformHandle()?.Handle ?? IntPtr.Zero;
            if (handle == IntPtr.Zero)
                return;
            const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
            var preference = 2; // DWMWCP_ROUND
            _ = DwmSetWindowAttribute(
                handle,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ref preference,
                Marshal.SizeOf<int>());
        }
        catch
        {
            // Cosmetic only; the opaque borderless rail remains usable without DWM rounding.
        }
    }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(
        IntPtr hwnd,
        int dwAttribute,
        ref int pvAttribute,
        int cbAttribute);
}

