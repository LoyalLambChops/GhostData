using System.Diagnostics;
using System.Text.Json;
using Avalonia.Threading;
namespace GhostData.App.Services;

public sealed class HandHoverSensor : IDisposable
{
    private readonly string _root;
    private Process? _process;
    private readonly CancellationTokenSource _lifetime=new();
    public HandHoverSensor(string root)=>_root=root;
    public void Start()
    {
        var paths=new[]{Path.Combine(_root,"sensor","bin","GhostData.Sensor.exe"),
            Path.Combine(_root,"sensor","GhostData.Sensor","bin","Release","net48","GhostData.Sensor.exe")};
        var exe=paths.FirstOrDefault(File.Exists);
        if(exe is null)return;
        var info=new ProcessStartInfo(exe){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
        info.ArgumentList.Add("hand-stream");
        info.ArgumentList.Add("--parent-pid");info.ArgumentList.Add(Environment.ProcessId.ToString());
        _process=Process.Start(info);
        if(_process is null)return;
        _=ReadAsync();
    }
    private async Task ReadAsync()
    {
        try
        {
            while(!_lifetime.IsCancellationRequested)
            {
                var line=await _process!.StandardOutput.ReadLineAsync(_lifetime.Token);
                if(line is null)break;
                if(line.Length>300000)continue;
                using var doc=JsonDocument.Parse(line);var sample=doc.RootElement.Clone();
                Dispatcher.UIThread.Post(()=>{if(!_lifetime.IsCancellationRequested)RailHoverPreview.ApplyHandSensor(sample);});
            }
        }
        catch(Exception){} // enrichments cannot interrupt tracking
        finally{Dispatcher.UIThread.Post(()=>RailHoverPreview.ClearHandSensor());}
    }
    public void Dispose()
    {
        _lifetime.Cancel();
        try{if(_process is {HasExited:false})_process.Kill(entireProcessTree:true);}catch{}
        _process?.Dispose();RailHoverPreview.ClearHandSensor();
    }
}
