using System.Windows;
using System.Windows.Threading;

namespace DocumentWorkbench;

public partial class App : Application
{
    private BackendProcessHost? _backend;

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        try
        {
            _backend = await BackendProcessHost.StartAsync(CancellationToken.None);
            var settingsStore = new SettingsStore(_backend.ApplicationDataDirectory);
            var window = new MainWindow(_backend, settingsStore);
            MainWindow = window;
            window.Show();
            ShutdownMode = ShutdownMode.OnMainWindowClose;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"本地服务启动失败。\n\n{SafeMessage(ex)}",
                "文档生成工作台",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            Shutdown(1);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _backend?.Dispose();
        base.OnExit(e);
    }

    private static string SafeMessage(Exception exception)
    {
        var value = exception.Message.Replace('\r', ' ').Replace('\n', ' ').Trim();
        return value.Length <= 400 ? value : value[..400];
    }

    private static void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        MessageBox.Show(
            "界面操作未能完成。请在“诊断”页检查本地服务状态。",
            "文档生成工作台",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        e.Handled = true;
    }
}
