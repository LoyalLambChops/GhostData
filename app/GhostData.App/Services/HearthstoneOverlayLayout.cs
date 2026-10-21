using Avalonia;

namespace GhostData.App.Services;

public readonly record struct HearthstoneOverlayLayout(
    PixelPoint OpponentRailPosition,
    PixelPoint PlayerRailPosition,
    double RailWidthDip,
    double RailHeightDip,
    int SideInsetPx);

/// <summary>
/// Resolution-independent presentation geometry for the GhostData deck rails.
/// All decisions are derived from the current Hearthstone client rectangle, so the
/// layout adapts continuously to native resolution/window-size choices rather than
/// relying on a hard-coded resolution table.
/// </summary>
public static class HearthstoneOverlayLayoutCalculator
{
    public const double RailWidthRatio = 0.09;
    public const double RailMinWidthDip = 180;
    public const double RailMaxWidthDip = 220;

    public static HearthstoneOverlayLayout Calculate(
        GameWindowBounds game,
        double scale,
        PixelRect workingArea)
    {
        scale = scale <= 0 ? 1.0 : scale;

        var gameWidthDip = game.Width / scale;
        var railWidthDip = Math.Clamp(gameWidthDip * RailWidthRatio, RailMinWidthDip, RailMaxWidthDip);
        var railWidthPx = Math.Max(1, (int)Math.Round(railWidthDip * scale));

        var sideInsetPx = (int)Math.Clamp(
            game.Width * 0.012,
            Math.Round(8 * scale),
            Math.Round(24 * scale));

        // Leave the Hearthstone player-name/banner region unobstructed.
        var topInsetPx = (int)Math.Clamp(
            game.Height * 0.115,
            Math.Round(76 * scale),
            Math.Round(140 * scale));
        // The lower quarter contains the local player banner and hand. Preserve
        // that space at every resolution rather than capping its inset in pixels.
        var bottomInsetPx = (int)Math.Round(game.Height * 0.25);

        var availableHeightPx = Math.Max(1, Math.Min(
            game.Height - topInsetPx - bottomInsetPx,
            workingArea.Height - 4));
        var railHeightDip = Math.Min(availableHeightPx / scale, 780);
        var railHeightPx = Math.Max(1, (int)Math.Round(railHeightDip * scale));

        // Opponent LEFT, player RIGHT, both inside the game client frame.
        var opponentX = game.Left + sideInsetPx;
        var playerX = game.Right - sideInsetPx - railWidthPx;

        // Keep vertical placement within both the game surface and monitor work area.
        var preferredY = game.Top + topInsetPx;
        var maxGameY = game.Bottom - bottomInsetPx - railHeightPx;
        var maxWorkY = workingArea.Y + workingArea.Height - railHeightPx - 2;
        var y = Math.Clamp(
            preferredY,
            Math.Max(game.Top + 2, workingArea.Y + 2),
            Math.Max(Math.Max(game.Top + 2, workingArea.Y + 2), Math.Min(maxGameY, maxWorkY)));

        return new HearthstoneOverlayLayout(
            new PixelPoint(opponentX, y),
            new PixelPoint(playerX, y),
            railWidthDip,
            railHeightDip,
            sideInsetPx);
    }
}

