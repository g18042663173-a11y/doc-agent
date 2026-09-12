namespace DocumentWorkbench;

public static class AppInfo
{
    public static string Version { get; } = ResolveVersion();

    public static string ProductVersionLabel => $"文档生成工作台 {Version}";

    public static string PlatformVersionLabel => $"{Version} · Windows x64";

    private static string ResolveVersion()
    {
        var version = typeof(AppInfo).Assembly.GetName().Version;
        return version is null
            ? "unknown"
            : $"{version.Major}.{version.Minor}.{Math.Max(version.Build, 0)}";
    }
}
