using System.Diagnostics;
using FlaUI.Core;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Conditions;
using FlaUI.Core.Definitions;
using FlaUI.Core.Tools;
using FlaUI.UIA3;

namespace DocumentWorkbench.Tests;

public sealed class NativeUiSmokeTests
{
    [Fact]
    [Trait("Category", "NativeUI")]
    public void NativeWindowStartsAndCoreNavigationIsKeyboardReachable()
    {
        if (!System.OperatingSystem.IsWindows())
        {
            return;
        }

        var repoRoot = FindRepositoryRoot();
        var executable = Path.Combine(
            repoRoot,
            "desktop",
            "DocumentWorkbench",
            "bin",
            "Debug",
            "net8.0-windows10.0.19041.0",
            "win-x64",
            "DocumentWorkbench.exe");
        Assert.True(File.Exists(executable), $"Desktop executable is missing: {executable}");
        var start = new ProcessStartInfo(executable)
        {
            WorkingDirectory = Path.GetDirectoryName(executable)!,
            UseShellExecute = false,
        };
        start.Environment["DOCUMENT_WORKBENCH_REPO_ROOT"] = repoRoot;

        using var application = Application.Launch(start);
        using var automation = new UIA3Automation();
        var window = Retry.WhileNull(
            () => application.GetMainWindow(automation),
            TimeSpan.FromSeconds(40),
            TimeSpan.FromMilliseconds(250)).Result;
        Assert.NotNull(window);
        Assert.Equal("文档生成工作台", window.Title);
        var condition = new ConditionFactory(new UIA3PropertyLibrary());

        var generate = window.FindFirstDescendant(condition.ByAutomationId("generate"));
        var settings = window.FindFirstDescendant(condition.ByAutomationId("nav-settings"));
        var diagnostics = window.FindFirstDescendant(condition.ByAutomationId("nav-diagnostics"));

        Assert.NotNull(generate);
        Assert.NotNull(settings);
        Assert.NotNull(diagnostics);
        Assert.True(generate.Patterns.LegacyIAccessible.IsSupported || generate.Patterns.Invoke.IsSupported);

        settings.AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByText("常规")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        Assert.NotNull(window.FindFirstDescendant(condition.ByText("常规")));

        diagnostics.AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByAutomationId("refresh-diagnostics")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        Assert.NotNull(window.FindFirstDescendant(condition.ByAutomationId("refresh-diagnostics")));

        CloseAndAssertExit(application);
    }

    private static void CloseAndAssertExit(Application application)
    {
        try
        {
            Assert.True(
                application.Close(killIfCloseFails: false),
                "主窗口关闭后应用进程未在关闭超时内退出。");
            Assert.True(application.HasExited, "主窗口关闭后应用进程仍在运行。");
        }
        finally
        {
            if (!application.HasExited)
            {
                application.Kill();
            }
        }
    }

    private static string FindRepositoryRoot()
    {
        var cursor = new DirectoryInfo(AppContext.BaseDirectory);
        while (cursor is not null)
        {
            if (File.Exists(Path.Combine(cursor.FullName, "backend", "app", "web_api.py")))
            {
                return cursor.FullName;
            }
            cursor = cursor.Parent;
        }
        throw new DirectoryNotFoundException("Repository root was not found.");
    }
}
