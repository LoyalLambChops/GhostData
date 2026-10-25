using Avalonia;
using Avalonia.Controls;
using Avalonia.Threading;
using GhostData.App.Models;

namespace GhostData.App.Services;

public sealed class DeckRailCoordinator : IAsyncDisposable
{
    private readonly Window _owner;
    private readonly StartupOptions _options;
    private readonly PlayerDeckWindow _playerRail = new();
    private readonly OpponentDeckWindow _opponentRail = new();
    private readonly SecretTrackerWindow _secretRail = new();
    private readonly IGameWindowLocator _gameWindowLocator = new HearthstoneWindowLocator();
    private readonly DispatcherTimer _placementTimer;
    private readonly object _pendingGate = new();
    private TrackerBackendProcess? _backend;
    private TrackerStateDto? _latest;
    private TrackerStateDto? _pending;
    private bool _playerShown;
    private bool _opponentShown;
    public bool Enabled { get; set; } = true;
    public event Action<string>? Failed;

    public DeckRailCoordinator(Window owner, StartupOptions options)
    {
        _owner = owner;
        _options = options;
        _placementTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(150) };
        _placementTimer.Tick += (_, _) =>
        {
            DrainPending();
            UpdatePlacementAndVisibility();
        };
    }

    public async Task StartAsync()
    {
        _placementTimer.Start();
        _backend = new TrackerBackendProcess(_options);
        _backend.EnvelopeReceived += OnEnvelope;
        _backend.Failed += message => Dispatcher.UIThread.Post(()=>{lock(_pendingGate)_pending=null;_latest=null;Hide();Failed?.Invoke(message);});
        await _backend.StartAsync();
    }

    private void OnEnvelope(TrackerEnvelope envelope)
    {
        var tracker = envelope.TryGetTrackerState();
        if (tracker is null) return;
        lock (_pendingGate) _pending = tracker;
    }

    private void DrainPending()
    {
        TrackerStateDto? state;
        lock (_pendingGate)
        {
            state = _pending;
            _pending = null;
        }
        if (state is null) return;
        _latest = state;
        _secretRail.ViewModel.Apply(state);
        _playerRail.ViewModel.Apply(state);
        _opponentRail.ViewModel.Apply(state);
    }

    private void UpdatePlacementAndVisibility()
    {
        // Rails belong to the Hearthstone window, not the dashboard's visual state.
        // Keep them alive when the match-history window is minimized.
        var shouldShow = Enabled && _latest is { Active: true, Complete: false };
        if (!shouldShow || !_gameWindowLocator.TryGetHearthstoneBounds(out var game))
        {
            Hide();
            return;
        }
        var centerX = game.Left + game.Width / 2;
        var centerY = game.Top + game.Height / 2;
        var screen = _owner.Screens.All.FirstOrDefault(s =>
        {
            var bounds = s.Bounds;
            return centerX >= bounds.X && centerX < bounds.Right &&
                   centerY >= bounds.Y && centerY < bounds.Bottom;
        }) ?? _owner.Screens.Primary;
        if (screen is null)
        {
            Hide();
            return;
        }
        var layout = HearthstoneOverlayLayoutCalculator.Calculate(
            game, screen.Scaling <= 0 ? 1.0 : screen.Scaling, screen.WorkingArea);
        _playerRail.Width = _opponentRail.Width = layout.RailWidthDip;
        _playerRail.Height = _opponentRail.Height = layout.RailHeightDip;
        _opponentRail.Position = layout.OpponentRailPosition;
        _playerRail.Position = layout.PlayerRailPosition;
        _playerRail.Topmost = _opponentRail.Topmost = true;
        var secretWidth = layout.RailWidthDip;
        _secretRail.Width = secretWidth;
        _secretRail.Height = Math.Min(layout.RailHeightDip, Math.Max(100, 55 + _secretRail.ViewModel.PlayerSecrets.Count * 54 + _latest!.SecretReads.Sum(s => 60 + (Math.Max(1,s.CandidateNames.Count) + s.EliminatedNames.Count) * 24)));
        var secretX = layout.OpponentRailPosition.X + (int)Math.Round((secretWidth + 8) * screen.Scaling);
        _secretRail.Position = new PixelPoint(secretX, layout.OpponentRailPosition.Y);
        if (_secretRail.ViewModel.HasSecrets) { if (!_secretRail.IsVisible) _secretRail.Show(); }
        else if (_secretRail.IsVisible) _secretRail.Hide();
        Show();
    }

    private void Show()
    {
        // Native owned windows are hidden automatically when their owner is
        // minimized, regardless of IsVisible. Rails must stay over Hearthstone.
        // DisposeAsync closes these independent tool windows with the dashboard.
        if (!_playerShown) { _playerRail.Show(); _playerShown = true; }
        else if (!_playerRail.IsVisible) _playerRail.Show();
        if (!_opponentShown) { _opponentRail.Show(); _opponentShown = true; }
        else if (!_opponentRail.IsVisible) _opponentRail.Show();
    }

    private void Hide()
    {
        if (_secretRail.IsVisible) _secretRail.Hide();
        if (_playerRail.IsVisible) _playerRail.Hide();
        if (_opponentRail.IsVisible) _opponentRail.Hide();
    }

    public async ValueTask DisposeAsync()
    {
        _placementTimer.Stop();
        Hide();
        try { _secretRail.Close(); } catch { }
        try { _playerRail.Close(); } catch { }
        try { _opponentRail.Close(); } catch { }
        if (_backend is not null) await _backend.DisposeAsync();
    }
}
