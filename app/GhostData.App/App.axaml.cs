using Avalonia;
using Avalonia.Controls;
using Avalonia.Threading;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using GhostData.App.Services;

namespace GhostData.App;

public sealed partial class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var options = StartupOptions.Parse(desktop.Args ?? Array.Empty<string>());
            desktop.MainWindow = new DashboardWindow(options);
            Program.Instance?.OnActivate(() => Dispatcher.UIThread.Post(() =>
            {
                var window = desktop.MainWindow;
                if (window is null) return;
                window.Show();
                if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
                window.Activate();
            }));
        }
        base.OnFrameworkInitializationCompleted();
    }
}
