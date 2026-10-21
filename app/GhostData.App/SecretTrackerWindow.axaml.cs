using Avalonia.Controls;
using Avalonia.Markup.Xaml;
using GhostData.App.Services;
using GhostData.App.ViewModels;
namespace GhostData.App;
public sealed partial class SecretTrackerWindow : Window
{
    public SecretRailViewModel ViewModel { get; } = new();
    public SecretTrackerWindow()
    {
        AvaloniaXamlLoader.Load(this); DataContext = ViewModel;
        RailHoverPreview.Attach(this);
        Opened += (_, _) => WindowsRailOverlay.Apply(this);
    }
}
