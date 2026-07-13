namespace WindowsAppCleaner.Services;

public sealed class SingleInstanceService : IDisposable
{
    private const string MutexName = @"Local\WindowsAppCleaner.SingleInstance";
    private const string EventName = @"Local\WindowsAppCleaner.Activate";
    private Mutex? _mutex;
    private EventWaitHandle? _activationEvent;
    private RegisteredWaitHandle? _wait;

    public bool TryAcquire(Action onActivated)
    {
        _mutex = new Mutex(true, MutexName, out var created);
        if (!created)
        {
            try { EventWaitHandle.OpenExisting(EventName).Set(); } catch { }
            return false;
        }
        _activationEvent = new EventWaitHandle(false, EventResetMode.AutoReset, EventName);
        _wait = ThreadPool.RegisterWaitForSingleObject(_activationEvent, (_, _) => onActivated(), null, Timeout.Infinite, false);
        return true;
    }

    public void Dispose()
    {
        _wait?.Unregister(null);
        _activationEvent?.Dispose();
        _mutex?.ReleaseMutex();
        _mutex?.Dispose();
    }
}
