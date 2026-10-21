using Avalonia.Controls;
using Avalonia.Markup.Xaml;
using GhostData.App.Services;
using GhostData.App.ViewModels;

namespace GhostData.App;

public sealed partial class OpponentDeckWindow : Window
{
    public OpponentRailViewModel ViewModel { get; } = new();

    public OpponentDeckWindow()
    {
        AvaloniaXamlLoader.Load(this);
        DataContext = ViewModel;
        RailHoverPreview.Attach(this);
        Opened += (_, _) => WindowsRailOverlay.Apply(this);
    }
}

