using System.Runtime.InteropServices;
using Avalonia.Controls;
using Avalonia.Platform;

namespace GhostData.App.Services;

public static class WindowsRailOverlay
{
    private const int GwlExStyle = -20;
    private const long WsExTransparent = 0x00000020L;
    private const long WsExToolWindow = 0x00000080L;
    private const long WsExNoActivate = 0x08000000L;

    /// <summary>
    /// Make a rail presentation-only on Windows: no taskbar button, no activation,
    /// and mouse input passes through to Hearthstone when the rail must sit inside
    /// the client bounds (for example on a maximized display).
    /// </summary>
    public static void Apply(Window window)
    {
        WindowsOverlayChrome.Apply(window);
        if (!OperatingSystem.IsWindows())
            return;

        try
        {
            var handle = window.TryGetPlatformHandle()?.Handle ?? IntPtr.Zero;
            if (handle == IntPtr.Zero)
                return;

            var style = GetWindowLongPtr(handle, GwlExStyle).ToInt64();
            style |= WsExTransparent | WsExToolWindow | WsExNoActivate;
            _ = SetWindowLongPtr(handle, GwlExStyle, new IntPtr(style));
        }
        catch
        {
            // Presentation hardening only.  Rail windows are already borderless,
            // non-focusable Avalonia windows and tracking truth lives in Python.
        }
    }

    private static IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex) =>
        IntPtr.Size == 8 ? GetWindowLongPtr64(hWnd, nIndex) : new IntPtr(GetWindowLong32(hWnd, nIndex));

    private static IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong) =>
        IntPtr.Size == 8 ? SetWindowLongPtr64(hWnd, nIndex, dwNewLong) : new IntPtr(SetWindowLong32(hWnd, nIndex, dwNewLong.ToInt32()));

    [DllImport("user32.dll", EntryPoint = "GetWindowLong")]
    private static extern int GetWindowLong32(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtr")]
    private static extern IntPtr GetWindowLongPtr64(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll", EntryPoint = "SetWindowLong")]
    private static extern int SetWindowLong32(IntPtr hWnd, int nIndex, int dwNewLong);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtr")]
    private static extern IntPtr SetWindowLongPtr64(IntPtr hWnd, int nIndex, IntPtr dwNewLong);
}

