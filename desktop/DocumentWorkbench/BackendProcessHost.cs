using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace DocumentWorkbench;

public sealed class BackendProcessHost : IDisposable
{
    private const int MaxStderrChars = 16 * 1024;
    private readonly Process _process;
    private readonly string _statePath;
    private bool _disposed;

    private BackendProcessHost(Process process, Uri baseAddress, string sessionToken, string appData, string statePath)
    {
        _process = process;
        BaseAddress = baseAddress;
        SessionToken = sessionToken;
        ApplicationDataDirectory = appData;
        _statePath = statePath;
    }

    public Uri BaseAddress { get; }
    public string SessionToken { get; }
    public string ApplicationDataDirectory { get; }
    public int ProcessId => _process.Id;

    /// <summary>
    /// True while the spawned backend process is still alive. Used by the UI to
    /// distinguish a transient connection failure from a backend that has
    /// permanently died (no auto-restart exists in desktop_host), so the job
    /// poll loop can stop instead of retrying forever.
    /// </summary>
    public bool IsProcessAlive()
    {
        try
        {
            return !_process.HasExited;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    public static async Task<BackendProcessHost> StartAsync(CancellationToken cancellationToken)
    {
        var appData = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "HuaweiDocumentGenerator");
        var runtime = Path.Combine(appData, "runtime");
        var jobs = Path.Combine(appData, "jobs");
        Directory.CreateDirectory(runtime);
        Directory.CreateDirectory(jobs);
        CleanupStaleRuntimeFiles(runtime);

        var layout = ResolveRuntimeLayout();
        var sessionToken = Convert.ToBase64String(RandomNumberGenerator.GetBytes(48));
        var nonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(8)).ToLowerInvariant();
        var bootstrapPath = Path.Combine(runtime, $"bootstrap-{Environment.ProcessId}-{nonce}.json");
        var statePath = Path.Combine(runtime, $"backend-state-{Environment.ProcessId}-{nonce}.json");
        var payload = new
        {
            bootstrap_version = "1.0",
            session_token = sessionToken,
            state_path = statePath,
            jobs_path = jobs,
            parent_pid = Environment.ProcessId,
        };
        WriteProtectedBootstrap(bootstrapPath, JsonSerializer.Serialize(payload));

        var start = new ProcessStartInfo
        {
            FileName = layout.PythonExecutable,
            WorkingDirectory = layout.RepositoryRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
        };
        start.ArgumentList.Add("-m");
        start.ArgumentList.Add("app.desktop_host");
        start.ArgumentList.Add("--bootstrap");
        start.ArgumentList.Add(bootstrapPath);
        start.Environment["PYTHONPATH"] = layout.BackendDirectory;
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        // Explicitly forward the gateway credential so the backend defaults to
        // real AI generation (codex/opencode-go) even if the inherited
        // environment were ever filtered; never logs or persists the value.
        var gatewayApiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
        if (!string.IsNullOrWhiteSpace(gatewayApiKey))
        {
            start.Environment["OPENAI_API_KEY"] = gatewayApiKey;
        }

        var process = new Process { StartInfo = start, EnableRaisingEvents = true };
        if (!process.Start())
        {
            File.Delete(bootstrapPath);
            throw new InvalidOperationException("无法启动内置 Python 服务。");
        }
        // Drain both pipes continuously: Windows pipe buffers (4-64 KB) fill and
        // block the child if stdout/stderr are never consumed, which would stall
        // startup and hang long-running jobs on traceback floods.
        var stderrBuffer = new StringBuilder();
        var stderrDrain = StartStreamDrains(process, stderrBuffer);

        try
        {
            var deadline = DateTime.UtcNow.AddSeconds(35);
            while (DateTime.UtcNow < deadline)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (process.HasExited)
                {
                    if (stderrDrain is not null)
                    {
                        await Task.WhenAny(stderrDrain, Task.Delay(500));
                    }
                    string error;
                    lock (stderrBuffer)
                    {
                        error = stderrBuffer.ToString();
                    }
                    throw new InvalidOperationException(SanitizeStartupError(error, process.ExitCode));
                }
                var state = TryReadState(statePath);
                if (state is { Port: > 0 } && state.ParentPid == Environment.ProcessId)
                {
                    var host = new BackendProcessHost(
                        process,
                        new Uri($"http://127.0.0.1:{state.Port}/"),
                        sessionToken,
                        appData,
                        statePath);
                    await host.WaitUntilReadyAsync(cancellationToken);
                    return host;
                }
                await Task.Delay(150, cancellationToken);
            }
            throw new TimeoutException("内置服务未在 35 秒内完成启动。");
        }
        catch
        {
            TryStopOwnedProcess(process);
            TryDelete(bootstrapPath);
            TryDelete(statePath);
            process.Dispose();
            throw;
        }
    }

    private static Task StartStreamDrains(Process process, StringBuilder stderrBuffer)
    {
        _ = DrainStreamAsync(process.StandardOutput, capture: false, stderrBuffer);
        return DrainStreamAsync(process.StandardError, capture: true, stderrBuffer);
    }

    private static async Task DrainStreamAsync(StreamReader reader, bool capture, StringBuilder stderrBuffer)
    {
        try
        {
            while (true)
            {
                var line = await reader.ReadLineAsync().ConfigureAwait(false);
                if (line is null)
                {
                    return;
                }
                if (capture)
                {
                    lock (stderrBuffer)
                    {
                        if (stderrBuffer.Length > MaxStderrChars)
                        {
                            stderrBuffer.Remove(0, stderrBuffer.Length - MaxStderrChars / 2);
                        }
                        stderrBuffer.AppendLine(line);
                    }
                }
            }
        }
        catch (ObjectDisposedException)
        {
        }
        catch (IOException)
        {
        }
    }

    public HttpClient CreateHttpClient()
    {
        var client = new HttpClient(new HttpClientHandler { UseProxy = false })
        {
            BaseAddress = BaseAddress,
            Timeout = TimeSpan.FromMinutes(20),
        };
        client.DefaultRequestHeaders.Add("X-Workbench-Session", SessionToken);
        client.DefaultRequestHeaders.UserAgent.ParseAdd($"DocumentWorkbench/{AppInfo.Version}");
        return client;
    }

    private async Task WaitUntilReadyAsync(CancellationToken cancellationToken)
    {
        using var client = CreateHttpClient();
        client.Timeout = TimeSpan.FromSeconds(2);
        var deadline = DateTime.UtcNow.AddSeconds(20);
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                using var response = await client.GetAsync("api/version", cancellationToken);
                if (response.IsSuccessStatusCode)
                {
                    return;
                }
            }
            catch (HttpRequestException)
            {
            }
            catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
            }
            await Task.Delay(150, cancellationToken);
        }
        throw new TimeoutException("本地 API 未通过就绪检查。");
    }

    private static RuntimeLayout ResolveRuntimeLayout()
    {
        var configured = Environment.GetEnvironmentVariable("DOCUMENT_WORKBENCH_REPO_ROOT");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            var configuredRoot = Path.GetFullPath(configured);
            return DevelopmentLayout(configuredRoot);
        }

        var baseDirectory = AppContext.BaseDirectory;
        var packagedPython = Path.Combine(baseDirectory, "runtime", "python", "pythonw.exe");
        var packagedBackend = Path.Combine(baseDirectory, "app", "backend");
        if (File.Exists(packagedPython) && Directory.Exists(packagedBackend))
        {
            return new RuntimeLayout(packagedPython, packagedBackend, Path.Combine(baseDirectory, "app"));
        }

        var cursor = new DirectoryInfo(baseDirectory);
        while (cursor is not null)
        {
            if (File.Exists(Path.Combine(cursor.FullName, "backend", "app", "web_api.py")))
            {
                return DevelopmentLayout(cursor.FullName);
            }
            cursor = cursor.Parent;
        }
        throw new FileNotFoundException("未找到内置 Python 运行时或开发仓库。");
    }

    private static RuntimeLayout DevelopmentLayout(string repositoryRoot)
    {
        var pythonw = Path.Combine(repositoryRoot, ".venv", "Scripts", "pythonw.exe");
        if (!File.Exists(pythonw))
        {
            pythonw = Path.Combine(repositoryRoot, ".venv", "Scripts", "python.exe");
        }
        var backend = Path.Combine(repositoryRoot, "backend");
        if (!File.Exists(pythonw) || !Directory.Exists(backend))
        {
            throw new FileNotFoundException("开发环境缺少 .venv 或 backend。请先运行 bootstrap_windows.ps1。");
        }
        return new RuntimeLayout(pythonw, backend, repositoryRoot);
    }

    private static void WriteProtectedBootstrap(string path, string content)
    {
        File.WriteAllText(path, content, new UTF8Encoding(false));
        try
        {
            var identity = WindowsIdentity.GetCurrent();
            var sid = identity.User ?? throw new InvalidOperationException("无法识别当前 Windows 用户。");
            var security = new FileSecurity();
            security.SetOwner(sid);
            security.SetAccessRuleProtection(true, false);
            security.AddAccessRule(new FileSystemAccessRule(
                sid,
                FileSystemRights.FullControl,
                AccessControlType.Allow));
            new FileInfo(path).SetAccessControl(security);
        }
        catch
        {
            TryDelete(path);
            throw new InvalidOperationException("无法保护桌面会话启动文件。");
        }
    }

    private static BackendState? TryReadState(string path)
    {
        try
        {
            if (!File.Exists(path))
            {
                return null;
            }
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            return new BackendState
            {
                Pid = root.GetProperty("pid").GetInt32(),
                ParentPid = root.GetProperty("parent_pid").GetInt32(),
                Port = root.GetProperty("port").GetInt32(),
            };
        }
        catch (IOException)
        {
            return null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static void CleanupStaleRuntimeFiles(string runtime)
    {
        foreach (var path in Directory.EnumerateFiles(runtime, "bootstrap-*.json"))
        {
            if (File.GetLastWriteTimeUtc(path) < DateTime.UtcNow.AddMinutes(-2))
            {
                TryDelete(path);
            }
        }
        foreach (var path in Directory.EnumerateFiles(runtime, "backend-state-*.json"))
        {
            var state = TryReadState(path);
            if (state is null || !IsProcessRunning(state.Pid))
            {
                TryDelete(path);
            }
        }
    }

    private static bool IsProcessRunning(int pid)
    {
        try
        {
            using var process = Process.GetProcessById(pid);
            return !process.HasExited;
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

    private static string SanitizeStartupError(string value, int exitCode)
    {
        var lastLine = value.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        if (string.IsNullOrWhiteSpace(lastLine))
        {
            return $"内置服务退出，代码 {exitCode}。";
        }
        var sanitized = lastLine.Trim();
        return sanitized.Length <= 300 ? sanitized : sanitized[..300];
    }

    private static void TryStopOwnedProcess(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(true);
                process.WaitForExit(3000);
            }
        }
        catch (InvalidOperationException)
        {
        }
        catch (System.ComponentModel.Win32Exception)
        {
        }
    }

    private static void TryDelete(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        TryStopOwnedProcess(_process);
        _process.Dispose();
        TryDelete(_statePath);
    }

    private sealed record RuntimeLayout(string PythonExecutable, string BackendDirectory, string RepositoryRoot);

    private sealed class BackendState
    {
        public int Pid { get; set; }
        public int ParentPid { get; set; }
        public int Port { get; set; }
    }
}
