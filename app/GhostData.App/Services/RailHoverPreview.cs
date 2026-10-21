using System.Diagnostics;
using System.Runtime.InteropServices;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Avalonia.Threading;
using Avalonia.VisualTree;
using GhostData.App.Models;
using GhostData.App.ViewModels;

namespace GhostData.App.Services;

/// <summary>One cursor sampler and one preview window for all click-through rails.</summary>
public static class RailHoverPreview
{
    private static readonly List<Window> Rails = new();
    private static readonly DispatcherTimer Timer = new() { Interval = TimeSpan.FromMilliseconds(50) };
    private static readonly HookProc WheelCallback = OnMouse;
    private static IntPtr _hook;
    private static Window? _popup;
    private static TextBlock? _fallback;
    private static string _cardId = "";
    private static (string Id, string Name, string Detail) _card;
    private static long _entered;
    private static bool _requested;
    private static Window? _rail;

    static RailHoverPreview() => Timer.Tick += (_, _) => Tick();

    public static void Attach(Window rail)
    {
        Rails.Add(rail);
        rail.PropertyChanged += (_, e) => { if (e.Property == Visual.IsVisibleProperty) UpdateActivity(); };
        rail.Closed += (_, _) =>
        {
            Rails.Remove(rail);
            if (_rail == rail) Hide();
            UpdateActivity();
            if (Rails.Count == 0) { _popup?.Close(); _popup = null; }
        };
        rail.Opened += (_, _) => UpdateActivity();
    }

    private static void UpdateActivity()
    {
        if (Rails.Any(w => w.IsVisible) && OperatingSystem.IsWindows())
        {
            Timer.Start();
            if (_hook == IntPtr.Zero) _hook = SetWindowsHookEx(14, WheelCallback, GetModuleHandle(null), 0);
        }
        else
        {
            Timer.Stop(); Hide();
            if (_hook != IntPtr.Zero) { UnhookWindowsHookEx(_hook); _hook = IntPtr.Zero; }
        }
    }

    public static (string Id, string Name, string Detail) CardFor(object? data) => data switch
    {
        DisplayCardViewModel card => (card.CardId, card.Name, card.PreviewText),
        HeroZoneEffectViewModel effect => (effect.CardId, effect.Name, effect.PreviewText),
        SecretCandidateViewModel secret => (secret.CardId, secret.Name, secret.Text),
        HandSlotDto hand => (hand.CardId, hand.Name, hand.Text),
        _ => ("", "", "")
    };

    private static void Tick()
    {
        if (!HearthstoneWindowLocator.IsRelevantForeground()) { Hide(); return; }
        if (!GetCursorPos(out var cursor) || (GetAsyncKeyState(1) & 0x8000) != 0) { Hide(); return; }
        var screenPoint = new PixelPoint(cursor.X, cursor.Y);
        Window? foundRail = null;
        Control? foundRow = null;
        (string Id, string Name, string Detail) card = ("", "", "");
        foreach (var rail in Rails.Where(w => w.IsVisible))
        {
            var point = rail.PointToClient(screenPoint);
            if (!new Rect(rail.Bounds.Size).Contains(point)) continue;
            if (rail.InputHitTest(point) is not Visual hit) continue;
            foreach (var control in hit.GetSelfAndVisualAncestors().OfType<Control>())
            {
                card = CardFor(control.DataContext);
                if (string.IsNullOrEmpty(card.Id)) continue;
                foundRail = rail; foundRow = control; break;
            }
            break;
        }
        if (foundRail is null || foundRow is null) { Hide(); return; }
        if (_card != card || _rail != foundRail)
        {
            Hide(); _card = card; _cardId = card.Id; _rail = foundRail; _entered = Stopwatch.GetTimestamp();
        }
        if (Stopwatch.GetElapsedTime(_entered).TotalMilliseconds < 150) return;
        EnsurePopup();
        PlacePopup(foundRail, foundRow);
        if (!_requested)
        {
            _requested = true;
            _fallback!.Text = PreviewText(card.Name, card.Detail);
            _popup!.Show();
        }
    }

    private static string CleanText(string value) => System.Text.RegularExpressions.Regex.Replace(value ?? "", "<[^>]*>|\\[x\\]", "").Replace("$", "").Replace("#", "");

