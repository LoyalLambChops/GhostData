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
    private static TrackerStateDto? _handState;
    private static int _hoveredEntity;
    private static string _hoveredCard="";
    private static long _sensorAt;
    private static long _textAt;
    private static readonly Dictionary<int,(string CardId,string Text)> HandText=new();

    public static void ApplyHandState(TrackerStateDto state)
    {
        if(_handState?.GameNumber!=state.GameNumber || !state.Active || state.Complete)ClearHandSensor();
        _handState=state;
    }
    public static void ClearHandSensor()
    {
        _hoveredEntity=0;_hoveredCard="";HandText.Clear();_sensorAt=0;_textAt=0;
    }
    public static void ApplyHandSensor(System.Text.Json.JsonElement root)
    {
        _sensorAt=Stopwatch.GetTimestamp();_hoveredEntity=0;_hoveredCard="";
        if(root.TryGetProperty("hand",out var hand) && hand.ValueKind==System.Text.Json.JsonValueKind.Array)
        {
            HandText.Clear();_textAt=_sensorAt;
            foreach(var row in hand.EnumerateArray())
            {
                var id=row.GetProperty("entity_id").GetInt32();
                HandText[id]=(row.GetProperty("card_id").GetString()??"",row.GetProperty("text").GetString()??"");
            }
        }
        if(root.TryGetProperty("hover",out var hover) && hover.ValueKind==System.Text.Json.JsonValueKind.Object)
        {
            _hoveredEntity=hover.GetProperty("entity_id").GetInt32();
            _hoveredCard=hover.GetProperty("card_id").GetString()??"";
        }
    }
    public static HandSlotDto? ResolveHand(TrackerStateDto? state,int entityId,string cardId) =>
        state is {Active:true,Complete:false} && entityId>0 && cardId.Length>0
            ? state.PlayerHand.SingleOrDefault(h=>h.EntityId==entityId && h.CardId==cardId) : null;
    public static string HandDetail(HandSlotDto slot,string? rendered=null)
    {
        var text=CardTextFormatter.Format(string.IsNullOrWhiteSpace(rendered)?slot.Text:rendered);
        if(slot.RelatedLabel.Length>0)text+="\n\n"+slot.RelatedLabel;
        foreach(var related in slot.RelatedCards)text+="\n• "+related.Name+(related.Count>1?$" ×{related.Count}":"");
        return text;
    }
    private static string HandDetail(HandSlotDto slot)
    {
        var rendered=_textAt!=0 && Stopwatch.GetElapsedTime(_textAt).TotalSeconds<2
            && HandText.TryGetValue(slot.EntityId,out var row) && row.CardId==slot.CardId ? row.Text : null;
        return HandDetail(slot,rendered);
    }
    private static (string Id,string Name,string Detail) Enrich((string Id,string Name,string Detail) card)
    {
        var slots=_handState is {Active:true,Complete:false} ? _handState.PlayerHand.Where(h=>h.CardId==card.Id).ToArray() : Array.Empty<HandSlotDto>();
        if(slots.Length==1)return (card.Id,card.Name,HandDetail(slots[0]));
        if(slots.Length>1 && slots.Any(h=>h.RelatedLabel.Length>0))
            return (card.Id,card.Name,string.Join("\n\n",slots.Select(h=>$"Hand position {h.Position}\n{HandDetail(h)}")));
        return (card.Id,card.Name,CleanText(card.Detail));
    }

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
                card = Enrich(CardFor(control.DataContext));
                if (string.IsNullOrEmpty(card.Id)) continue;
                foundRail = rail; foundRow = control; break;
            }
            break;
        }
        var inHand=false;
        if (foundRail is null || foundRow is null)
        {
            var slot=_sensorAt!=0 && Stopwatch.GetElapsedTime(_sensorAt).TotalMilliseconds<500
                ? ResolveHand(_handState,_hoveredEntity,_hoveredCard) : null;
            if(slot is null || !HearthstoneWindowLocator.IsGameForeground() || !Rails.Any(w=>w.IsVisible)) { Hide(); return; }
            foundRail=Rails.OfType<PlayerDeckWindow>().FirstOrDefault(w=>w.IsVisible);
            if(foundRail is null){Hide();return;}
            card=($"{slot.CardId}:{slot.EntityId}",slot.Name,HandDetail(slot));inHand=true;
        }
        if (_card != card || _rail != foundRail)
        {
            Hide(); _card = card; _cardId = card.Id; _rail = foundRail; _entered = Stopwatch.GetTimestamp();
        }
        if (Stopwatch.GetElapsedTime(_entered).TotalMilliseconds < 150) return;
        EnsurePopup();
        if(inHand)
        {
            var screen=foundRail.Screens.ScreenFromPoint(screenPoint) ?? foundRail.Screens.Primary;
            if(screen is null){Hide();return;}
            var scale=screen.Scaling;
            var area=screen.WorkingArea;
            var width=(int)(_popup!.Width*scale);var height=(int)(_popup.Height*scale);
            _popup.Position=new PixelPoint(Math.Clamp(screenPoint.X-width-30,area.X,Math.Max(area.X,area.Right-width)),
                Math.Clamp(screenPoint.Y-height-45,area.Y,Math.Max(area.Y,area.Bottom-height)));
        }
        else PlacePopup(foundRail, foundRow!);
        if (!_requested)
        {
            _requested = true;
            _fallback!.Text = card.Name + "\n\n" + (string.IsNullOrWhiteSpace(card.Detail) ? "Card text unavailable in local data." : card.Detail);
            _popup!.Show();
        }
    }

    private static string CleanText(string value) => CardTextFormatter.Format(value);

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
