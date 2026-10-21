using System.Diagnostics;
using System.Text.Json;
using GhostData.App.Models;

namespace GhostData.App.Services;

public sealed class DashboardDataService
{
    private readonly StartupOptions _options;
    private readonly JsonSerializerOptions _json = new(){PropertyNameCaseInsensitive=true};
    private DashboardSnapshotDto? _cached;
    private (DateTime Written, long Length, DateTime Day) _cacheKey;
    public DashboardDataService(StartupOptions options)=>_options=options;

    public async Task<DashboardSnapshotDto> LoadAsync(CancellationToken cancellationToken=default)
    {
        var dataRoot=Environment.GetEnvironmentVariable("GHOSTDATA_DATA_DIR");
        if(string.IsNullOrWhiteSpace(dataRoot))dataRoot=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),"GhostDataData");
        var history=new FileInfo(Path.Combine(dataRoot,"matches.json"));
        var key=(history.LastWriteTimeUtc, history.Exists?history.Length:0, DateTime.Today);
        if(_cached is not null && key==_cacheKey)return _cached;
        var result=await RunPythonAsync(new[]{"--dashboard-json"},cancellationToken,throwOnError:true);
        _cached=JsonSerializer.Deserialize<DashboardSnapshotDto>(result.Output.Trim(),_json) ?? throw new InvalidOperationException("GhostData returned an empty dashboard snapshot.");
        _cacheKey=key;
        return _cached;
    }

    public async Task ClearHistoryAsync(CancellationToken cancellationToken=default)
    {
        await RunPythonAsync(new[]{"--clear-history"},cancellationToken,throwOnError:true);
        _cached=null;
    }

    internal async Task<ProcessResult> RunPythonAsync(IEnumerable<string> arguments,CancellationToken cancellationToken,bool throwOnError)
    {
        var script=Path.Combine(_options.ProjectRoot,"ghostdata.py");
        if(!File.Exists(script)) throw new FileNotFoundException("GhostData recorder entry point not found.",script);
        var start=new ProcessStartInfo{FileName=_options.PythonExecutable,WorkingDirectory=_options.ProjectRoot,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false,CreateNoWindow=true};
        start.ArgumentList.Add(script); foreach(var argument in arguments)start.ArgumentList.Add(argument);
        using var process=new Process{StartInfo=start}; if(!process.Start())throw new InvalidOperationException("Could not start GhostData recorder.");
        using var registration=cancellationToken.Register(()=>{try{if(!process.HasExited)process.Kill(entireProcessTree:true);}catch(InvalidOperationException){};});
        var outputTask=process.StandardOutput.ReadToEndAsync(cancellationToken); var errorTask=process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken); var result=new ProcessResult(process.ExitCode,await outputTask,await errorTask);
        if(throwOnError && result.ExitCode!=0)throw new InvalidOperationException(string.IsNullOrWhiteSpace(result.Error)?"GhostData data process failed.":result.Error.Trim());
        return result;
    }
    internal sealed record ProcessResult(int ExitCode,string Output,string Error);
}
