using System.Collections.Specialized;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using GhostData.App.ViewModels;

namespace GhostData.App.Controls;

public sealed class StatisticsDonut : Control
{
    public static readonly StyledProperty<IEnumerable<ChartBar>?> ItemsProperty =
        AvaloniaProperty.Register<StatisticsDonut, IEnumerable<ChartBar>?>(nameof(Items));

    public IEnumerable<ChartBar>? Items { get => GetValue(ItemsProperty); set => SetValue(ItemsProperty, value); }

    protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
    {
        base.OnPropertyChanged(change);
        if (change.Property != ItemsProperty) return;
        if (change.OldValue is INotifyCollectionChanged oldItems) oldItems.CollectionChanged -= ItemsChanged;
        if (change.NewValue is INotifyCollectionChanged newItems) newItems.CollectionChanged += ItemsChanged;
        InvalidateVisual();
    }

    private void ItemsChanged(object? sender, NotifyCollectionChangedEventArgs e) => InvalidateVisual();

    public override void Render(DrawingContext context)
    {
        base.Render(context);
        var center = new Point(Bounds.Width / 2, Bounds.Height / 2);
        var outer = Math.Max(0, Math.Min(Bounds.Width, Bounds.Height) / 2 - 2);
        var inner = outer * .76;
        context.DrawEllipse(null, new Pen(Brush.Parse("#24333D"), outer - inner), center,
            (outer + inner) / 2, (outer + inner) / 2);
        var angle = -Math.PI / 2;
        foreach (var item in Items ?? Enumerable.Empty<ChartBar>())
        {
            if (item.Percent <= 0) continue;
            var sweep = Math.Min(100, item.Percent) * Math.PI / 50;
            var steps = Math.Max(2, (int)Math.Ceiling(sweep * 35));
            Point At(double radius, double a) => center + new Vector(Math.Cos(a) * radius, Math.Sin(a) * radius);
            var geometry = new StreamGeometry();
            using (var path = geometry.Open())
            {
                path.BeginFigure(At(outer, angle), true);
                for (var i = 1; i <= steps; i++) path.LineTo(At(outer, angle + sweep * i / steps));
                for (var i = steps; i >= 0; i--) path.LineTo(At(inner, angle + sweep * i / steps));
                path.EndFigure(true);
            }
            context.DrawGeometry(item.Color, null, geometry);
            angle += sweep;
        }
    }
}
