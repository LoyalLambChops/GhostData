using System.Diagnostics;
using System.Text.Json;

namespace GhostData.App.Services;

public sealed class ReleaseUpdateService(StartupOptions options)
{
    private string? _staged;
    public async Task<string> CheckAsync(DashboardDataService data, CancellationToken cancellationToken)
    {
        if(_staged is not null)return "A verified update is ready. Close GhostData to install it.";
        var result=await data.RunPythonAsync(new[]{"--update"},cancellationToken,true);
        using var document=JsonDocument.Parse(result.Output);
        var release=document.RootElement.GetProperty("release");
        if(release.GetProperty("status").GetString()=="STAGED")
            _staged=release.GetProperty("staged_path").GetString();
        return document.RootElement.GetProperty("cards").GetString()+" "+release.GetProperty("message").GetString();
    }

    public void InstallOnExit()
    {
        if(_staged is null)return;
        var root=Path.GetFullPath(options.ProjectRoot).TrimEnd(Path.DirectorySeparatorChar);
        var staged=Path.GetFullPath(_staged).TrimEnd(Path.DirectorySeparatorChar);
        if(!string.Equals(Path.GetDirectoryName(root),Path.GetDirectoryName(staged),StringComparison.OrdinalIgnoreCase)
            || !Path.GetFileName(staged).StartsWith(".ghostdata-update-",StringComparison.Ordinal)
            || Directory.Exists(Path.Combine(root,".git")))
            throw new InvalidOperationException("Invalid update staging location.");
        var folder=Path.Combine(Path.GetTempPath(),"ghostdata-install-"+Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        var helper=Path.Combine(folder,"Apply-Update.ps1");
        File.Copy(Path.Combine(root,"tools","Apply-Update.ps1"),helper);
        var plan=Path.Combine(folder,"plan.json");
        File.WriteAllText(plan,JsonSerializer.Serialize(new {root, staged, parent_pid=Environment.ProcessId}));
        var start=new ProcessStartInfo
        {
            FileName=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"WindowsPowerShell","v1.0","powershell.exe"),
            UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,WorkingDirectory=folder
        };
        foreach(var arg in new[]{"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",helper,"-PlanPath",plan})start.ArgumentList.Add(arg);
        using var process=Process.Start(start) ?? throw new InvalidOperationException("Could not start the update installer.");
    }
}
