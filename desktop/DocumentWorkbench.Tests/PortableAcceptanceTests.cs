using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using FlaUI.Core;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Conditions;
using FlaUI.Core.Tools;
using FlaUI.UIA3;

namespace DocumentWorkbench.Tests;

/// <summary>
/// 交付验收用：对便携包或已安装的 DocumentWorkbench.exe 做 UI 走查。
/// 通过 DOCUMENT_WORKBENCH_EXE 指定目标 exe（缺省时跳过，不影响常规测试），
/// DOCUMENT_WORKBENCH_SHOT_DIR 指定截图输出目录。
/// </summary>
public sealed class PortableAcceptanceTests
{
    [Fact]
    [Trait("Category", "PortableAcceptance")]
    public void SettingsExposeThemeAndNgaControls()
    {
        if (!System.OperatingSystem.IsWindows())
        {
            return;
        }
        var executable = Environment.GetEnvironmentVariable("DOCUMENT_WORKBENCH_EXE");
        if (string.IsNullOrWhiteSpace(executable) || !File.Exists(executable))
        {
            return; // 未指定目标 exe：跳过（常规 CI/verify 不受影响）
        }
        var shotDir = Environment.GetEnvironmentVariable("DOCUMENT_WORKBENCH_SHOT_DIR")
            ?? Path.Combine(Path.GetTempPath(), "dw-acceptance-shots");
        Directory.CreateDirectory(shotDir);

        var start = new ProcessStartInfo(executable)
        {
            WorkingDirectory = Path.GetDirectoryName(executable)!,
            UseShellExecute = false,
        };
        using var application = Application.Launch(start);
        using var automation = new UIA3Automation();
        var window = Retry.WhileNull(
            () => application.GetMainWindow(automation),
            TimeSpan.FromSeconds(60),
            TimeSpan.FromMilliseconds(250)).Result;
        Assert.NotNull(window);
        Assert.Equal("文档生成工作台", window.Title);
        var condition = new ConditionFactory(new UIA3PropertyLibrary());

        // 主窗口：引擎状态（侧栏 GeneratorStateText，x:Name 即 AutomationId）
        var engineState = Retry.WhileNull(
            () => window.FindFirstDescendant(condition.ByAutomationId("GeneratorStateText")),
            TimeSpan.FromSeconds(30),
            TimeSpan.FromMilliseconds(250)).Result;
        Assert.NotNull(engineState);
        Assert.Contains("生成器", engineState.Name);
        CaptureShot(window, shotDir, "01-main");

        // 设置 > 常规：默认 PPT 主题（含学术版）
        RequireElement(window.FindFirstDescendant(condition.ByAutomationId("nav-settings")), "nav-settings").AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByText("默认 PPT 主题")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        Assert.NotNull(window.FindFirstDescendant(condition.ByAutomationId("DefaultThemeComboBox")));
        CaptureShot(window, shotDir, "02-settings-general");

        // 设置 > NGA：调用方式 + 当前生成器状态
        RequireElement(window.FindFirstDescendant(condition.ByName("NGA")), "NGA").AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByAutomationId("nga-transport")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        var ngaState = window.FindFirstDescendant(condition.ByAutomationId("NgaActiveStateText"));
        Assert.NotNull(ngaState);
        Assert.Contains("当前生成器", ngaState.Name);
        CaptureShot(window, shotDir, "03-settings-nga");

        // 诊断页：当前生成器字段存在
        RequireElement(window.FindFirstDescendant(condition.ByAutomationId("nav-diagnostics")), "nav-diagnostics").AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByAutomationId("refresh-diagnostics")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        Assert.NotNull(window.FindFirstDescendant(condition.ByAutomationId("DiagnosticGenerator")));
        CaptureShot(window, shotDir, "04-diagnostics");

        // 生成页：简洁/高级渐进披露——默认收起（主题下拉不在 UIA 树），展开后可见
        Mark(shotDir, "before-nav-generate");
        RequireElement(window.FindFirstDescendant(condition.ByAutomationId("nav-generate")), "nav-generate").AsButton().Invoke();
        Thread.Sleep(300);
        var themeProbe = () =>
        {
            var theme = window.FindFirstDescendant(condition.ByAutomationId("deck-theme"));
            return theme is not null && !IsOffscreen(theme);
        };
        Assert.False(
            Retry.WhileFalse(themeProbe, TimeSpan.FromSeconds(2), TimeSpan.FromMilliseconds(100)).Result,
            "高级选项默认应收起");
        Mark(shotDir, "advanced-collapsed-ok");
        var toggle = RequireElement(window.FindFirstDescendant(condition.ByAutomationId("advanced-toggle")), "advanced-toggle").AsToggleButton();
        toggle.Toggle();
        Mark(shotDir, "toggled-advanced state=" + toggle.ToggleState);
        Retry.WhileFalse(themeProbe, TimeSpan.FromSeconds(5), TimeSpan.FromMilliseconds(100));
        Mark(shotDir, "deck-theme-visible");
        Assert.True(themeProbe(), "展开后应出现输出主题选择");
        Assert.NotNull(window.FindFirstDescendant(condition.ByAutomationId("select-template")));
        CaptureShot(window, shotDir, "05-advanced");
        Mark(shotDir, "captured-05");

        // 外观：依次留存浅色、深色和跟随系统；先回到"常规"子页——上文 NGA 子页可能仍处于选中。
        RequireElement(window.FindFirstDescendant(condition.ByAutomationId("nav-settings")), "nav-settings").AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByAutomationId("GeneralSettingsButton")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        RequireElement(window.FindFirstDescendant(condition.ByAutomationId("GeneralSettingsButton")), "GeneralSettingsButton").AsButton().Invoke();
        Retry.WhileFalse(
            () => window.FindFirstDescendant(condition.ByAutomationId("appearance-select")) is not null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromMilliseconds(100));
        Mark(shotDir, "settings-visible");
        var appearance = RequireElement(window.FindFirstDescendant(condition.ByAutomationId("appearance-select")), "appearance-select").AsComboBox();
        appearance.Expand();
        Mark(shotDir, "combo-expanded");
        Retry.WhileFalse(() => appearance.Items.Length >= 2, TimeSpan.FromSeconds(5), TimeSpan.FromMilliseconds(100));
        Mark(shotDir, "items-counted");
        appearance.Items.First(item => item.Text.Contains("浅色")).AsListBoxItem().Select();
        Mark(shotDir, "light-selected");
        Thread.Sleep(400);
        CaptureShot(window, shotDir, "06-light-settings");
        Mark(shotDir, "captured-06");
        appearance.Expand();
        appearance.Items.First(item => item.Text.Contains("深色")).AsListBoxItem().Select();
        Mark(shotDir, "dark-reselected");
        Thread.Sleep(400);
        CaptureShot(window, shotDir, "07-dark-settings");
        appearance.Expand();
        appearance.Items.First(item => item.Text.Contains("跟随系统")).AsListBoxItem().Select();
        Mark(shotDir, "system-selected");
        Thread.Sleep(400);
        CaptureShot(window, shotDir, "08-system-settings");

        // 紧凑与宽屏窗口：无裁切、无横向溢出目检用截图
        var transform = window.Patterns.Transform.PatternOrDefault;
        Mark(shotDir, "transform-null=" + (transform is null));
        if (transform is not null)
        {
            transform.Resize(1024, 700);
            Thread.Sleep(400);
            CaptureShot(window, shotDir, "09-compact-1024x700");
            transform.Resize(1280, 820);
            Thread.Sleep(400);
            CaptureShot(window, shotDir, "10-standard-1280x820");
            transform.Resize(1920, 1080);
            Thread.Sleep(400);
            CaptureShot(window, shotDir, "11-wide-1920x1080");
        }
        Mark(shotDir, "before-close");

        CloseAndAssertExit(application);
        Mark(shotDir, "closed");
    }

