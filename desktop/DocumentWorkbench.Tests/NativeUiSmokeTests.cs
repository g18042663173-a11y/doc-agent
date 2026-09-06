using System.Diagnostics;
using FlaUI.Core;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Conditions;
using FlaUI.Core.Definitions;
using FlaUI.Core.Tools;
using FlaUI.UIA3;
using System.Text.Json;

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

    [Fact]
    [Trait("Category", "NativeUI")]
    public void DiagnosticsRestartsAnExitedBackend()
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
        try
        {
            var window = Retry.WhileNull(
                () => application.GetMainWindow(automation),
                TimeSpan.FromSeconds(40),
                TimeSpan.FromMilliseconds(250)).Result;
            Assert.NotNull(window);
            var condition = new ConditionFactory(new UIA3PropertyLibrary());
            var backend = Retry.WhileNull(
                () => FindBackendState(application.ProcessId),
                TimeSpan.FromSeconds(30),
                TimeSpan.FromMilliseconds(150)).Result;
            Assert.NotNull(backend);

            using (var process = Process.GetProcessById(backend.ProcessId))
            {
                process.Kill(entireProcessTree: true);
                Assert.True(process.WaitForExit(5000), "The test backend did not exit after termination.");
            }

            var diagnostics = window.FindFirstDescendant(condition.ByAutomationId("nav-diagnostics"));
            Assert.NotNull(diagnostics);
            diagnostics.AsButton().Invoke();

            var replacement = Retry.WhileNull(
                () => FindBackendState(application.ProcessId, backend.ProcessId),
                TimeSpan.FromSeconds(45),
                TimeSpan.FromMilliseconds(250)).Result;
            Assert.NotNull(replacement);
            Assert.NotEqual(backend.ProcessId, replacement.ProcessId);
        }
        finally
        {
            CloseAndAssertExit(application);
        }
    }

    [Fact]
    [Trait("Category", "NativeUI")]
    public void TasksRestartsAnExitedBackendWithoutShowingTheGenericErrorDialog()
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
        try
        {
            var window = Retry.WhileNull(
                () => application.GetMainWindow(automation),
                TimeSpan.FromSeconds(40),
                TimeSpan.FromMilliseconds(250)).Result;
            Assert.NotNull(window);
            var condition = new ConditionFactory(new UIA3PropertyLibrary());
            var backend = Retry.WhileNull(
                () => FindBackendState(application.ProcessId),
                TimeSpan.FromSeconds(30),
                TimeSpan.FromMilliseconds(150)).Result;
            Assert.NotNull(backend);

            using (var process = Process.GetProcessById(backend.ProcessId))
            {
                process.Kill(entireProcessTree: true);
                Assert.True(process.WaitForExit(5000), "The test backend did not exit after termination.");
            }

            var tasks = window.FindFirstDescendant(condition.ByAutomationId("nav-tasks"));
            Assert.NotNull(tasks);
            tasks.AsButton().Invoke();

            var replacement = Retry.WhileNull(
                () => FindBackendState(application.ProcessId, backend.ProcessId),
                TimeSpan.FromSeconds(45),
                TimeSpan.FromMilliseconds(250)).Result;
            Assert.NotNull(replacement);
            Assert.NotEqual(backend.ProcessId, replacement.ProcessId);
            Retry.WhileFalse(
                () => string.Equals(
                    window.FindFirstDescendant(condition.ByAutomationId("service-state"))?.Name,
                    "本地服务已连接",
                    StringComparison.Ordinal),
                TimeSpan.FromSeconds(10),
                TimeSpan.FromMilliseconds(100));
            Assert.Null(window.FindFirstDescendant(condition.ByText("界面操作未能完成。请在“诊断”页检查本地服务状态。")));
        }
        finally
        {
            CloseAndAssertExit(application);
        }
    }

    [Fact]
    [Trait("Category", "NativeUI")]
    public void DiagnosticsExplainsWhenAutomaticBackendRecoveryIsExhausted()
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
        try
        {
            var window = Retry.WhileNull(
                () => application.GetMainWindow(automation),
                TimeSpan.FromSeconds(40),
                TimeSpan.FromMilliseconds(250)).Result;
            Assert.NotNull(window);
            var condition = new ConditionFactory(new UIA3PropertyLibrary());
            var backend = Retry.WhileNull(
                () => FindBackendState(application.ProcessId),
                TimeSpan.FromSeconds(30),
                TimeSpan.FromMilliseconds(150)).Result;
            Assert.NotNull(backend);

            var diagnostics = window.FindFirstDescendant(condition.ByAutomationId("nav-diagnostics"));
            Assert.NotNull(diagnostics);
            diagnostics.AsButton().Invoke();
            Thread.Sleep(600);

            for (var restart = 0; restart < 2; restart++)
            {
                using (var process = Process.GetProcessById(backend.ProcessId))
                {
                    process.Kill(entireProcessTree: true);
                    Assert.True(process.WaitForExit(5000), "The test backend did not exit after termination.");
                }

                var refresh = Retry.WhileNull(
                    () => window.FindFirstDescendant(condition.ByAutomationId("refresh-diagnostics")),
                    TimeSpan.FromSeconds(5),
                    TimeSpan.FromMilliseconds(100)).Result;
                Assert.NotNull(refresh);
                refresh.AsButton().Invoke();

                var previousProcessId = backend.ProcessId;
                backend = Retry.WhileNull(
                    () => FindBackendState(application.ProcessId, previousProcessId),
                    TimeSpan.FromSeconds(45),
                    TimeSpan.FromMilliseconds(250)).Result;
                Assert.NotNull(backend);
                Thread.Sleep(600);
            }

            using (var process = Process.GetProcessById(backend.ProcessId))
            {
                process.Kill(entireProcessTree: true);
                Assert.True(process.WaitForExit(5000), "The test backend did not exit after termination.");
            }

            var finalRefresh = window.FindFirstDescendant(condition.ByAutomationId("refresh-diagnostics"));
            Assert.NotNull(finalRefresh);
            finalRefresh.AsButton().Invoke();

            var guidance = Retry.WhileNull(
                () => window.FindFirstDescendant(condition.ByText("本地服务未能恢复。已保留上次成功的诊断结果；请重新启动工作台后重试。")),
                TimeSpan.FromSeconds(15),
                TimeSpan.FromMilliseconds(150)).Result;
            Assert.NotNull(guidance);
            Assert.Null(window.FindFirstDescendant(condition.ByText("界面操作未能完成。请在“诊断”页检查本地服务状态。")));
        }
        finally
        {
            CloseAndAssertExit(application);
        }
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

    private static BackendState? FindBackendState(int parentProcessId, int? excludedProcessId = null)
    {
        var runtime = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "HuaweiDocumentGenerator",
            "runtime");
        if (!Directory.Exists(runtime))
        {
            return null;
        }

        foreach (var path in Directory.EnumerateFiles(runtime, $"backend-state-{parentProcessId}-*.json"))
        {
            try
            {
                using var document = JsonDocument.Parse(File.ReadAllText(path));
                var root = document.RootElement;
                var processId = root.GetProperty("pid").GetInt32();
                if (processId != excludedProcessId && root.GetProperty("parent_pid").GetInt32() == parentProcessId)
                {
                    return new BackendState(path, processId);
                }
            }
            catch (IOException)
            {
                // The backend writes its state atomically; a concurrent cleanup can still race this probe.
            }
            catch (JsonException)
            {
                // Retry while the state file is being replaced during restart.
            }
        }
        return null;
    }

    private sealed record BackendState(string Path, int ProcessId);
}
