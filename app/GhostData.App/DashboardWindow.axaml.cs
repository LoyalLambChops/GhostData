using Avalonia;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;
using Avalonia.Layout;
using Avalonia.Threading;
using Avalonia.VisualTree;
using Avalonia.Input;
using GhostData.App.Services;
using GhostData.App.ViewModels;

namespace GhostData.App;

public sealed partial class DashboardWindow : Window
{
    private readonly string? _previewDirectory;
    private readonly bool _exitAfterPreview;
    private readonly List<Window> _previewWindows = new();
    private readonly DashboardViewModel _viewModel=new();
    private readonly DashboardDataService _dataService;
    private readonly BackgroundRecorderProcess _recorder;
    private readonly DeckRailCoordinator _deckRails;
    private readonly CancellationTokenSource _lifetime=new();
    private readonly DispatcherTimer _historyRefreshTimer;
    private GhostData.App.Models.DashboardSnapshotDto? _lastSnapshot;
    private readonly ReleaseUpdateService _updates;
    private readonly string? _updateAcknowledgement;
    private bool _closing, _closedCleanly;
    private string _loggingRestartNotice="";
    private int _loggingGamePid;
    private DateTime _lastSetupCheck=DateTime.UtcNow;
    public DashboardWindow():this(StartupOptions.Parse(Array.Empty<string>())){}
    public DashboardWindow(StartupOptions options)
    {
        _previewDirectory=options.PreviewDirectory;
        _updates=new ReleaseUpdateService(options);
        _updateAcknowledgement=options.UpdateAcknowledgement;
        _exitAfterPreview=options.ExitAfterPreview;
        if(_previewDirectory is not null)ShowActivated=false;
        AvaloniaXamlLoader.Load(this);DataContext=_viewModel;_dataService=new DashboardDataService(options);_recorder=new BackgroundRecorderProcess(options);_deckRails=new DeckRailCoordinator(this,options);
        Title=$"GhostData — {ProductInfo.ReleaseName}";
        this.FindControl<TextBlock>("ReleaseLabel")!.Text=$"PHANTOM · BETA 1  /  Build {ProductInfo.Version}";
        _deckRails.Failed+=message=>this.FindControl<TextBlock>("SetupStatus")!.Text=message+" Open SETUP or restart GhostData.";
        _historyRefreshTimer=new DispatcherTimer{Interval=TimeSpan.FromSeconds(4)};
        _historyRefreshTimer.Tick+=async (_,_)=>{await RefreshAsync(silent:true);if(DateTime.UtcNow-_lastSetupCheck>TimeSpan.FromSeconds(30)){_lastSetupCheck=DateTime.UtcNow;await CheckSetupAsync(prepare:true);}};
        Opened+=OnOpened;Closing+=OnClosing;
    }
    private async void OnOpened(object? sender,EventArgs e)
    {
        if(_updateAcknowledgement is not null)File.WriteAllText(_updateAcknowledgement,"ready");
        if(_previewDirectory is not null)
        {
            var snapshot=System.Text.Json.JsonSerializer.Deserialize<GhostData.App.Models.DashboardSnapshotDto>(File.ReadAllText(Path.Combine(_previewDirectory,"dashboard.json")))!;
            _viewModel.Apply(snapshot);
            var state=System.Text.Json.JsonSerializer.Deserialize<GhostData.App.Models.TrackerStateDto>(File.ReadAllText(Path.Combine(_previewDirectory,"tracker.json")))!;
            var player=new PlayerDeckWindow(); player.ViewModel.Apply(state); player.Position=new Avalonia.PixelPoint(1650,100);
            var opponent=new OpponentDeckWindow(); opponent.ViewModel.Apply(state); opponent.Position=new Avalonia.PixelPoint(30,100);
            var secrets=new SecretTrackerWindow(); secrets.ViewModel.Apply(state); secrets.Position=new Avalonia.PixelPoint(255,100);
            var counters=new EffectCounterWindow(); counters.Apply(state); counters.Width=220;
            var split=HearthstoneOverlayLayoutCalculator.SplitPlayerHeight(player.Height,state.PlayerCounters.Count);
            player.Height=split.PlayerHeight; counters.Height=Math.Max(1,split.CounterHeight);
            counters.Position=new Avalonia.PixelPoint(1650,100+(int)player.Height+6);
            foreach(var window in (state.PlayerCounters.Count>0 ? new Window[]{player,opponent,secrets,counters} : new Window[]{player,opponent,secrets})) { _previewWindows.Add(window); window.Show(); }
            Title=$"GhostData — {ProductInfo.ReleaseName} — Preview (sample data)";
            await Task.Delay(500);
            foreach(var pair in _previewWindows.Select((window,index)=>(window,index))) SavePreview(pair.window, $"rail-{pair.index}.png");
            SavePreview(this, "dashboard-summary.png");
            var tabs=this.FindControl<TabControl>("StatisticsTabs")!;
            for(var index=1;index<3;index++) { tabs.SelectedIndex=index; await Task.Delay(150); SavePreview(this, $"dashboard-{index}.png"); }
            tabs.SelectedIndex=0;
            await SavePreviewChecks(player,state);
            if(File.Exists(Path.Combine(_previewDirectory,"setup.json")))
            {
                using var setupJson=System.Text.Json.JsonDocument.Parse(File.ReadAllText(Path.Combine(_previewDirectory,"setup.json")));
                var setup=new SetupWindow(_dataService,setupJson.RootElement.Clone());setup.Show();
                await Task.Delay(150);SavePreview(setup,"setup.png");setup.Close();
            }
            if(_exitAfterPreview)Close();
            return;
        }
        this.FindControl<TextBlock>("SetupStatus")!.Text="Preparing local tracking automatically…";
        await CheckSetupAsync(prepare:true);
        if(_closing)return;
        string? trackerError=null;
        try{_recorder.Start();}
        catch(Exception ex){trackerError="Recorder unavailable: "+ex.Message+". Open SETUP or repair GhostData.";}
        try
        {
            await _deckRails.StartAsync();
        }
        catch(Exception ex)
        {
            // A live-tracker startup problem must never take down the dashboard.
            // Match history remains useful while the actionable error is shown.
            trackerError="Deck rails unavailable: "+ex.Message;
        }
        await RefreshAsync();
        _historyRefreshTimer.Start();
        if(trackerError is not null)_viewModel.Status=trackerError;
        else if(_updateAcknowledgement is null)await CheckSetupAsync();
    }
    private void SavePreview(Window window, string filename)
    {
        using var bitmap=new Avalonia.Media.Imaging.RenderTargetBitmap(new Avalonia.PixelSize((int)window.Width,(int)window.Height),new Avalonia.Vector(96,96));
        bitmap.Render(window); bitmap.Save(Path.Combine(_previewDirectory!,filename),new Avalonia.Media.Imaging.PngBitmapEncoderOptions());
    }
    private async Task SavePreviewChecks(PlayerDeckWindow player, GhostData.App.Models.TrackerStateDto state)
    {
        // A dense deck must overflow vertically without shrinking any text.
        var original=state.PlayerDisplayRows;
        state.PlayerDisplayRows=Enumerable.Range(0,30).Select(i=>original[i%original.Count]).ToList();
        player.ViewModel.Apply(state);
        await Task.Delay(150);
        SavePreview(player,"rail-full-deck.png");
        var scroll=player.GetVisualDescendants().OfType<ScrollViewer>().First();
        var names=player.GetVisualDescendants().OfType<TextBlock>().Where(t=>t.DataContext is DisplayCardViewModel card && t.Text==card.Name).ToList();
        var first=names.First(n=>n.DataContext is DisplayCardViewModel card && card.CardId==original[0].CardId);
        var point=first.TranslatePoint(new Avalonia.Point(2,2),player)!.Value;
        var hit=player.InputHitTest(point) as Avalonia.Visual;
        var hoverIdentity=hit?.GetSelfAndVisualAncestors().OfType<Control>().Select(c=>RailHoverPreview.CardFor(c.DataContext).Id).FirstOrDefault(id=>id.Length>0);
        var overflow=scroll.Extent.Height>scroll.Viewport.Height;
        scroll.Offset=new Avalonia.Vector(0,scroll.Extent.Height);
        await Task.Delay(100);
        SavePreview(player,"rail-full-deck-bottom.png");
        File.WriteAllText(Path.Combine(_previewDirectory!,"validation.json"),System.Text.Json.JsonSerializer.Serialize(new {
            rows=names.Count, readableNames=names.All(n=>n.FontSize>=15), scrolls=overflow,
            hoverHitTest=hoverIdentity==original[0].CardId,
            footerFontSize=player.GetVisualDescendants().OfType<TextBlock>().Single(t=>t.Text==player.ViewModel.CountLine).FontSize,
            textOnly=!player.GetVisualDescendants().OfType<Image>().Any()
        }));
        state.PlayerDisplayRows=original;player.ViewModel.Apply(state);scroll.Offset=default;
        var originalWidth=player.Width;
        player.Width=HearthstoneOverlayLayoutCalculator.RailMinWidthDip;
        await Task.Delay(100);
        SavePreview(player,"rail-minimum-width.png");
        player.Width=originalWidth;
    }
    private async void OnClosing(object? sender,WindowClosingEventArgs e)
    {
        if(_closedCleanly)return;
        e.Cancel=true;
        if(_closing)return;
        _closing=true;
        foreach(var w in _previewWindows)w.Close();
        _historyRefreshTimer.Stop();_lifetime.Cancel();_recorder.Dispose();
        await _deckRails.DisposeAsync();
        try{_updates.InstallOnExit();}
        catch(Exception ex)
        {
            _viewModel.Status="Update installation could not start: "+ex.Message;
            _closing=false;_closedCleanly=true;return;
        }
        _lifetime.Dispose();_closedCleanly=true;Close();
    }
    private bool _setupOpen;
    private async void OnSetupClicked(object? sender,RoutedEventArgs e)
    {
        await ShowSetupAsync();
    }
    private async Task ShowSetupAsync()
    {
        if(_setupOpen)return;_setupOpen=true;
        try
        {
            System.Text.Json.JsonElement? preview=null;
            if(_previewDirectory is not null)
            {
                using var json=System.Text.Json.JsonDocument.Parse(File.ReadAllText(Path.Combine(_previewDirectory,"setup.json")));
                preview=json.RootElement.Clone();
            }
            var setup=new SetupWindow(_dataService,preview);await setup.ShowDialog(this);
            this.FindControl<TextBlock>("SetupStatus")!.Text=setup.Summary;
        }
        finally{_setupOpen=false;}
    }
    private async Task CheckSetupAsync(bool prepare=false)
    {
        using var timeout=CancellationTokenSource.CreateLinkedTokenSource(_lifetime.Token);timeout.CancelAfter(TimeSpan.FromSeconds(12));
        try
        {
            var response=await _dataService.RunPythonAsync(new[]{prepare ? "--prepare-local-setup" : "--setup-status"},timeout.Token,true);
            using var doc=System.Text.Json.JsonDocument.Parse(response.Output);
            var pid=doc.RootElement.TryGetProperty("hearthstone_pid",out var processId)?processId.GetInt32():0;
            if(pid!=_loggingGamePid)_loggingRestartNotice="";
            if(doc.RootElement.TryGetProperty("logging_changed",out var changed) && changed.GetBoolean() && pid>0)
            {
                _loggingGamePid=pid;
                _loggingRestartNotice="Logging enabled automatically — restart Hearthstone once to activate it. ";
            }
            this.FindControl<TextBlock>("SetupStatus")!.Text=_loggingRestartNotice+SetupWindow.ReadinessSummary(doc.RootElement);
        }
        catch(OperationCanceledException){if(!_closing)this.FindControl<TextBlock>("SetupStatus")!.Text="Setup check timed out — open SETUP to retry.";}
        catch(Exception ex){this.FindControl<TextBlock>("SetupStatus")!.Text="Setup unavailable: "+ex.Message;}
    }
    private async void OnTwitchClicked(object? sender,RoutedEventArgs e) => await OpenContactAsync(ProductInfo.Twitch);
    private async void OnDiscordClicked(object? sender,RoutedEventArgs e) => await OpenContactAsync(ProductInfo.Discord);
    private async void OnContactClicked(object? sender,RoutedEventArgs e) => await OpenContactAsync(ProductInfo.BugReportUri);
    private async Task OpenContactAsync(string uri)
    {
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(uri){UseShellExecute=true}); }
        catch
        {
            await ShowInformationAsync("Contact GhostData", "Windows could not open the link. Configure a default browser or email app, or copy the address below.\n\n"
                + (uri.StartsWith("mailto:",StringComparison.Ordinal) ? ProductInfo.Email : uri)
                + "\n\nGhostData sends no email or diagnostic data automatically.");
        }
    }
    private async void OnLicenseClicked(object? sender,RoutedEventArgs e)
    {
        using var stream=typeof(ProductInfo).Assembly.GetManifestResourceStream("GhostData.LICENSE")!;
        using var reader=new StreamReader(stream);
        await ShowInformationAsync("GhostData — MIT license",await reader.ReadToEndAsync()
            + "\nBundled third-party components retain their own licenses. See THIRD_PARTY_NOTICES.md and licenses/ in the application folder. This license does not grant rights to Blizzard game content.");
    }
    private async Task ShowInformationAsync(string title,string text)
    {
        var dialog=new Window{Title=title,Width=660,Height=540,MinWidth=440,MinHeight=300,WindowStartupLocation=WindowStartupLocation.CenterOwner};
        var close=new Button{Content="CLOSE",HorizontalAlignment=HorizontalAlignment.Right,Margin=new Thickness(0,12,0,0)};
        close.Click+=(_,_)=>dialog.Close();
        var panel=new DockPanel{Margin=new Thickness(24)};
        DockPanel.SetDock(close,Dock.Bottom); panel.Children.Add(close);
        panel.Children.Add(new ScrollViewer{Content=new SelectableTextBlock{Text=text,TextWrapping=Avalonia.Media.TextWrapping.Wrap,FontSize=14}});
        dialog.Content=panel;
        await dialog.ShowDialog(this);
    }
    private async void OnUpdateClicked(object? sender,RoutedEventArgs e)
    {
        if(_previewDirectory is not null || _viewModel.IsBusy)return;
        _viewModel.IsBusy=true;
        _viewModel.Status="Refreshing local game definitions and checking GhostData releases…";
        try{_viewModel.Status=await _updates.CheckAsync(_dataService,_lifetime.Token);}
        catch(OperationCanceledException){}
        catch(Exception ex){_viewModel.Status="Update could not complete: "+ex.Message;}
        finally{_viewModel.IsBusy=false;}
    }
    private async void OnRefreshClicked(object? sender,RoutedEventArgs e)=>await RefreshAsync();
    private async void OnClearHistoryClicked(object? sender,RoutedEventArgs e)
    {
        if(_previewDirectory is not null)return;
        if(!await ConfirmClearHistoryAsync())return;
        try
        {
            _viewModel.IsBusy=true;
            _viewModel.Status="Clearing local match history…";
            // Pause ingestion so the clear transaction cannot race the recorder.
            _recorder.Dispose();
            await _dataService.ClearHistoryAsync(_lifetime.Token);
        }
        catch(Exception ex){_viewModel.Status="Could not clear local history: "+ex.Message;return;}
        finally{_recorder.Start();_viewModel.IsBusy=false;}
        await RefreshAsync();
        _viewModel.Status="Match history cleared. Future completed matches will be recorded automatically.";
    }

    private async Task<bool> ConfirmClearHistoryAsync()
    {
        var dialog=new Window{Title="Clear Match History",Width=430,Height=210,CanResize=false,WindowStartupLocation=WindowStartupLocation.CenterOwner};
        var cancel=new Button{Content="CANCEL",MinWidth=95};
        var clear=new Button{Content="CLEAR HISTORY",MinWidth=125};
        cancel.Click+=(_,_)=>dialog.Close(false);
        clear.Click+=(_,_)=>dialog.Close(true);
        dialog.Content=new StackPanel
        {
            Margin=new Avalonia.Thickness(24),Spacing=16,
            Children=
            {
                new TextBlock{Text="Erase all recorded matches?",FontSize=20,FontWeight=Avalonia.Media.FontWeight.SemiBold},
                new TextBlock{Text="This removes GhostData's local match history and starts a new recording period. This cannot be undone.",TextWrapping=Avalonia.Media.TextWrapping.Wrap},
                new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Spacing=10,Children={cancel,clear}}
            }
        };
        return await dialog.ShowDialog<bool>(this);
    }
    private void OnDeckRailsChanged(object? sender,RoutedEventArgs e)
    {
        if(sender is CheckBox box)_deckRails.Enabled=box.IsChecked==true;
    }
    private void OnMatchSelectionChanged(object? sender,SelectionChangedEventArgs e){if(sender is ListBox list && list.SelectedItem is DashboardMatchItemViewModel item)_viewModel.SelectedMatch=item;}
    private async Task RefreshAsync(bool silent=false)
    {
        if(_previewDirectory is not null || _viewModel.IsBusy)return;
        try
        {
            _viewModel.IsBusy=true;
            if(!silent)_viewModel.Status="Loading local match history…";
            var snapshot=await _dataService.LoadAsync(_lifetime.Token);
            if(!silent || !ReferenceEquals(snapshot,_lastSnapshot))_viewModel.Apply(snapshot);
            _lastSnapshot=snapshot;
        }
        catch(OperationCanceledException){}
        catch(Exception ex){if(!silent)_viewModel.Status="Could not load local history: "+ex.Message;}
        finally{_viewModel.IsBusy=false;}
    }
}