    public static string PreviewText(string name, string detail) => name + "\n\n"
        + (string.IsNullOrWhiteSpace(detail) ? "Card text unavailable in local data." : CleanText(detail));

    private static void EnsurePopup()
    {
        if (_popup is not null) return;
        _fallback = new TextBlock { FontSize = 16, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(20), Foreground = Brushes.White };
        _popup = new Window
        {
            Width = 280, Height = 340, Title = "GhostData · Card details", Topmost = true,
            CanResize = false, ShowActivated = false, ShowInTaskbar = false, Focusable = false,
            WindowDecorations = WindowDecorations.None, Background = Brush.Parse("#0B1520"),
            Content = new ScrollViewer { Content = _fallback },
        };
        _popup.Opened += (_, _) => WindowsRailOverlay.Apply(_popup);
    }

    public static PixelPoint Position(PixelRect rail, PixelRect area, PixelSize popup, int rowY)
    {
        var rightSide = rail.X + rail.Width / 2 > area.X + area.Width / 2;
        var x = rightSide ? rail.X - popup.Width - 8 : rail.Right + 8;
        return new PixelPoint(Math.Clamp(x, area.X, Math.Max(area.X, area.Right - popup.Width)),
            Math.Clamp(rowY, area.Y, Math.Max(area.Y, area.Bottom - popup.Height)));
    }

    private static void PlacePopup(Window rail, Control row)
    {
        var screen = rail.Screens.ScreenFromWindow(rail) ?? rail.Screens.Primary;
        if (screen is null) return;
        var scale = rail.RenderScaling;
        var size = new PixelSize((int)(_popup!.Width * scale), (int)(_popup.Height * scale));
        var bounds = new PixelRect(rail.PointToScreen(default), new PixelSize((int)(rail.Bounds.Width * scale), (int)(rail.Bounds.Height * scale)));
        _popup.Position = Position(bounds, screen.WorkingArea, size, row.PointToScreen(default).Y);
    }

    private static void Hide()
    {
        if (_cardId.Length == 0) return;
        _cardId = ""; _card = default; _rail = null; _requested = false;
        _popup?.Hide();
    }

    // Scroll only a rail under the pointer. Every click and all other mouse
    // input continue unchanged to Hearthstone; no window is activated.
    private static IntPtr OnMouse(int code, IntPtr message, IntPtr data)
    {
        try
        {
            if (code >= 0 && message.ToInt64() == 0x020A && HearthstoneWindowLocator.IsRelevantForeground())
            {
                var mouse = Marshal.PtrToStructure<MouseData>(data);
                foreach (var rail in Rails.Where(w => w.IsVisible))
                {
                    var point = rail.PointToClient(new PixelPoint(mouse.Point.X, mouse.Point.Y));
                    if (!new Rect(rail.Bounds.Size).Contains(point)) continue;
                    var scroll = rail.GetVisualDescendants().OfType<ScrollViewer>().FirstOrDefault();
                    if (scroll is null || scroll.Extent.Height <= scroll.Viewport.Height) break;
                    var delta = (short)(mouse.Data >> 16);
                    Dispatcher.UIThread.Post(() =>
                    {
                        Hide();
                        scroll.Offset = new Vector(0, Math.Clamp(scroll.Offset.Y - delta / 120.0 * 90,
                            0, Math.Max(0, scroll.Extent.Height - scroll.Viewport.Height)));
                    });
                    return new IntPtr(1);
                }
            }
        }
        catch (Exception) { /* A presentation failure must never interrupt global mouse input. */ }
        return CallNextHookEx(_hook, code, message, data);
    }

    [StructLayout(LayoutKind.Sequential)] private struct PointNative { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] private struct MouseData { public PointNative Point; public uint Data, Flags, Time; public UIntPtr Extra; }
    private delegate IntPtr HookProc(int code, IntPtr message, IntPtr data);
    [DllImport("user32.dll")] private static extern bool GetCursorPos(out PointNative point);
    [DllImport("user32.dll")] private static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll")] private static extern IntPtr SetWindowsHookEx(int id, HookProc callback, IntPtr module, uint thread);
    [DllImport("user32.dll")] private static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string? name);
}
