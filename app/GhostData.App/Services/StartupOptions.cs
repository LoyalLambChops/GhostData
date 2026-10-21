namespace GhostData.App.Services;

public sealed class StartupOptions
{
    public string? PreviewDirectory { get; init; }
    public bool ExitAfterPreview { get; init; }
    public string? UpdateAcknowledgement { get; init; }
    public string ProjectRoot { get; init; } = AppContext.BaseDirectory;
    public string PythonExecutable { get; init; } = Environment.GetEnvironmentVariable("GHOSTDATA_PYTHON") ?? "python";
    public static StartupOptions Parse(string[] args)
    {
        string? preview = null;
        var exitAfterPreview = false;
        string? updateAcknowledgement = null;
        var root = FindProjectRoot(AppContext.BaseDirectory);
        string? python = Environment.GetEnvironmentVariable("GHOSTDATA_PYTHON");
        for (var i=0;i<args.Length;i++)
        {
            if (args[i]=="--preview" && i+1<args.Length) preview=Path.GetFullPath(args[++i]);
            else if(args[i]=="--preview-exit") exitAfterPreview=true;
            else if (args[i]=="--root" && i+1<args.Length) root=Path.GetFullPath(args[++i]);
            else if(args[i]=="--python" && i+1<args.Length) python=args[++i];
            else if(args[i]=="--update-ack" && i+1<args.Length) updateAcknowledgement=Path.GetFullPath(args[++i]);
        }
        python ??= File.Exists(Path.Combine(root,"python","python.exe"))?Path.Combine(root,"python","python.exe"):"python";
        return new StartupOptions{ProjectRoot=root,PythonExecutable=python,PreviewDirectory=preview,ExitAfterPreview=exitAfterPreview,UpdateAcknowledgement=updateAcknowledgement};
    }
    private static string FindProjectRoot(string start)
    {
        var dir=new DirectoryInfo(start);
        while(dir is not null)
        {
            if(File.Exists(Path.Combine(dir.FullName,"ghostdata.py"))) return dir.FullName;
            dir=dir.Parent;
        }
        return Path.GetFullPath(Path.Combine(start,"..","..","..",".."));
    }
}
