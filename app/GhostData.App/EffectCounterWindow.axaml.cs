using Avalonia.Controls;
using Avalonia.Markup.Xaml;
using GhostData.App.Models;
using GhostData.App.Services;

namespace GhostData.App;

public sealed partial class EffectCounterWindow : Window
{
    public EffectCounterWindow()
    {
        AvaloniaXamlLoader.Load(this);
        RailHoverPreview.Attach(this);
        Opened += (_, _) => WindowsRailOverlay.Apply(this);
    }
    public void Apply(TrackerStateDto state) => this.FindControl<ItemsControl>("Counters")!.ItemsSource = state.PlayerCounters;
}
