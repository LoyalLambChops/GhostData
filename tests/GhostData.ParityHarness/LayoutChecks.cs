using Avalonia;
using GhostData.App.Services;
using GhostData.App.Models;
using GhostData.App.ViewModels;

internal static class LayoutChecks
{
    internal static void Run()
    {
        var cases = new[]
        {
            (new GameWindowBounds(0, 0, 2560, 1440), 1d),
            (new GameWindowBounds(0, 0, 1920, 1080), 1d),
            (new GameWindowBounds(0, 0, 1280, 720), 1d),
            (new GameWindowBounds(0, 0, 2560, 1440), 1.5d),
            (new GameWindowBounds(-2560, 0, 0, 1440), 1.25d),
            (new GameWindowBounds(100, 80, 1700, 980), 1d),
        };
        foreach (var (game, scale) in cases)
        {
            var layout = HearthstoneOverlayLayoutCalculator.Calculate(game, scale,
                new PixelRect(game.Left, game.Top, game.Width, game.Height));
            var width = (int)Math.Round(layout.RailWidthDip * scale);
            var height = (int)Math.Round(layout.RailHeightDip * scale);
            if (layout.RailWidthDip > 220 || layout.RailHeightDip > 780
                || layout.OpponentRailPosition.X < game.Left
                || layout.PlayerRailPosition.X + width > game.Right
                || layout.OpponentRailPosition.Y < game.Top
                || layout.PlayerRailPosition.Y + height > game.Bottom - game.Height * .25 + 1)
                throw new Exception($"Rail intrudes into protected lower quarter: {game}, scale {scale}");
        }
        var unknown = new PlayerRailViewModel();
        unknown.Apply(new TrackerStateDto { PlayerHandCount = 7 });
        if (unknown.CountLine != "DECK ? · HAND 7")
            throw new Exception("Missing deck count must not conceal the known hand total");
        if (RailHoverPreview.PreviewText("Example", "[x]<b>Deal $3 damage.</b>") != "Example\n\nDeal 3 damage.")
            throw new Exception("Hover must retain readable rules text without requiring artwork");
        if (!RailHoverPreview.PreviewText("Example", "").Contains("unavailable"))
            throw new Exception("Missing local card text must be explicit");
        Console.WriteLine("Passed 9 compact layout and text-preview checks.");
    }
}
