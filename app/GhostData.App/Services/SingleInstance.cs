using System.Threading;

namespace GhostData.App.Services;

/// <summary>One desktop instance per Windows session, with a foreground request.</summary>
public sealed class SingleInstance : IDisposable
{
    public const string MutexName = @"Local\GhostData.App";
    private const string ActivationName = @"Local\GhostData.Activate";
    private readonly Mutex _mutex;
    private readonly EventWaitHandle? _activation;
    private RegisteredWaitHandle? _wait;
    public bool IsPrimary { get; }

    public SingleInstance(string mutexName = MutexName, string activationName = ActivationName)
    {
        // createdNew avoids the recursive-ownership behavior of named mutexes.
        _mutex = new Mutex(false, mutexName, out var createdNew);
        IsPrimary = createdNew;
        if (IsPrimary) _activation = new EventWaitHandle(false, EventResetMode.AutoReset, activationName);
        else if (OperatingSystem.IsWindows())
        {
            try { using var signal = EventWaitHandle.OpenExisting(activationName); signal.Set(); }
            catch (WaitHandleCannotBeOpenedException) { /* Primary is still starting. */ }
        }
    }

    public void OnActivate(Action activate)
    {
        if (_activation is not null)
            _wait = ThreadPool.RegisterWaitForSingleObject(_activation, (_, _) => activate(), null, Timeout.Infinite, false);
    }

    public void Dispose()
    {
        _wait?.Unregister(null);
        _activation?.Dispose();
        _mutex.Dispose();
    }
}
