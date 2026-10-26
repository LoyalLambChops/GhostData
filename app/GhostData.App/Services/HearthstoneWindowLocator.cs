using System.Diagnostics;
using System.Runtime.InteropServices;

namespace GhostData.App.Services;

public readonly record struct GameWindowBounds(int Left, int Top, int Right, int Bottom)
{
    public int Width => Math.Max(0, Right - Left);
    public int Height => Math.Max(0, Bottom - Top);
    public bool Valid => Width > 0 && Height > 0;
}

public interface IGameWindowLocator
{
    bool TryGetHearthstoneBounds(out GameWindowBounds bounds);
}

public sealed class HearthstoneWindowLocator : IGameWindowLocator
{
    private IntPtr _cachedHandle;
    private DateTime _nextLookup;
    private static uint _gamePid;

    public static bool IsGameForeground()
    {
        if(!OperatingSystem.IsWindows())return false;
        GetWindowThreadProcessId(GetForegroundWindow(),out var pid);
        return _gamePid!=0 && pid==_gamePid;
    }

    public static bool IsRelevantForeground()
    {
        if (!OperatingSystem.IsWindows()) return false;
        GetWindowThreadProcessId(GetForegroundWindow(), out var pid);
        return pid == Environment.ProcessId || (_gamePid != 0 && pid == _gamePid);
    }

    public bool TryGetHearthstoneBounds(out GameWindowBounds bounds)
    {
        bounds = default;
        if (!OperatingSystem.IsWindows())
            return false;

        try
        {
            if (_cachedHandle != IntPtr.Zero && IsWindow(_cachedHandle))
            {
                GetWindowThreadProcessId(_cachedHandle, out var pid);
                if (pid == _gamePid)
                    return IsRelevantForeground() && !IsIconic(_cachedHandle) && IsWindowVisible(_cachedHandle)
                        && TryGetClientScreenRect(_cachedHandle, out bounds);
            }
            _cachedHandle = IntPtr.Zero;
            if (DateTime.UtcNow < _nextLookup) return false;
            _nextLookup = DateTime.UtcNow.AddSeconds(1);
            foreach (var process in Process.GetProcessesByName("Hearthstone"))
            {
                using (process)
                {
                    var handle = process.MainWindowHandle;
                    if (handle == IntPtr.Zero || IsIconic(handle) || !IsWindowVisible(handle))
                        continue;
                    _cachedHandle = handle;
                    _gamePid = (uint)process.Id;
                    if (!IsRelevantForeground()) return false;

                    // v46.3.1 anchors overlays to Hearthstone's *client* rectangle,
                    // not its outer Win32 frame. This keeps rails inside the rendered
                    // game surface across windowed/fullscreen resolutions and avoids
                    // title-bar/border drift on Windows 11.
                    if (TryGetClientScreenRect(handle, out var client))
                    {
                        bounds = client;
                        return true;
                    }

                    // Presentation-only fallback for unusual window states where the
                    // client rect cannot be mapped. Never make coaching depend on it.
                    if (!GetWindowRect(handle, out var frame))
                        continue;
                    var candidate = new GameWindowBounds(frame.Left, frame.Top, frame.Right, frame.Bottom);
                    if (candidate.Valid)
                    {
                        bounds = candidate;
                        return true;
                    }
                }
            }
        }
        catch
        {
            // Game-window anchoring is presentation-only. Failure must never stop coaching.
        }
        return false;
    }

    private static bool TryGetClientScreenRect(IntPtr handle, out GameWindowBounds bounds)
    {
        bounds = default;
        if (!GetClientRect(handle, out var client))
            return false;

        var topLeft = new POINT { X = client.Left, Y = client.Top };
        var bottomRight = new POINT { X = client.Right, Y = client.Bottom };
        if (!ClientToScreen(handle, ref topLeft) || !ClientToScreen(handle, ref bottomRight))
            return false;

        var candidate = new GameWindowBounds(topLeft.X, topLeft.Y, bottomRight.X, bottomRight.Y);
        if (!candidate.Valid)
            return false;
        bounds = candidate;
        return true;
    }

    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [DllImport("user32.dll")] private static extern bool IsWindow(IntPtr window);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(IntPtr hWnd);
}

