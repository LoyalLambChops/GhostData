using Avalonia;
using GhostData.App.Services;

namespace GhostData.App;

internal static class Program
{
    internal static SingleInstance? Instance { get; private set; }

    [STAThread]
    public static void Main(string[] args)
    {
        // Isolated rendering never activates or replaces a real user's session.
        if (!OperatingSystem.IsWindows() || args.Contains("--preview"))
        {
            BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
            return;
        }
        using var instance = new SingleInstance();
        if (!instance.IsPrimary) return;
        Instance = instance;
        try { BuildAvaloniaApp().StartWithClassicDesktopLifetime(args); }
        finally { Instance = null; }
    }

    public static AppBuilder BuildAvaloniaApp() =>
        AppBuilder.Configure<App>().UsePlatformDetect().LogToTrace();
}
