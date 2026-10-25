using System.Diagnostics;

namespace GhostData.App.Services;

public sealed class BackgroundRecorderProcess : IDisposable
{
    private readonly StartupOptions _options;
    private Process? _process;
    public BackgroundRecorderProcess(StartupOptions options)=>_options=options;
    public void Start()
    {
        if(_process is { HasExited:false }) return;
        var script=Path.Combine(_options.ProjectRoot,"ghostdata.py");
        if(!File.Exists(script))throw new FileNotFoundException("GhostData recorder is missing. Repair the app with Setup.",script);
        var start=new ProcessStartInfo{FileName=_options.PythonExecutable,WorkingDirectory=_options.ProjectRoot,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
        start.ArgumentList.Add(script);start.ArgumentList.Add("--record-continuously");
        _process=new Process{StartInfo=start};_process.Start();
        // Drain continuously so a full redirected pipe cannot stall recording.
        _process.OutputDataReceived+=(_,_)=>{};
        _process.ErrorDataReceived+=(_,_)=>{};
        _process.BeginOutputReadLine();_process.BeginErrorReadLine();
    }
    public void Dispose()
    {
        try{if(_process is {HasExited:false})_process.Kill(entireProcessTree:true);}catch{}
        _process?.Dispose();_process=null;
    }
}
