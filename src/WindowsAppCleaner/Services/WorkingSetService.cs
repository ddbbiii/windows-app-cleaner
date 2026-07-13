using System.Runtime.InteropServices;

namespace WindowsAppCleaner.Services;

internal static class WorkingSetService
{
    [DllImport("kernel32.dll")] private static extern nint GetCurrentProcess();
    [DllImport("kernel32.dll")][return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetProcessWorkingSetSize(nint process, nint minimum, nint maximum);

    internal static void Trim() => SetProcessWorkingSetSize(GetCurrentProcess(), new nint(-1), new nint(-1));
}
