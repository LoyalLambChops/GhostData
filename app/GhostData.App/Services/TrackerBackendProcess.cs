using System.Diagnostics;
using System.Text.Json;
using GhostData.App.Models;

namespace GhostData.App.Services;

public sealed class TrackerBackendProcess : IAsyncDisposable
{
    private readonly StartupOptions _options;
    private readonly CancellationTokenSource _lifetime = new();
    private Process? _process;

    public event Action<TrackerEnvelope>? EnvelopeReceived;
    public event Action<string>? DiagnosticReceived;
    public event Action<string>? Failed;

    public TrackerBackendProcess(StartupOptions options) => _options = options;

    public Task StartAsync()
    {
        var script = Path.Combine(_options.ProjectRoot, "ghostdata.py");
        if (!File.Exists(script))
            throw new FileNotFoundException("GhostData tracker backend was not found.", script);
        var start = new ProcessStartInfo
        {
            FileName = _options.PythonExecutable,
            WorkingDirectory = _options.ProjectRoot,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add(script);
        start.ArgumentList.Add("--tracker-stream");
        start.ArgumentList.Add("--interval");
        start.ArgumentList.Add("0.25");

        _process = new Process { StartInfo = start, EnableRaisingEvents = true };
        _process.Exited += (_, _) =>
        {
            if (!_lifetime.IsCancellationRequested)
                Failed?.Invoke($"Deck tracker exited with code {_process?.ExitCode ?? -1}.");
        };
        if (!_process.Start())
            throw new InvalidOperationException("Could not start the GhostData deck tracker.");

        _ = Task.Run(ReadOutputAsync);
        _ = Task.Run(ReadErrorsAsync);
        return Task.CompletedTask;
    }

    private async Task ReadOutputAsync()
    {
        while (!_lifetime.IsCancellationRequested && _process is not null)
        {
            var line = await _process.StandardOutput.ReadLineAsync(_lifetime.Token);
            if (line is null) break;
            try
            {
                var envelope = JsonSerializer.Deserialize<TrackerEnvelope>(line, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true,
                });
                if (envelope is not null) EnvelopeReceived?.Invoke(envelope);
            }
            catch (JsonException)
            {
                DiagnosticReceived?.Invoke("Unparseable tracker output: " + line);
            }
        }
    }

    private async Task ReadErrorsAsync()
    {
        while (!_lifetime.IsCancellationRequested && _process is not null)
        {
            var line = await _process.StandardError.ReadLineAsync(_lifetime.Token);
            if (line is null) break;
            DiagnosticReceived?.Invoke(line);
        }
    }

    public async ValueTask DisposeAsync()
    {
        _lifetime.Cancel();
        if (_process is { HasExited: false })
        {
            try { _process.Kill(entireProcessTree: true); } catch { }
            try { await _process.WaitForExitAsync(); } catch { }
        }
        _process?.Dispose();
        _lifetime.Dispose();
    }
}
