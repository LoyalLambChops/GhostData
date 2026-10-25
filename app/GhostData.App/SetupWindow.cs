using System.Text.Json;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Platform.Storage;
using GhostData.App.Services;

namespace GhostData.App;

public sealed class SetupWindow : Window
{
    private readonly DashboardDataService _service;
    private readonly CancellationTokenSource _lifetime = new();
    private readonly TextBox _folder = new(){PlaceholderText="Automatic discovery, or select your Hearthstone folder"};
    private readonly SelectableTextBlock _status = new(){Text="Checking local setup…",TextWrapping=TextWrapping.Wrap,FontSize=14};
    private readonly TextBlock _result = new(){TextWrapping=TextWrapping.Wrap,FontSize=13};
    private readonly StackPanel _actions = new(){Orientation=Orientation.Horizontal,Spacing=8};
    private readonly Button _done = new(){Content="SAVE AND CLOSE"};
    public string Summary { get; private set; } = "Open SETUP to check tracking readiness.";
    public SetupWindow(DashboardDataService service, JsonElement? preview=null)
    {
        _service=service; Title="GhostData — Local setup"; Width=820; Height=730;
        MinWidth=740; MinHeight=540; WindowStartupLocation=WindowStartupLocation.CenterOwner;
        Background=(IBrush?)Application.Current?.FindResource("GdWindow");
        var browse=new Button{Content="BROWSE"};
        browse.Click+=async (_,_)=>
        {
            try
            {
                var folders=await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions{Title="Select the folder containing Hearthstone.exe",AllowMultiple=false});
                if(folders.Count>0 && folders[0].TryGetLocalPath() is {} path)_folder.Text=path;
            }
            catch(Exception ex){_result.Text="Folder picker unavailable: "+ex.Message+" You can paste a folder path instead.";}
        };
        var pathRow=new Grid{ColumnDefinitions=new ColumnDefinitions("*,Auto"),ColumnSpacing=8};
        pathRow.Children.Add(_folder);Grid.SetColumn(browse,1);pathRow.Children.Add(browse);
        var save=new Button{Content="SAVE FOLDER"}; save.Click+=async (_,_)=>await PerformAsync(async ()=>
        {
            await SaveAsync(false); await CheckAsync(false);
            _result.Text="Folder saved. Restart GhostData after closing Setup to apply it to tracking. Your history is unchanged.";
        });
        var logging=new Button{Content="ENABLE POWER LOGGING"}; logging.Click+=async (_,_)=>await PerformAsync(async ()=>
        {
            using var json=await RunAsync(new[]{"--enable-power-logging"});
            var message=json.RootElement.GetProperty("message").GetString(); await CheckAsync(false); _result.Text=message;
        });
        var refresh=new Button{Content="REFRESH LOCAL CARDS"}; refresh.Click+=async (_,_)=>await PerformAsync(async ()=>
        {
            _result.Text="Reading public definitions from the running Blizzard client. This may take a minute…";
            using var json=await RunAsync(new[]{"--update-card-data"}); await CheckAsync(false);
            _result.Text="Local card definitions refreshed. No card data was downloaded.";
        });
        var check=new Button{Content="CHECK AGAIN"}; check.Click+=async (_,_)=>await PerformAsync(()=>CheckAsync(false));
        foreach(var button in new[]{save,logging,refresh,check})_actions.Children.Add(button);
        _done.Click+=async (_,_)=>await PerformAsync(async ()=>{await SaveAsync(true);Close();});
        var later=new Button{Content="CLOSE"};later.Click+=(_,_)=>Close();
        var bottom=new StackPanel{Spacing=12,Margin=new Thickness(0,12,0,0)};
        bottom.Children.Add(_result);
        bottom.Children.Add(new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Spacing=8,Children={later,_done}});
        var head=new StackPanel{Spacing=10,Margin=new Thickness(0,0,0,14),Children={
            new TextBlock{Text="Your games. Your data. Let's get ready.",FontSize=23,FontWeight=FontWeight.SemiBold},
            new TextBlock{Text="Start Hearthstone and reach the main menu. Select its installation folder below if automatic discovery misses it.",TextWrapping=TextWrapping.Wrap},
            pathRow,
            new TextBlock{Text="ENABLE POWER LOGGING changes only Power LogLevel / FilePrinting in your Blizzard log.config, preserving other settings and backing up an existing file. Restart Hearthstone afterward. Nothing changes until you click it.",TextWrapping=TextWrapping.Wrap,FontSize=12},
            _actions}};
        var panel=new DockPanel{Margin=new Thickness(22)};
        DockPanel.SetDock(head,Dock.Top);panel.Children.Add(head);
        DockPanel.SetDock(bottom,Dock.Bottom);panel.Children.Add(bottom);
        panel.Children.Add(new ScrollViewer{Content=_status});Content=panel;
        if(preview is {} sample)
        {
            Title="GhostData — Setup preview (sample data)";
            _actions.IsEnabled=false;_folder.IsEnabled=false;browse.IsEnabled=false;_done.IsVisible=false;
            ApplyStatus(sample,true);
            _result.Text="Synthetic setup preview. All configuration-changing controls are disabled.";
        }
        else Opened+=async (_,_)=>await PerformAsync(()=>CheckAsync(true));
        Closed+=(_,_)=>_lifetime.Cancel();
    }
    private async Task PerformAsync(Func<Task> operation)
    {
        _actions.IsEnabled=false;_folder.IsEnabled=false;_done.IsEnabled=false;
        try{await operation();}
        catch(OperationCanceledException){if(!_lifetime.IsCancellationRequested)_result.Text="The check timed out. Reach Hearthstone's main menu and try again.";}
        catch(Exception ex){_result.Text="Setup needs attention: "+ex.Message;Summary="Setup needs attention — open SETUP for details.";}
        finally{_actions.IsEnabled=true;_folder.IsEnabled=true;_done.IsEnabled=true;}
    }
    private async Task<JsonDocument> RunAsync(string[] arguments)
    {
        using var timeout=CancellationTokenSource.CreateLinkedTokenSource(_lifetime.Token);timeout.CancelAfter(TimeSpan.FromSeconds(75));
        var result=await _service.RunPythonAsync(arguments,timeout.Token,true);
        return JsonDocument.Parse(result.Output);
    }
    private async Task SaveAsync(bool acknowledge)
    {
        var args=new List<string>{"--save-game-directory",_folder.Text?.Trim()??""};
        if(acknowledge)args.Add("--acknowledge-setup");
        using var json=await RunAsync(args.ToArray());
    }
    private async Task CheckAsync(bool populate)
    {
        using var json=await RunAsync(new[]{"--setup-status"});ApplyStatus(json.RootElement,populate);
        _result.Text="Checks stay local. SAVE AND CLOSE remembers setup; it does not assert that every check passed. Folder changes take effect after restarting GhostData.";
    }
    private void ApplyStatus(JsonElement root,bool populate)
    {
        if(populate)_folder.Text=root.GetProperty("game_directory").GetString();
        _status.Text=string.Join("\n\n",root.GetProperty("checks").EnumerateArray().Select(row=>$"{row.GetProperty("name").GetString()} — {row.GetProperty("status").GetString()}\n{row.GetProperty("detail").GetString()}"));
        Summary=ReadinessSummary(root);

    }
    public static string ReadinessSummary(JsonElement root)=>root.GetProperty("ready").GetBoolean()
        ? "Local setup checks passed. Live card accounting is verified during play."
        : "Tracking setup is waiting or needs attention — open SETUP for details.";
    public static bool HasSeenSetup()
    {
        var folder=Environment.GetEnvironmentVariable("GHOSTDATA_DATA_DIR");
        if(string.IsNullOrWhiteSpace(folder))folder=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),"GhostDataData");
        try{using var doc=JsonDocument.Parse(File.ReadAllText(Path.Combine(folder,"settings.json")));return doc.RootElement.GetProperty("schema_version").GetInt32()==1 && doc.RootElement.GetProperty("setup_seen").GetBoolean();}
        catch{return false;}
    }
}