    private static void CloseAndAssertExit(Application application)
    {
        try
        {
            Assert.True(
                application.Close(killIfCloseFails: false),
                "主窗口关闭后便携包进程未在关闭超时内退出。");
            Assert.True(application.HasExited, "主窗口关闭后便携包进程仍在运行。");
        }
        finally
        {
            if (!application.HasExited)
            {
                application.Kill();
            }
        }
    }

    private static void Mark(string shotDir, string marker) =>
        File.AppendAllText(Path.Combine(shotDir, "progress.log"), $"{DateTime.Now:HH:mm:ss.fff} {marker}\n");

    private static bool IsOffscreen(AutomationElement element) =>
        element.Properties.IsOffscreen.ValueOrDefault;

    private static AutomationElement RequireElement(AutomationElement? element, string automationId) =>
        element ?? throw new InvalidOperationException($"Missing required UI Automation element: {automationId}");

    private static void CaptureShot(Window window, string shotDir, string name)
    {
        try
        {
            window.SetForeground();
        }
        catch
        {
            // 前台失败不阻断：截图仍以窗口区域为准
        }
        Thread.Sleep(600);
        var handle = new IntPtr(window.Properties.NativeWindowHandle.ValueOrDefault);
        Assert.NotEqual(IntPtr.Zero, handle);

        // PrintWindow renders the target HWND directly. This is independent of
        // foreground-window restrictions and desktop coordinate virtualization.
        var previousDpiContext = SetThreadDpiAwarenessContext(PerMonitorAwareV2);
        try
        {
            Assert.True(GetWindowRect(handle, out var bounds), "无法读取主窗口边界。");
            var width = bounds.Right - bounds.Left;
            var height = bounds.Bottom - bounds.Top;
            Assert.True(width > 0 && height > 0, $"主窗口边界无效：{width}x{height}");

            using var bitmap = new Bitmap(width, height);
            using var graphics = Graphics.FromImage(bitmap);
            var deviceContext = graphics.GetHdc();
            try
            {
                Assert.True(
                    PrintWindow(handle, deviceContext, PrintWindowRenderFullContent),
                    $"PrintWindow 采集失败（Win32={Marshal.GetLastWin32Error()}）。");
            }
            finally
            {
                graphics.ReleaseHdc(deviceContext);
            }

            bitmap.Save(Path.Combine(shotDir, $"{name}.png"), ImageFormat.Png);
            Mark(shotDir, $"captured-{name} {width}x{height}");
        }
        finally
        {
            if (previousDpiContext != IntPtr.Zero)
            {
                SetThreadDpiAwarenessContext(previousDpiContext);
            }
        }
    }

    private const uint PrintWindowRenderFullContent = 0x00000002;
    private static readonly IntPtr PerMonitorAwareV2 = new(-4);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool GetWindowRect(IntPtr windowHandle, out NativeRect bounds);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool PrintWindow(IntPtr windowHandle, IntPtr deviceContext, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetThreadDpiAwarenessContext(IntPtr dpiContext);

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
