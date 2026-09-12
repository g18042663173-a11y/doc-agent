using Microsoft.Win32;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net.Http;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace DocumentWorkbench;

public partial class MainWindow : Window
{
    private static readonly IReadOnlyDictionary<string, string> AuditLabels = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["lint"] = "合规报告",
        ["profile"] = "模板 Profile",
        ["plan"] = "页面映射 Plan",
        ["structure"] = "模板结构报告",
        ["replacement-audit"] = "模板替换审计",
        ["package-report"] = "PPTX 包关系报告",
        ["failure-report"] = "失败诊断报告",
        ["asset-manifest"] = "图片资产清单",
        ["asset-usage-audit"] = "图片使用审计",
        ["visual-plan"] = "视觉计划",
        ["visual-selection-audit"] = "视觉选择审计",
        ["deck-ir"] = "结构化内容（DeckIR，可改后重渲染）",
    };

    private BackendProcessHost _backend;
    private readonly SettingsStore _settingsStore;
    private WorkbenchApiClient _api;
    private readonly CancellationTokenSource _lifetime = new();
    private WorkbenchSettings _settings = new();
    private string? _inputPath;
    private string? _templatePath;
    private TemplateValidationState _templateValidationState;
    private TemplateFingerprint? _validatedTemplateFingerprint;
    private int _templateValidationGeneration;
    private bool _templateRepairAvailable;
    private readonly ObservableCollection<string> _assetPaths = [];
    private JobInfo? _currentJob;
    private long _pollGeneration;
    private bool _serviceReady;
    private bool _generatorBlocked;
    private bool _busy;
    private bool _ngaDraftTested;
    private int _backendRestarts;
    private DateTime? _lastDiagnosticsUpdatedAt;
    private readonly SemaphoreSlim _backendRestartGate = new(1, 1);

    private enum TemplateValidationState
    {
        None,
        Validating,
        Valid,
        Invalid,
    }

    private readonly record struct TemplateFingerprint(long Length, DateTime LastWriteTimeUtc);

    public MainWindow(BackendProcessHost backend, SettingsStore settingsStore)
    {
        InitializeComponent();
        FitToWorkingArea();
        _backend = backend;
        _settingsStore = settingsStore;
        _api = new WorkbenchApiClient(backend.CreateHttpClient());
        Jobs = [];
        DataContext = this;
        AssetListBox.ItemsSource = _assetPaths;
        JobsPathTextBox.Text = Path.Combine(backend.ApplicationDataDirectory, "jobs");
        BuildStageTrack();
        SystemParameters.StaticPropertyChanged += SystemParameters_StaticPropertyChanged;
        SystemEvents.UserPreferenceChanged += SystemEvents_UserPreferenceChanged;
    }

    // 与后端任务阶段一一对应（StageLabels），仅做可视化，不伪造进度
    private static readonly string[] StageOrder =
    [
        "queued", "parsing", "normalizing_assets", "planning_visuals", "generating",
        "profiling_template", "planning_template", "rendering", "linting", "validating_package",
    ];

    private void BuildStageTrack()
    {
        StageTrackText.Inlines.Clear();
        for (var index = 0; index < StageOrder.Length; index++)
        {
            if (index > 0)
            {
                StageTrackText.Inlines.Add(new System.Windows.Documents.Run(" → ")
                {
                    Foreground = (Brush)FindResource("FaintTextBrush"),
                });
            }
            StageTrackText.Inlines.Add(new System.Windows.Documents.Run(StageLabels.Value(StageOrder[index])));
        }
        UpdateStageTrack("queued", "pending");
    }

    private void UpdateStageTrack(string stageKey, string status)
    {
        var current = Array.IndexOf(StageOrder, stageKey);
        var runIndex = 0;
        foreach (var inline in StageTrackText.Inlines)
        {
            if (inline is not System.Windows.Documents.Run run || run.Text == " → ")
            {
                continue;
            }
            var state = status == "done" ? 2
                : current < 0 ? 0
                : runIndex < current ? 2
                : runIndex == current ? 1
                : 0;
            run.Foreground = (Brush)FindResource(state switch
            {
                1 => "AccentOnDarkBrush",
                2 => "MutedTextBrush",
                _ => "FaintTextBrush",
            });
            run.FontWeight = state == 1 ? FontWeights.SemiBold : FontWeights.Normal;
            runIndex++;
        }
    }

    public ObservableCollection<JobInfo> Jobs { get; }

    private void FitToWorkingArea()
    {
        const double edgeMargin = 8;
        var area = SystemParameters.WorkArea;
        var availableWidth = Math.Max(760, area.Width - edgeMargin * 2);
        var availableHeight = Math.Max(480, area.Height - edgeMargin * 2);
        MinWidth = Math.Min(1024, availableWidth);
        MinHeight = Math.Min(700, availableHeight);
        Width = Math.Min(1280, availableWidth);
        Height = Math.Min(820, availableHeight);
        WindowStartupLocation = WindowStartupLocation.Manual;
        Left = area.Left + Math.Max(0, (area.Width - Width) / 2);
        Top = area.Top + Math.Max(0, (area.Height - Height) / 2);
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            _settings = await _settingsStore.LoadAsync();
            ApplySettingsToControls();
            await InitializeServiceAsync();
            await RefreshJobsAsync();
            var running = Jobs.FirstOrDefault(job => job.Status is "pending" or "running");
            if (running is not null)
            {
                _currentJob = running;
                ShowJob(running);
                _ = PollCurrentJobAsync(running.JobId, _lifetime.Token);
            }
        }
        catch (Exception ex)
        {
            SetServiceState(false, "本地服务不可用");
            ShowOperationError(ex, "初始化未完成");
        }
        finally
        {
            UpdateActionState();
        }
    }

    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        SystemParameters.StaticPropertyChanged -= SystemParameters_StaticPropertyChanged;
        SystemEvents.UserPreferenceChanged -= SystemEvents_UserPreferenceChanged;
        _lifetime.Cancel();
        _api.Dispose();
    }

    private async Task InitializeServiceAsync()
    {
        var version = await _api.GetVersionAsync(_lifetime.Token);
        if (version.ApiVersion != "1.0" || version.DeckIrVersion != "2.2")
        {
            _generatorBlocked = true;
            SetServiceState(false, "版本不兼容");
            GenerateGuardText.Text = $"需要 API 1.0 / DeckIR 2.2，当前为 {version.ApiVersion} / {version.DeckIrVersion}";
            return;
        }

        SidebarVersionText.Text = $"本地服务 v{version.AppVersion}";
        SetServiceState(true, "本地服务已连接");

        if (!_settings.NgaEnabled)
        {
            // Do not force the stub generator here: the backend defaults to
            // real AI generation (codex/opencode-go) when OPENAI_API_KEY is
            // configured and falls back to the deterministic stub otherwise.
            // Forcing stub would override that AI-first default on every start.
            _generatorBlocked = false;
            try
            {
                var current = await _api.GetGeneratorSettingsAsync(_lifetime.Token);
                var activeName = current.Active?.Name ?? "stub";
                var label = activeName == "nga" ? "NGA" : activeName == "codex" ? "opencode-go" : "stub";
                GeneratorStateText.Text = $"生成器：{label}";
                GeneratorActiveStateText.Text = $"当前生成器：{label}";
                LoadGeneratorControls(current);
            }
            catch (Exception)
            {
                GeneratorStateText.Text = "生成器：未知";
                GeneratorActiveStateText.Text = "当前生成器：未知";
            }
            return;
        }

        var token = CredentialManager.ReadNgaToken();
        if (string.IsNullOrWhiteSpace(token))
        {
            BlockNga("NGA 已启用，但 Windows 凭据中没有 Token。请在设置中补充并重新测试。");
            return;
        }

        try
        {
            await _api.ConfigureGeneratorAsync("nga", _settings.Nga, token, false, _settings.GeneratorMode, _lifetime.Token);
            var tested = await _api.TestGeneratorAsync(_lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            _ngaDraftTested = true;
            _generatorBlocked = false;
            GeneratorStateText.Text = "生成器：NGA";
            GeneratorActiveStateText.Text = "当前生成器：NGA";
            GeneratorOperationStatusText.Text = $"已恢复连接，延迟 {tested.Connection?.LatencyMs ?? 0} ms";
        }
        catch (Exception ex)
        {
            BlockNga($"NGA 恢复失败：{SafeFailureText(ex)}");
        }
    }

    private void BlockNga(string message)
    {
        _generatorBlocked = true;
        _ngaDraftTested = false;
        GeneratorStateText.Text = "生成器：NGA 配置异常";
        GeneratorActiveStateText.Text = "当前生成器：NGA 未就绪";
        GeneratorOperationStatusText.Text = message;
        GenerateGuardText.Text = message;
    }

    private void ApplySettingsToControls()
    {
        SelectComboByTag(AppearanceComboBox, _settings.Appearance);
        ApplyAppearance(_settings.Appearance);
        SelectComboByTag(DefaultTargetComboBox, string.IsNullOrWhiteSpace(_settings.DefaultTarget) ? "deck" : _settings.DefaultTarget);
        SelectComboByText(DefaultDepthComboBox, string.IsNullOrWhiteSpace(_settings.DefaultDepth) ? "标准" : _settings.DefaultDepth);
        SelectComboByTag(TargetComboBox, string.IsNullOrWhiteSpace(_settings.DefaultTarget) ? "deck" : _settings.DefaultTarget);
        SelectComboByText(DepthComboBox, string.IsNullOrWhiteSpace(_settings.DefaultDepth) ? "标准" : _settings.DefaultDepth);
        SelectComboByTag(DefaultThemeComboBox, string.IsNullOrWhiteSpace(_settings.DefaultTheme) ? "hw_v1" : _settings.DefaultTheme);
        SelectComboByTag(GenerateThemeComboBox, string.IsNullOrWhiteSpace(_settings.DefaultTheme) ? "hw_v1" : _settings.DefaultTheme);
        NgaCliPathTextBox.Text = string.IsNullOrWhiteSpace(_settings.Nga.CliPath) ? "nga" : _settings.Nga.CliPath;
        NgaBaseUrlTextBox.Text = _settings.Nga.BaseUrl;
        NgaEndpointTextBox.Text = string.IsNullOrWhiteSpace(_settings.Nga.EndpointPath)
            ? "/v1/chat/completions"
            : _settings.Nga.EndpointPath;
        NgaModelTextBox.Text = _settings.Nga.Model;
        NgaTimeoutTextBox.Text = _settings.Nga.TimeoutSeconds.ToString(CultureInfo.InvariantCulture);
        SelectComboByText(NgaRetriesComboBox, _settings.Nga.MaxRetries.ToString(CultureInfo.InvariantCulture));
        SelectComboByTag(NgaResponseFormatComboBox, _settings.Nga.ResponseFormat);
        NgaVerifyTlsCheckBox.IsChecked = _settings.Nga.VerifyTls;
        NgaAllowHttpCheckBox.IsChecked = _settings.Nga.AllowInsecureHttp;
        NgaCaPathTextBox.Text = _settings.Nga.CaBundlePath ?? "";
        NgaCredentialStateText.Text = CredentialManager.ReadNgaToken() is null
            ? "未保存凭据"
            : "Token 已保存在 Windows 凭据管理器";
        CodexBaseUrlTextBox.Text = _settings.Codex.BaseUrl;
        CodexModelTextBox.Text = _settings.Codex.Model;
        CodexApiModeComboBox.SelectedIndex = _settings.Codex.ApiMode == "chat_completions" ? 1 : 0;
        CodexTimeoutTextBox.Text = _settings.Codex.TimeoutSeconds.ToString();
        CodexReasoningComboBox.SelectedIndex = _settings.Codex.ReasoningEffort == "medium" ? 1 : _settings.Codex.ReasoningEffort == "low" ? 2 : 0;
        CodexCredentialStateText.Text = CredentialManager.ReadCodexToken() is null
            ? "密钥：未保存（使用环境变量 OPENAI_API_KEY）"
            : "密钥：已保存在 Windows 凭据管理器";
        ApplyChannelVisibility();
        UpdateDeckOptionsVisibility();
    }

    private void ApplyChannelVisibility()
    {
        var channel = ComboTag(GeneratorChannelComboBox, "stub");
        var isNgaCli = channel == "nga-cli";
        var isNgaHttp = channel == "nga-http";
        var isCodex = channel == "codex";
        ChannelHintText.Text = channel switch
        {
            "stub" => "确定性生成，不调用 AI；适合流程验证与离线环境。",
            "nga-cli" => "本机已登录 NGA 直接可用：认证、Token 刷新由 NGA 自行管理，无需填写任何凭据。",
            "nga-http" => "适用于内网 OpenAI 兼容 AI 服务：需服务根地址、接口路径与 Bearer Token。",
            "codex" => "opencode-go 或任意 OpenAI 兼容网关；API 密钥留空时使用环境变量 OPENAI_API_KEY。",
            _ => "",
        };
        SetVisible(NgaCliPathLabel, isNgaCli);
        SetVisible(NgaCliPathTextBox, isNgaCli);
        SetVisible(NgaModelLabel, isNgaCli || isNgaHttp);
        SetVisible(NgaModelTextBox, isNgaCli || isNgaHttp);
        foreach (var name in new[] { "NgaBaseUrlLabel", "NgaEndpointLabel", "NgaTokenLabel", "NgaResponseFormatLabel", "NgaCaLabel" })
        {
            if (FindName(name) is TextBlock label) label.Visibility = isNgaHttp ? Visibility.Visible : Visibility.Collapsed;
        }
        foreach (var name in new[] { "NgaBaseUrlTextBox", "NgaEndpointTextBox", "NgaTokenPasswordBox", "NgaResponseFormatComboBox", "NgaVerifyTlsCheckBox", "NgaAllowHttpCheckBox", "NgaCaPathTextBox", "NgaCaRow" })
        {
            if (FindName(name) is UIElement control) control.Visibility = isNgaHttp ? Visibility.Visible : Visibility.Collapsed;
        }
        NgaCredentialStateText.Visibility = isNgaHttp ? Visibility.Visible : Visibility.Collapsed;
        SetVisible(NgaTimeoutLabel, isNgaCli || isNgaHttp);
        SetVisible(NgaTimeoutTextBox, isNgaCli || isNgaHttp);
        SetVisible(NgaRetriesLabel, isNgaCli || isNgaHttp);
        SetVisible(NgaRetriesComboBox, isNgaCli || isNgaHttp);
        foreach (var name in new[] { "CodexBaseUrlLabel", "CodexModelLabel", "CodexApiModeLabel", "CodexApiKeyLabel", "CodexHintText" })
        {
            if (FindName(name) is TextBlock label) label.Visibility = isCodex ? Visibility.Visible : Visibility.Collapsed;
        }
        foreach (var name in new[] { "CodexBaseUrlTextBox", "CodexModelTextBox", "CodexApiModeComboBox", "CodexApiKeyPasswordBox", "CodexCredentialStateText", "CodexTimeoutLabel", "CodexTimeoutTextBox", "CodexReasoningLabel", "CodexReasoningComboBox" })
        {
            if (FindName(name) is UIElement control) control.Visibility = isCodex ? Visibility.Visible : Visibility.Collapsed;
        }
        DeleteNgaTokenButton.Visibility = isNgaHttp ? Visibility.Visible : Visibility.Collapsed;
    }

    private static void SetVisible(UIElement element, bool visible) => element.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;

    private void GeneratorChannel_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        ApplyChannelVisibility();
    }

    private void SetServiceState(bool connected, string text)
    {
        _serviceReady = connected;
        ServiceDot.Fill = connected
            ? (Brush)FindResource("SuccessBrush")
            : (Brush)FindResource("DangerBrush");
        ServiceStateText.Text = text;
        TopbarStatusText.Text = text;
        UpdateActionState();
    }

    private void SetTasksSyncStatus(string? text, bool warning = false)
    {
        TasksSyncStatusText.Text = text ?? string.Empty;
        TasksSyncStatusText.Foreground = (Brush)FindResource(warning ? "WarningBrush" : "MutedTextBrush");
        TasksSyncStatusText.Visibility = string.IsNullOrWhiteSpace(text)
            ? Visibility.Collapsed
            : Visibility.Visible;
    }

    private void SetDiagnosticsStatus(string? text, bool warning = false)
    {
        DiagnosticsStatusText.Text = text ?? string.Empty;
        DiagnosticsStatusText.Foreground = (Brush)FindResource(warning ? "WarningBrush" : "MutedTextBrush");
        DiagnosticsStatusText.Visibility = string.IsNullOrWhiteSpace(text)
            ? Visibility.Collapsed
            : Visibility.Visible;
    }

    private void UpdateActionState()
    {
        var available = _serviceReady && !_generatorBlocked && !_busy && File.Exists(_inputPath);
        var templateBlocksGeneration = TemplateBlocksGeneration();
        AnalyzeButton.IsEnabled = available;
        GenerateButton.IsEnabled = available && !templateBlocksGeneration;
        CancelButton.IsEnabled = _currentJob is { Status: "pending" or "running" };
        if (_generatorBlocked)
        {
            GenerateGuardText.Text = string.IsNullOrWhiteSpace(GenerateGuardText.Text)
                ? "NGA 配置未就绪，生成已阻断"
                : GenerateGuardText.Text;
        }
        else if (!_serviceReady)
        {
            GenerateGuardText.Text = "本地服务未连接";
        }
        else if (!File.Exists(_inputPath))
        {
            GenerateGuardText.Text = "请选择输入资料";
        }
        else if (_busy)
        {
            GenerateGuardText.Text = "正在处理当前操作";
        }
        else if (templateBlocksGeneration)
        {
            GenerateGuardText.Text = _templateValidationState == TemplateValidationState.Validating
                ? "正在检查所选 PPT 模板"
                : "请先处理模板校验提示";
        }
        else
        {
            GenerateGuardText.Text = "可先分析资料，也可直接生成";
        }
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        BrowseState(busy);
        UpdateActionState();
    }

    private void BrowseState(bool busy)
    {
        TargetComboBox.IsEnabled = !busy;
        DepthComboBox.IsEnabled = !busy;
        DefaultTargetComboBox.IsEnabled = !busy;
        DefaultDepthComboBox.IsEnabled = !busy;
        RepairTemplateButton.IsEnabled = _templateRepairAvailable && !busy;
    }

    private bool TemplateBlocksGeneration() =>
        CurrentTarget() == "deck" &&
        !string.IsNullOrWhiteSpace(_templatePath) &&
        _templateValidationState != TemplateValidationState.Valid;

    private void SetTemplateValidationStatus(string? text, string brushResource = "MutedTextBrush")
    {
        TemplateValidationText.Text = text ?? string.Empty;
        TemplateValidationText.Foreground = (Brush)FindResource(brushResource);
        TemplateValidationText.Visibility = string.IsNullOrWhiteSpace(text)
            ? Visibility.Collapsed
            : Visibility.Visible;
    }

    private void SetTemplateRepairAvailable(bool available)
    {
        _templateRepairAvailable = available;
        RepairTemplateButton.Visibility = available ? Visibility.Visible : Visibility.Collapsed;
        RepairTemplateButton.IsEnabled = available && !_busy;
    }

    private static bool IsRepairableHyperlinkFailure(WorkbenchApiException exception) =>
        exception.Failure.Code == "E003" &&
        (exception.Failure.Message.Contains("(hyperlink)", StringComparison.OrdinalIgnoreCase) ||
         exception.Failure.Message.Contains("外部超链接", StringComparison.Ordinal));

    private static bool TryGetTemplateFingerprint(string path, out TemplateFingerprint fingerprint)
    {
        try
        {
            var info = new FileInfo(path);
            if (!info.Exists)
            {
                fingerprint = default;
                return false;
            }
            fingerprint = new TemplateFingerprint(info.Length, info.LastWriteTimeUtc);
            return true;
        }
        catch (IOException)
        {
            fingerprint = default;
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            fingerprint = default;
            return false;
        }
    }

    private async Task<bool> EnsureTemplateValidatedAsync()
    {
        var templatePath = _templatePath;
        if (string.IsNullOrWhiteSpace(templatePath))
        {
            SetTemplateRepairAvailable(false);
            return true;
        }
        if (!TryGetTemplateFingerprint(templatePath, out var fingerprint))
        {
            _templateValidationGeneration++;
            _templateValidationState = TemplateValidationState.Invalid;
            _validatedTemplateFingerprint = null;
            SetTemplateValidationStatus("模板文件无法读取或已被移动，请重新选择。", "DangerBrush");
            SetTemplateRepairAvailable(false);
            UpdateActionState();
            return false;
        }
        if (_templateValidationState == TemplateValidationState.Valid &&
            _validatedTemplateFingerprint is TemplateFingerprint validated &&
            validated == fingerprint)
        {
            return true;
        }
        if (_templateValidationState == TemplateValidationState.Validating)
        {
            return false;
        }

        var validationGeneration = ++_templateValidationGeneration;
        _templateValidationState = TemplateValidationState.Validating;
        _validatedTemplateFingerprint = null;
        SetTemplateValidationStatus("正在检查模板安全性...", "MutedTextBrush");
        SetTemplateRepairAvailable(false);
        UpdateActionState();
        try
        {
            var result = await _api.ValidateTemplateAsync(templatePath, _lifetime.Token);
            if (validationGeneration != _templateValidationGeneration ||
                !string.Equals(templatePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
            if (!result.Valid || !TryGetTemplateFingerprint(templatePath, out fingerprint))
            {
                _templateValidationState = TemplateValidationState.Invalid;
                SetTemplateValidationStatus("模板文件无法读取或已被替换，请重新选择。", "DangerBrush");
                SetTemplateRepairAvailable(false);
                return false;
            }
            _templateValidationState = TemplateValidationState.Valid;
            _validatedTemplateFingerprint = fingerprint;
            SetTemplateValidationStatus("模板安全校验通过，可以生成 PPT。", "SuccessBrush");
            SetTemplateRepairAvailable(false);
            return true;
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
            return false;
        }
        catch (Exception ex)
        {
            if (validationGeneration != _templateValidationGeneration ||
                !string.Equals(templatePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
            _templateValidationState = TemplateValidationState.Invalid;
            _validatedTemplateFingerprint = null;
            if (ex is WorkbenchApiException api)
            {
                var location = string.IsNullOrWhiteSpace(api.Failure.Location)
                    ? "template_file"
                    : api.Failure.Location;
                SetTemplateValidationStatus(
                    $"模板不可用（{api.Failure.Code}，定位：{location}）：{api.Failure.Message} {api.Failure.Suggestion}",
                    "DangerBrush");
                SetTemplateRepairAvailable(IsRepairableHyperlinkFailure(api));
            }
            else
            {
                SetTemplateValidationStatus($"模板安全检查暂不可用：{SafeFailureText(ex)}", "DangerBrush");
                SetTemplateRepairAvailable(false);
            }
            ShowMessage("所选模板无法使用，请按下方提示处理。", true);
            return false;
        }
        finally
        {
            if (validationGeneration == _templateValidationGeneration &&
                string.Equals(templatePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                UpdateActionState();
            }
        }
    }

    private void BrowseInput_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "选择输入资料",
            Filter = "支持的资料 (*.md;*.docx;*.xlsx;*.pptx)|*.md;*.docx;*.xlsx;*.pptx",
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        var info = new FileInfo(dialog.FileName);
        if (info.Length > 100L * 1024 * 1024)
        {
            ShowMessage("输入文件不能超过 100 MB。", true);
            return;
        }
        _inputPath = info.FullName;
        InputFileTextBox.Text = $"{info.Name}  ·  {FormatBytes(info.Length)}";
        AnalysisPanel.Visibility = Visibility.Collapsed;
        ResultPanel.Visibility = Visibility.Collapsed;
        UpdateActionState();
    }

    private async void BrowseTemplate_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "选择 PPTX 模板",
            Filter = "PowerPoint 模板 (*.pptx)|*.pptx",
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        var info = new FileInfo(dialog.FileName);
        if (info.Length > 50L * 1024 * 1024)
        {
            ShowMessage("模板文件不能超过 50 MB。", true);
            return;
        }
        _templatePath = info.FullName;
        _templateValidationState = TemplateValidationState.None;
        _validatedTemplateFingerprint = null;
        SetTemplateRepairAvailable(false);
        TemplateFileTextBox.Text = $"{info.Name}  ·  {FormatBytes(info.Length)}";
        await EnsureTemplateValidatedAsync();
    }

    private void RemoveTemplate_Click(object sender, RoutedEventArgs e)
    {
        if (_busy)
        {
            return;
        }
        _templateValidationGeneration++;
        _templatePath = null;
        _templateValidationState = TemplateValidationState.None;
        _validatedTemplateFingerprint = null;
        SetTemplateRepairAvailable(false);
        TemplateFileTextBox.Text = "使用默认主题";
        SetTemplateValidationStatus(null);
        UpdateActionState();
    }

    private async void RepairTemplate_Click(object sender, RoutedEventArgs e)
    {
        var sourcePath = _templatePath;
        if (_busy || !_templateRepairAvailable || string.IsNullOrWhiteSpace(sourcePath) || !File.Exists(sourcePath))
        {
            return;
        }
        var dialog = new SaveFileDialog
        {
            Title = "保存模板安全副本",
            FileName = $"{Path.GetFileNameWithoutExtension(sourcePath)}_安全副本.pptx",
            Filter = "PowerPoint 模板 (*.pptx)|*.pptx",
            OverwritePrompt = true,
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        var repairGeneration = ++_templateValidationGeneration;
        SetTemplateRepairAvailable(false);
        SetTemplateValidationStatus("正在生成不含外部超链接的安全副本...", "MutedTextBrush");
        try
        {
            await _api.SanitizeTemplateAsync(sourcePath, dialog.FileName, _lifetime.Token);
            if (repairGeneration != _templateValidationGeneration ||
                !string.Equals(sourcePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
            var info = new FileInfo(dialog.FileName);
            _templatePath = info.FullName;
            _templateValidationState = TemplateValidationState.None;
            _validatedTemplateFingerprint = null;
            TemplateFileTextBox.Text = $"{info.Name}  ·  {FormatBytes(info.Length)}";
            await EnsureTemplateValidatedAsync();
            if (_templateValidationState == TemplateValidationState.Valid)
            {
                ShowMessage("模板安全副本已保存并通过校验。", false);
            }
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            if (repairGeneration == _templateValidationGeneration &&
                string.Equals(sourcePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                _templateValidationState = TemplateValidationState.Invalid;
                SetTemplateValidationStatus($"无法生成模板安全副本：{SafeFailureText(ex)}", "DangerBrush");
                SetTemplateRepairAvailable(ex is WorkbenchApiException api && IsRepairableHyperlinkFailure(api));
                ShowMessage("模板安全副本生成失败，请按下方提示处理。", true);
            }
        }
        finally
        {
            if (repairGeneration == _templateValidationGeneration &&
                string.Equals(sourcePath, _templatePath, StringComparison.OrdinalIgnoreCase))
            {
                UpdateActionState();
            }
        }
    }

    private void AddAssets_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "选择图片资产",
            Filter = "图片 (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp",
            Multiselect = true,
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        var candidates = dialog.FileNames.Select(path => new FileInfo(path)).ToList();
        if (candidates.Any(info => info.Length > 20L * 1024 * 1024))
        {
            ShowMessage("单张图片不能超过 20 MB。", true);
            return;
        }
        var merged = _assetPaths.Concat(candidates.Select(info => info.FullName)).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if (merged.Count > 20 || merged.Sum(path => new FileInfo(path).Length) > 100L * 1024 * 1024)
        {
            ShowMessage("图片最多 20 张且总计不超过 100 MB。", true);
            return;
        }
        _assetPaths.Clear();
        foreach (var path in merged)
        {
            _assetPaths.Add(path);
        }
    }

    private void ClearAssets_Click(object sender, RoutedEventArgs e)
    {
        if (!_busy)
        {
            _assetPaths.Clear();
        }
    }

    private async void Analyze_Click(object sender, RoutedEventArgs e)
    {
        if (!File.Exists(_inputPath))
        {
            return;
        }
        SetBusy(true);
        try
        {
            var analysis = await _api.AnalyzeAsync(_inputPath, _lifetime.Token);
            AnalysisMetricsText.Text = $"{analysis.Metrics.TitleCount} 个标题 · {analysis.Metrics.MaxHeadingDepth} 级结构 · " +
                                       $"{analysis.Metrics.TableCount} 张表 · 约 {analysis.Metrics.CharacterCount} 字";
            AnalysisReasonText.Text = analysis.RecommendedReason;
            RecommendedDepthText.Text = $"推荐：{analysis.RecommendedDepth}";
            AnalysisTiersItems.ItemsSource = analysis.Tiers.Select(tier => new AnalysisTierDisplay(
                $"{tier.Depth} · {tier.MinPages}-{tier.MaxPages} 页", tier.Coverage));
            AnalysisPanel.Visibility = Visibility.Visible;
            if (CurrentTarget() == "deck")
            {
                SelectComboByText(DepthComboBox, analysis.RecommendedDepth);
            }
            ShowMessage("资料分析已完成。", false);
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "资料分析失败");
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void Generate_Click(object sender, RoutedEventArgs e) => await SubmitGenerationAsync();

    private async Task SubmitGenerationAsync()
    {
        if (!File.Exists(_inputPath) || _generatorBlocked || !_serviceReady)
        {
            UpdateActionState();
            return;
        }
        if (CurrentTarget() == "deck" && !await EnsureTemplateValidatedAsync())
        {
            return;
        }
        SetBusy(true);
        ResetResult();
        ProgressPanel.Visibility = Visibility.Visible;
        ProgressTitleText.Text = "正在创建任务";
        JobProgressBar.Value = 0;
        ProgressPercentText.Text = "0%";
        try
        {
            var target = CurrentTarget();
            var depth = target == "deck" ? CurrentComboText(DepthComboBox) : null;
            var created = await _api.GenerateAsync(
                _inputPath,
                target,
                depth,
                target == "deck" ? ComboTag(GenerateThemeComboBox, "hw_v1") : null,
                target == "deck" ? _templatePath : null,
                target == "deck" ? _assetPaths.ToList() : [],
                $"desktop-{Guid.NewGuid():N}",
                _lifetime.Token);
            _currentJob = created;
            RememberJob(created.JobId);
            ShowJob(created);
            await PollCurrentJobAsync(created.JobId, _lifetime.Token);
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "无法创建生成任务");
            SetBusy(false);
        }
    }

    private async Task PollCurrentJobAsync(string jobId, CancellationToken cancellationToken)
    {
        // A newer poll (a new submission or the startup recovery of a running
        // job) supersedes this loop: stale loops must not touch _currentJob,
        // the progress panel, or _busy after a newer job starts.
        var pollGeneration = Interlocked.Increment(ref _pollGeneration);
        var consecutiveFailures = 0;
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                using var pollTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                pollTimeout.CancelAfter(TimeSpan.FromSeconds(15));
                var job = await _api.GetJobAsync(jobId, pollTimeout.Token);
                if (Interlocked.Read(ref _pollGeneration) != pollGeneration)
                {
                    return;
                }
                _currentJob = job;
                ShowJob(job);
                consecutiveFailures = 0;
                if (job.Status is "done" or "failed" or "canceled")
                {
                    SetBusy(false);
                    try
                    {
                        await RefreshJobsAsync();
                    }
                    catch (Exception)
                    {
                        // A failed refresh must not re-enter the poll loop;
                        // the job list refreshes on the next trigger.
                    }
                    return;
                }
                await Task.Delay(700, cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
            catch (OperationCanceledException)
            {
                // Per-request poll timeout (15s): the backend may be hung, but
                // the loop must stay responsive and keep retrying with backoff.
                if (!_backend.IsProcessAlive())
                {
                    await StopPollingForDeadBackendAsync();
                    return;
                }
                consecutiveFailures++;
                ProgressTitleText.Text = "连接中断，正在恢复任务状态";
                SetServiceState(false, "连接中断，正在重试");
                await Task.Delay(Math.Min(5000, 700 * (1 << Math.Min(consecutiveFailures, 3))), cancellationToken);
            }
            catch (HttpRequestException)
            {
                if (!_backend.IsProcessAlive())
                {
                    await StopPollingForDeadBackendAsync();
                    return;
                }
                consecutiveFailures++;
                ProgressTitleText.Text = "连接中断，正在恢复任务状态";
                SetServiceState(false, "连接中断，正在重试");
                await Task.Delay(Math.Min(5000, 700 * (1 << Math.Min(consecutiveFailures, 3))), cancellationToken);
            }
            catch (Exception ex)
            {
                ShowOperationError(ex, "任务状态读取失败");
                SetBusy(false);
                return;
            }
        }
    }

    private async Task StopPollingForDeadBackendAsync()
    {
        if (await TryRecoverStoppedBackendAsync())
        {
            return;
        }

        SetBusy(false);
        ProgressTitleText.Text = "本地服务已停止";
        SetServiceState(false, "本地服务已停止，请重启工作台");
        try
        {
            await RefreshJobsAsync();
        }
        catch (Exception)
        {
            // A dead backend cannot refresh the job list; ignore.
        }
    }

    private async Task<bool> TryRecoverStoppedBackendAsync()
    {
        if (_backend.IsProcessAlive())
        {
            return true;
        }

        try
        {
            await _backendRestartGate.WaitAsync(_lifetime.Token);
            try
            {
                // Another UI action may have restarted the host while this
                // caller was waiting for the recovery gate.
                if (_backend.IsProcessAlive())
                {
                    return true;
                }
                if (_backendRestarts >= 2)
                {
                    return false;
                }

                _backendRestarts++;
                ProgressTitleText.Text = "本地服务已停止，正在自动重启…";
                SetServiceState(false, "本地服务已停止，正在自动重启…");
                var previousApi = _api;
                var restarted = await _backend.RestartAsync(_lifetime.Token);
                _backend = restarted;
                _api = new WorkbenchApiClient(restarted.CreateHttpClient());
                previousApi.Dispose();
                await InitializeServiceAsync();
                try
                {
                    await RefreshJobsAsync(allowRecovery: false);
                }
                catch (Exception)
                {
                    // Diagnostics and generation can continue; the task list
                    // will be refreshed by its next explicit navigation.
                }
                return true;
            }
            finally
            {
                _backendRestartGate.Release();
            }
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
            return false;
        }
        catch (Exception)
        {
            return false;
        }
    }

    private bool IsBackendRecoveryExhausted() =>
        !_backend.IsProcessAlive() && _backendRestarts >= 2;

    private async Task<T> ReadApiWithRecoveryAsync<T>(
        Func<WorkbenchApiClient, CancellationToken, Task<T>> read,
        bool allowRecovery = true)
    {
        if (!allowRecovery)
        {
            return await read(_api, _lifetime.Token);
        }

        try
        {
            return await read(_api, _lifetime.Token);
        }
        catch (HttpRequestException) when (!_backend.IsProcessAlive())
        {
            if (await TryRecoverStoppedBackendAsync())
            {
                return await read(_api, _lifetime.Token);
            }
            throw;
        }
        catch (TaskCanceledException) when (!_lifetime.IsCancellationRequested && !_backend.IsProcessAlive())
        {
            if (await TryRecoverStoppedBackendAsync())
            {
                return await read(_api, _lifetime.Token);
            }
            throw;
        }
    }

    private Task<DiagnosticsInfo> GetDiagnosticsWithRecoveryAsync() =>
        ReadApiWithRecoveryAsync((api, cancellationToken) => api.GetDiagnosticsAsync(cancellationToken));

    private void ShowJob(JobInfo job)
    {
        ProgressPanel.Visibility = Visibility.Visible;
        JobProgressBar.Value = Math.Clamp(job.Progress.Percent, 0, 100);
        ProgressPercentText.Text = $"{Math.Clamp(job.Progress.Percent, 0, 100)}%";
        ProgressTitleText.Text = StageLabels.Value(job.Progress.Stage);
        ProgressGeneratorText.Text = GeneratorStateText.Text;
        UpdateStageTrack(job.Progress.Stage, job.Status);
        CancelButton.Visibility = job.Status is "pending" or "running" ? Visibility.Visible : Visibility.Collapsed;
        SetServiceState(true, "本地服务已连接");

        if (job.Status is "pending" or "running")
        {
            ResultPanel.Visibility = Visibility.Collapsed;
            return;
        }
        ResultPanel.Visibility = Visibility.Visible;
        RetryButton.Visibility = Visibility.Collapsed;
        DownloadOutputButton.Visibility = Visibility.Collapsed;
        if (job.Status == "done")
        {
            ResultTitleText.Text = "生成完成";
            ResultTitleText.Foreground = (Brush)FindResource("SuccessBrush");
            ResultDetailText.Text = job.Artifact is null ? "任务已完成。" : $"{job.Artifact.Name} 已准备就绪。";
            ResultSupportText.Text = "下载后请在目标 Office 与字体环境完成最终人工复核。";
            DownloadOutputButton.Visibility = job.Artifact is null ? Visibility.Collapsed : Visibility.Visible;
        }
        else
        {
            var error = job.Error ?? new ApiFailure { Message = "任务未完成。", Suggestion = "请检查输入后重试。" };
            ResultTitleText.Text = job.Status == "canceled" ? "任务已取消" : $"生成未完成 · {error.Code}";
            ResultTitleText.Foreground = (Brush)FindResource("DangerBrush");
            ResultDetailText.Text = error.Message + Environment.NewLine + error.Suggestion;
            var location = string.IsNullOrWhiteSpace(error.Location) ? StageLabels.Value(error.Stage) : error.Location;
            ResultSupportText.Text = $"定位：{location}" +
                                     (string.IsNullOrWhiteSpace(error.SupportId) ? "" : $"  ·  支持编号：{error.SupportId}") +
                                     (error.Retryable ? "  ·  可重试" : "");
            RetryButton.Visibility = job.Status == "failed" ? Visibility.Visible : Visibility.Collapsed;
        }
        RenderAuditAssets(job);
    }

    private void RenderAuditAssets(JobInfo job)
    {
        var items = job.Assets.Select(pair => new AuditDownloadItem(
            pair.Key,
            AuditLabels.TryGetValue(pair.Key, out var label) ? label : pair.Value.Name,
            pair.Value)).ToList();
        AuditAssetsListBox.ItemsSource = items;
        var visible = items.Count > 0 ? Visibility.Visible : Visibility.Collapsed;
        AuditTitleText.Visibility = visible;
        AuditAssetsListBox.Visibility = visible;
        DownloadAuditButton.Visibility = visible;
        if (items.Count > 0)
        {
            AuditAssetsListBox.SelectedIndex = 0;
        }
    }

    private void ResetResult()
    {
        ResultPanel.Visibility = Visibility.Collapsed;
        AuditAssetsListBox.ItemsSource = null;
        ResultTitleText.Foreground = (Brush)FindResource("TextBrush");
    }

    private async void Cancel_Click(object sender, RoutedEventArgs e)
    {
        if (_currentJob is null || _currentJob.Status is not ("pending" or "running"))
        {
            return;
        }
        try
        {
            CancelButton.IsEnabled = false;
            _currentJob = await _api.CancelJobAsync(_currentJob.JobId, _lifetime.Token);
            ShowJob(_currentJob);
            SetBusy(false);
            await RefreshJobsAsync();
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "取消任务失败");
        }
        finally
        {
            CancelButton.IsEnabled = true;
        }
    }

    private async void Retry_Click(object sender, RoutedEventArgs e) => await RetrySelectedJobAsync();

    private async Task RetrySelectedJobAsync()
    {
        // Replay the SELECTED failed job's exact input instead of silently
        // re-submitting whatever is currently in the form (C-N9).
        if (_currentJob is not { Status: "failed" } ||
            !_currentJob.Assets.TryGetValue("original-input", out var originalInput))
        {
            await SubmitGenerationAsync();
            return;
        }
        try
        {
            SetBusy(true);
            var extension = Path.GetExtension(originalInput.Name);
            var tempPath = Path.Combine(Path.GetTempPath(), $"retry-{Guid.NewGuid():N}{extension}");
            await _api.DownloadAsync(originalInput.DownloadUrl, tempPath, _lifetime.Token);
            _inputPath = tempPath;
            SelectComboByTag(TargetComboBox, _currentJob.Type);
            if (_currentJob.Type == "deck")
            {
                SelectComboByText(DepthComboBox, string.IsNullOrWhiteSpace(_currentJob.Depth) ? "标准" : _currentJob.Depth!);
                SelectComboByText(GenerateThemeComboBox, _currentJob.Theme ?? "hw_v1");
            }
            InputFileTextBox.Text = $"{Path.GetFileName(tempPath)}  ·  {FormatBytes(new FileInfo(tempPath).Length)}";
            ShowMessage("已载入该任务原始输入，正在重试。", false);
            SetBusy(false);
            await SubmitGenerationAsync();
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "重试失败");
            SetBusy(false);
        }
    }

    private async void DownloadOutput_Click(object sender, RoutedEventArgs e)
    {
        if (_currentJob?.Artifact is not null)
        {
            await DownloadAssetAsync(_currentJob.Artifact);
        }
    }

    private async void DownloadAudit_Click(object sender, RoutedEventArgs e)
    {
        if (AuditAssetsListBox.SelectedItem is AuditDownloadItem item)
        {
            await DownloadAssetAsync(item.Asset);
        }
    }

    private async void AuditAssetsListBox_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (AuditAssetsListBox.SelectedItem is AuditDownloadItem item)
        {
            await DownloadAssetAsync(item.Asset);
        }
    }

    private async Task DownloadAssetAsync(DownloadAsset asset)
    {
        var extension = Path.GetExtension(asset.Name);
        var dialog = new SaveFileDialog
        {
            Title = "保存文件",
            FileName = asset.Name,
            Filter = string.IsNullOrWhiteSpace(extension)
                ? "所有文件 (*.*)|*.*"
                : $"{extension.TrimStart('.').ToUpperInvariant()} 文件 (*{extension})|*{extension}|所有文件 (*.*)|*.*",
            OverwritePrompt = true,
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        try
        {
            await _api.DownloadAsync(asset.DownloadUrl, dialog.FileName, _lifetime.Token);
            ShowMessage($"已保存：{dialog.FileName}", false);
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "下载失败");
        }
    }

    private async Task RefreshJobsAsync(bool allowRecovery = true)
    {
        SetTasksSyncStatus("正在同步本机任务…");
        var selectedJobId = (JobsDataGrid.SelectedItem as JobInfo)?.JobId;
        try
        {
            var jobs = await ReadApiWithRecoveryAsync(
                (api, cancellationToken) => api.GetJobsAsync(cancellationToken),
                allowRecovery);
            Jobs.Clear();
            foreach (var job in jobs)
            {
                Jobs.Add(job);
            }
            if (selectedJobId is not null)
            {
                JobsDataGrid.SelectedItem = Jobs.FirstOrDefault(j => j.JobId == selectedJobId);
            }
            SetTasksSyncStatus(null);
            SetServiceState(true, "本地服务已连接");
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
            SetTasksSyncStatus(null);
            throw;
        }
        catch
        {
            var recoveryExhausted = IsBackendRecoveryExhausted();
            SetServiceState(
                false,
                recoveryExhausted ? "本地服务未能恢复，请重启工作台" : "本地服务暂不可用");
            SetTasksSyncStatus(
                Jobs.Count > 0
                    ? recoveryExhausted
                        ? "任务列表暂时无法同步。当前显示的是上次加载的结果，状态可能已变化；请重新启动工作台后重试。"
                        : "任务列表暂时无法同步。当前显示的是上次加载的结果，状态可能已变化；请稍后点击“刷新”重试。"
                    : recoveryExhausted
                        ? "暂时无法读取任务列表。请重新启动工作台后重试。"
                        : "暂时无法读取任务列表。请稍后点击“刷新”重试。",
                warning: true);
            throw;
        }
    }

    private async Task RefreshTasksForDisplayAsync()
    {
        try
        {
            await RefreshJobsAsync();
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
        }
        catch (Exception)
        {
            // RefreshJobsAsync has already left an actionable page-level status.
        }
    }

    private async void RefreshTasks_Click(object sender, RoutedEventArgs e)
    {
        await RefreshTasksForDisplayAsync();
    }

    private void OpenSelectedTask_Click(object sender, RoutedEventArgs e)
    {
        if (JobsDataGrid.SelectedItem is not JobInfo job)
        {
            return;
        }
        _currentJob = job;
        SelectMainPage("generate");
        ShowJob(job);
    }

    private async void DownloadSelectedTask_Click(object sender, RoutedEventArgs e)
    {
        if (JobsDataGrid.SelectedItem is JobInfo { Artifact: not null } job)
        {
            await DownloadAssetAsync(job.Artifact);
        }
        else
        {
            ShowMessage("所选任务没有可下载产物。", true);
        }
    }

    private async void CancelSelectedTask_Click(object sender, RoutedEventArgs e)
    {
        if (JobsDataGrid.SelectedItem is not JobInfo { Status: "pending" or "running" } job)
        {
            ShowMessage("所选任务当前不能取消。", true);
            return;
        }
        try
        {
            await _api.CancelJobAsync(job.JobId, _lifetime.Token);
            await RefreshJobsAsync();
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "取消任务失败");
        }
    }

    private async void SaveGeneralSettings_Click(object sender, RoutedEventArgs e)
    {
        _settings.Appearance = AppearanceResolver.Normalize(ComboTag(AppearanceComboBox, AppearanceResolver.System));
        _settings.DefaultTarget = ComboTag(DefaultTargetComboBox, "deck");
        _settings.DefaultDepth = CurrentComboText(DefaultDepthComboBox);
        _settings.DefaultTheme = ComboTag(DefaultThemeComboBox, "hw_v1");
        await _settingsStore.SaveAsync(_settings);
        SelectComboByTag(TargetComboBox, _settings.DefaultTarget);
        SelectComboByText(DepthComboBox, _settings.DefaultDepth);
        SelectComboByTag(GenerateThemeComboBox, _settings.DefaultTheme);
        ShowMessage("常规设置已保存。", false);
    }

    private void AppearanceComboBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (AppearanceComboBox is null || !IsLoaded)
        {
            return;
        }
        ApplyAppearance(ComboTag(AppearanceComboBox, AppearanceResolver.System));
    }

    private void ApplyAppearance(string mode)
    {
        var source = new Uri(
            AppearanceResolver.PaletteResource(
                mode,
                SystemParameters.HighContrast,
                AppearanceResolver.SystemUsesLightTheme()),
            UriKind.Relative);
        var palette = Resources.MergedDictionaries.FirstOrDefault(
            dict => dict.Source?.OriginalString.Contains("Palette.") == true);
        if (palette is null)
        {
            Resources.MergedDictionaries.Insert(0, new ResourceDictionary { Source = source });
        }
        else
        {
            palette.Source = source;
        }
        BuildStageTrack();
    }

    private void SystemParameters_StaticPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(SystemParameters.HighContrast))
        {
            RefreshSystemAppearance();
        }
    }

    private void SystemEvents_UserPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
    {
        if (e.Category is UserPreferenceCategory.Color or UserPreferenceCategory.General or UserPreferenceCategory.VisualStyle)
        {
            RefreshSystemAppearance();
        }
    }

    private void RefreshSystemAppearance()
    {
        if (!IsLoaded)
        {
            return;
        }
        _ = Dispatcher.BeginInvoke(() => ApplyAppearance(_settings.Appearance));
    }

    private NgaStoredConfig ReadNgaControls(string transport)
    {
        if (!int.TryParse(NgaTimeoutTextBox.Text, out var timeout) || timeout is < 1 or > 900)
        {
            throw new InvalidDataException("超时必须是 1-900 秒之间的整数。");
        }
        var retriesText = CurrentComboText(NgaRetriesComboBox);
        if (!int.TryParse(retriesText, out var retries) || retries is < 0 or > 5)
        {
            throw new InvalidDataException("重试次数必须是 0-5。");
        }
        if (transport == "cli")
        {
            if (string.IsNullOrWhiteSpace(NgaModelTextBox.Text))
            {
                throw new InvalidDataException("模型不能为空。");
            }
            if (string.IsNullOrWhiteSpace(NgaCliPathTextBox.Text))
            {
                throw new InvalidDataException("NGA 命令行路径不能为空。");
            }
            return new NgaStoredConfig
            {
                Transport = "cli",
                CliPath = NgaCliPathTextBox.Text.Trim(),
                Model = NgaModelTextBox.Text.Trim(),
                TimeoutSeconds = timeout,
                MaxRetries = retries,
            };
        }
        if (string.IsNullOrWhiteSpace(NgaBaseUrlTextBox.Text) || string.IsNullOrWhiteSpace(NgaModelTextBox.Text))
        {
            throw new InvalidDataException("服务地址和模型不能为空。");
        }
        return new NgaStoredConfig
        {
            Transport = "http",
            BaseUrl = NgaBaseUrlTextBox.Text.Trim(),
            EndpointPath = NgaEndpointTextBox.Text.Trim(),
            Model = NgaModelTextBox.Text.Trim(),
            TimeoutSeconds = timeout,
            MaxRetries = retries,
            VerifyTls = NgaVerifyTlsCheckBox.IsChecked == true,
            CaBundlePath = string.IsNullOrWhiteSpace(NgaCaPathTextBox.Text) ? null : NgaCaPathTextBox.Text.Trim(),
            ResponseFormat = ComboTag(NgaResponseFormatComboBox, "json_object"),
            AllowInsecureHttp = NgaAllowHttpCheckBox.IsChecked == true,
        };
    }

    private string SelectedChannel() => ComboTag(GeneratorChannelComboBox, "stub");

    private async Task<GeneratorSettingsResponse> SaveGeneratorDraftAsync()
    {
        var channel = SelectedChannel();
        if (channel == "stub")
        {
            return await _api.ConfigureGeneratorAsync("stub", null, null, false, _settings.GeneratorMode, _lifetime.Token);
        }
        if (channel == "nga-cli")
        {
            var config = ReadNgaControls("cli");
            var response = await _api.ConfigureGeneratorAsync("nga", config, null, false, _settings.GeneratorMode, _lifetime.Token);
            _settings.Nga = config;
            await _settingsStore.SaveAsync(_settings);
            _ngaDraftTested = false;
            GeneratorOperationStatusText.Text = "配置已保存，启用前需要测试连接。";
            return response;
        }
        if (channel == "nga-http")
        {
            var config = ReadNgaControls("http");
            // A freshly typed token in the password box wins over a stored one.
            var token = string.IsNullOrWhiteSpace(NgaTokenPasswordBox.Password)
                ? CredentialManager.ReadNgaToken()
                : NgaTokenPasswordBox.Password;
            if (string.IsNullOrWhiteSpace(token))
            {
                throw new InvalidDataException("请先输入 NGA Token。");
            }
            // Validate on the backend first: a rejected configuration (E010)
            // must not leave a persisted credential or settings behind.
            var response = await _api.ConfigureGeneratorAsync("nga", config, token, false, _settings.GeneratorMode, _lifetime.Token);
            if (!string.IsNullOrWhiteSpace(NgaTokenPasswordBox.Password))
            {
                CredentialManager.WriteNgaToken(NgaTokenPasswordBox.Password);
                NgaTokenPasswordBox.Clear();
            }
            _settings.Nga = config;
            await _settingsStore.SaveAsync(_settings);
            _ngaDraftTested = false;
            NgaCredentialStateText.Text = "Token 已保存在 Windows 凭据管理器";
            GeneratorOperationStatusText.Text = "配置已保存，启用前需要测试连接。";
            return response;
        }
        var codexConfig = ReadCodexControls();
        var codexToken = string.IsNullOrWhiteSpace(CodexApiKeyPasswordBox.Password)
            ? CredentialManager.ReadCodexToken()
            : CodexApiKeyPasswordBox.Password;
        var codexResponse = await _api.ConfigureGeneratorAsync("codex", codexConfig, codexToken, false, _settings.GeneratorMode, _lifetime.Token);
        if (!string.IsNullOrWhiteSpace(CodexApiKeyPasswordBox.Password))
        {
            CredentialManager.WriteCodexToken(CodexApiKeyPasswordBox.Password);
            CodexApiKeyPasswordBox.Clear();
        }
        _settings.Codex = codexConfig;
        await _settingsStore.SaveAsync(_settings);
        CodexCredentialStateText.Text = CredentialManager.ReadCodexToken() is null
            ? "密钥：未保存（使用环境变量 OPENAI_API_KEY）"
            : "密钥：已保存在 Windows 凭据管理器";
        GeneratorOperationStatusText.Text = "配置已保存，启用前需要测试连接。";
        return codexResponse;
    }

    private async void SaveGenerator_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetGeneratorControlsEnabled(false);
            await SaveGeneratorDraftAsync();
        }
        catch (Exception ex)
        {
            ShowGeneratorError(ex);
        }
        finally
        {
            SetGeneratorControlsEnabled(true);
        }
    }

    private async void TestGenerator_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetGeneratorControlsEnabled(false);
            await SaveGeneratorDraftAsync();
            var response = await _api.TestGeneratorAsync(_lifetime.Token);
            _ngaDraftTested = true;
            GeneratorOperationStatusText.Text = $"连接测试成功 · {response.Connection?.LatencyMs ?? 0} ms";
        }
        catch (Exception ex)
        {
            _ngaDraftTested = false;
            ShowGeneratorError(ex);
        }
        finally
        {
            SetGeneratorControlsEnabled(true);
        }
    }

    private async void ActivateGenerator_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetGeneratorControlsEnabled(false);
            if (!_ngaDraftTested && SelectedChannel() != "stub")
            {
                throw new InvalidOperationException("请先保存配置并通过连接测试。");
            }
            var response = await _api.ActivateGeneratorAsync(_lifetime.Token);
            var name = response.Active.Name;
            _settings.NgaEnabled = name == "nga";
            await _settingsStore.SaveAsync(_settings);
            _generatorBlocked = false;
            GeneratorStateText.Text = name switch
            {
                "nga" => "生成器：NGA",
                "codex" => "生成器：opencode-go",
                _ => "生成器：stub",
            };
            GeneratorActiveStateText.Text = name switch
            {
                "nga" => $"当前生成器：NGA · 配置版本 {response.Active.Revision}",
                "codex" => $"当前生成器：opencode-go（{response.Active.Config?.Model ?? "?"} · Base URL：{response.Active.Config?.BaseUrl ?? "?"} · 密钥：{(response.Active.CredentialConfigured ? "已配置" : "未配置")}）",
                _ => "当前生成器：stub",
            };
            GeneratorOperationStatusText.Text = name switch
            {
                "nga" => "NGA 已启用。新任务将固定使用当前配置快照。",
                "codex" => "已启用 opencode-go 生成器。",
                _ => "已启用 Stub。",
            };
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowGeneratorError(ex);
        }
        finally
        {
            SetGeneratorControlsEnabled(true);
        }
    }

    private async void ActivateStub_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetGeneratorControlsEnabled(false);
            await _api.ConfigureGeneratorAsync("stub", null, null, false, _settings.GeneratorMode, _lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            _settings.NgaEnabled = false;
            await _settingsStore.SaveAsync(_settings);
            _generatorBlocked = false;
            _ngaDraftTested = false;
            GeneratorStateText.Text = "生成器：stub";
            GeneratorActiveStateText.Text = "当前生成器：stub";
            GeneratorOperationStatusText.Text = "已切换到离线 Stub。";
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowGeneratorError(ex);
        }
        finally
        {
            SetGeneratorControlsEnabled(true);
        }
    }

    private async void DeleteToken_Click(object sender, RoutedEventArgs e)
    {
        if (MessageBox.Show(this, "删除 Windows 凭据中的 NGA Token，并切换到 Stub？", "删除 Token",
                MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
        {
            return;
        }
        try
        {
            await _api.ConfigureGeneratorAsync("stub", null, null, false, _settings.GeneratorMode, _lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            CredentialManager.DeleteNgaToken();
            _settings.NgaEnabled = false;
            await _settingsStore.SaveAsync(_settings);
            NgaCredentialStateText.Text = "未保存凭据";
            GeneratorOperationStatusText.Text = "Token 已删除，当前生成器为 Stub。";
            GeneratorStateText.Text = "生成器：stub";
            GeneratorActiveStateText.Text = "当前生成器：stub";
            _generatorBlocked = false;
            _ngaDraftTested = false;
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowGeneratorError(ex);
        }
    }

    private void SetGeneratorControlsEnabled(bool enabled)
    {
        SaveGeneratorButton.IsEnabled = enabled;
        TestGeneratorButton.IsEnabled = enabled;
        ActivateGeneratorButton.IsEnabled = enabled;
    }

    private void LoadGeneratorControls(GeneratorSettingsResponse settings)
    {
        var active = settings.Active;
        // Reflect the backend's active generator in the channel selector.
        GeneratorChannelComboBox.SelectedIndex = active?.Name switch
        {
            "nga" => active.Config?.Transport == "cli" ? 1 : 2,
            "codex" => 3,
            _ => 0,
        };
        ApplyChannelVisibility();

        // Pre-fill every channel form from its saved draft/active config so a
        // switch never loses previously saved values.
        var ngaConfig = active?.Name == "nga" && active.Config is not null
            ? active.Config
            : settings.Draft?.Name == "nga" ? settings.Draft.Config : null;
        if (ngaConfig is not null)
        {
            var isCli = ngaConfig.Transport == "cli";
            NgaCliPathTextBox.Text = string.IsNullOrWhiteSpace(ngaConfig.CliPath) ? "nga" : ngaConfig.CliPath;
            NgaBaseUrlTextBox.Text = ngaConfig.BaseUrl ?? "";
            NgaEndpointTextBox.Text = string.IsNullOrWhiteSpace(ngaConfig.EndpointPath)
                ? "/v1/chat/completions"
                : ngaConfig.EndpointPath;
            NgaModelTextBox.Text = ngaConfig.Model ?? "";
            NgaTimeoutTextBox.Text = (ngaConfig.TimeoutSeconds ?? (isCli ? 300 : 120)).ToString(CultureInfo.InvariantCulture);
        }
        else
        {
            NgaCliPathTextBox.Text = string.IsNullOrWhiteSpace(_settings.Nga.CliPath) ? "nga" : _settings.Nga.CliPath;
            NgaBaseUrlTextBox.Text = _settings.Nga.BaseUrl;
            NgaEndpointTextBox.Text = string.IsNullOrWhiteSpace(_settings.Nga.EndpointPath)
                ? "/v1/chat/completions"
                : _settings.Nga.EndpointPath;
            NgaModelTextBox.Text = _settings.Nga.Model;
            NgaTimeoutTextBox.Text = _settings.Nga.TimeoutSeconds.ToString(CultureInfo.InvariantCulture);
        }
        SelectComboByText(NgaRetriesComboBox, _settings.Nga.MaxRetries.ToString(CultureInfo.InvariantCulture));
        SelectComboByTag(NgaResponseFormatComboBox, _settings.Nga.ResponseFormat);
        NgaVerifyTlsCheckBox.IsChecked = _settings.Nga.VerifyTls;
        NgaAllowHttpCheckBox.IsChecked = _settings.Nga.AllowInsecureHttp;
        NgaCaPathTextBox.Text = _settings.Nga.CaBundlePath ?? "";
        NgaCredentialStateText.Text = CredentialManager.ReadNgaToken() is null
            ? "未保存凭据"
            : "Token 已保存在 Windows 凭据管理器";

        var codexConfig = active?.Name == "codex" && active.Config is not null
            ? active.Config
            : settings.Draft?.Name == "codex" ? settings.Draft.Config : null;
        if (codexConfig is not null)
        {
            CodexBaseUrlTextBox.Text = string.IsNullOrWhiteSpace(codexConfig.BaseUrl) ? "https://opencode.ai/zen/go/v1" : codexConfig.BaseUrl;
            CodexModelTextBox.Text = codexConfig.Model ?? "";
            CodexApiModeComboBox.SelectedIndex = codexConfig.ApiMode == "chat_completions" ? 1 : 0;
            CodexTimeoutTextBox.Text = (codexConfig.TimeoutSeconds ?? 300).ToString();
            CodexReasoningComboBox.SelectedIndex = codexConfig.ReasoningEffort == "medium" ? 1 : codexConfig.ReasoningEffort == "low" ? 2 : 0;
        }
        else
        {
            CodexBaseUrlTextBox.Text = _settings.Codex.BaseUrl;
            CodexModelTextBox.Text = _settings.Codex.Model;
            CodexApiModeComboBox.SelectedIndex = _settings.Codex.ApiMode == "chat_completions" ? 1 : 0;
            CodexTimeoutTextBox.Text = _settings.Codex.TimeoutSeconds.ToString();
            CodexReasoningComboBox.SelectedIndex = _settings.Codex.ReasoningEffort == "medium" ? 1 : _settings.Codex.ReasoningEffort == "low" ? 2 : 0;
        }
        CodexCredentialStateText.Text = CredentialManager.ReadCodexToken() is null
            ? "密钥：未保存（使用环境变量 OPENAI_API_KEY）"
            : "密钥：已保存在 Windows 凭据管理器";

        if (active is { Name: "codex" })
        {
            GeneratorActiveStateText.Text =
                $"当前生成器：opencode-go（{active.Config?.Model ?? "?"} · Base URL：{active.Config?.BaseUrl ?? "?"} · 密钥：{(active.CredentialConfigured ? "已配置" : "未配置")}）";
        }
        else
        {
            GeneratorActiveStateText.Text = active?.Name switch
            {
                "nga" => $"当前生成器：NGA（{active.Config?.Model ?? "?"}）",
                "codex" => "当前生成器：opencode-go",
                _ => "当前生成器：stub",
            };
        }
        UpdateDeckOptionsVisibility();
    }

    private CodexStoredConfig ReadCodexControls()
    {
        if (string.IsNullOrWhiteSpace(CodexBaseUrlTextBox.Text) || string.IsNullOrWhiteSpace(CodexModelTextBox.Text))
        {
            throw new InvalidDataException("服务地址和模型不能为空。");
        }
        if (!int.TryParse(CodexTimeoutTextBox.Text, out var timeout) || timeout is < 1 or > 1800)
        {
            throw new InvalidDataException("超时必须是 1-1800 秒。");
        }
        return new CodexStoredConfig
        {
            BaseUrl = CodexBaseUrlTextBox.Text.Trim(),
            Model = CodexModelTextBox.Text.Trim(),
            ApiMode = ComboTag(CodexApiModeComboBox, "responses"),
            TimeoutSeconds = timeout,
            ReasoningEffort = ComboTag(CodexReasoningComboBox, "high"),
        };
    }

    private void ShowGeneratorError(Exception exception)
    {
        var message = SafeFailureText(exception);
        GeneratorOperationStatusText.Text = message;
        ShowMessage(message, true);
    }

    private void BrowseCa_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "选择自定义 CA 文件",
            Filter = "证书文件 (*.pem;*.crt;*.cer)|*.pem;*.crt;*.cer|所有文件 (*.*)|*.*",
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) == true)
        {
            NgaCaPathTextBox.Text = dialog.FileName;
        }
    }

    private void OpenJobsFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(JobsPathTextBox.Text);
        Process.Start(new ProcessStartInfo(JobsPathTextBox.Text) { UseShellExecute = true });
    }

    private async void RefreshDiagnostics_Click(object sender, RoutedEventArgs e) => await RefreshDiagnosticsAsync();

    private async Task RefreshDiagnosticsAsync()
    {
        SetDiagnosticsStatus("正在读取本机运行状态…");
        try
        {
            var info = await GetDiagnosticsWithRecoveryAsync();
            DiagnosticAppVersion.Text = info.Application.Version;
            DiagnosticApiVersion.Text = $"API {info.Application.ApiVersion} · DeckIR {info.Application.DeckIrVersion}";
            DiagnosticGenerator.Text = $"{info.Generator.Name} · 修订 {info.Generator.Revision}";
            DiagnosticQueue.Text = $"{info.Runner.QueueDepth} / {info.Runner.QueueCapacity} · 工作线程{(info.Runner.WorkerAlive ? "正常" : "异常")}";
            DiagnosticJobs.Text = $"共 {GetCount(info.Jobs, "total")} · 运行 {GetCount(info.Jobs, "running")} · 完成 {GetCount(info.Jobs, "done")} · 失败 {GetCount(info.Jobs, "failed")}";
            DiagnosticDisk.Text = $"{FormatBytes(info.Storage.FreeBytes)} 可用";
            DiagnosticGraphviz.Text = info.Graphviz.Available
                ? $"可用 · {info.Graphviz.Source} · {info.Graphviz.Version ?? "版本未知"}"
                : "未安装 · 使用确定性降级布局";
            DiagnosticNga.Text = info.Generator.Name == "nga"
                ? $"已启用 · 修订 {info.Generator.Revision}"
                : _generatorBlocked ? "配置异常 · 生成已阻断"
                : info.Generator.Name == "codex" ? "未启用 · 当前使用 opencode-go"
                : "未启用";
            _lastDiagnosticsUpdatedAt = DateTime.Now;
            DiagnosticUpdatedText.Text = $"更新时间：{_lastDiagnosticsUpdatedAt:yyyy-MM-dd HH:mm:ss}";
            SetDiagnosticsStatus(null);
            SetServiceState(true, "本地服务已连接");
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
            SetDiagnosticsStatus(null);
        }
        catch (Exception)
        {
            var recoveryExhausted = IsBackendRecoveryExhausted();
            SetServiceState(
                false,
                recoveryExhausted ? "本地服务未能恢复，请重启工作台" : "本地服务暂不可用");
            SetDiagnosticsStatus(
                recoveryExhausted
                    ? _lastDiagnosticsUpdatedAt is null
                        ? "本地服务未能恢复。请重新启动工作台后重试。"
                        : "本地服务未能恢复。已保留上次成功的诊断结果；请重新启动工作台后重试。"
                    : "暂时无法读取诊断信息。服务恢复后，请点击“刷新诊断”重试。",
                warning: true);
            if (_lastDiagnosticsUpdatedAt is null)
            {
                DiagnosticAppVersion.Text = "暂不可用";
                DiagnosticApiVersion.Text = "暂不可用";
                DiagnosticGenerator.Text = "暂不可用";
                DiagnosticQueue.Text = "暂不可用";
                DiagnosticJobs.Text = "暂不可用";
                DiagnosticDisk.Text = "暂不可用";
                DiagnosticGraphviz.Text = "暂不可用";
                DiagnosticNga.Text = "暂不可用";
                DiagnosticUpdatedText.Text = "尚未读取到诊断信息。";
            }
            else
            {
                DiagnosticUpdatedText.Text = $"上次成功更新：{_lastDiagnosticsUpdatedAt:yyyy-MM-dd HH:mm:ss}";
            }
        }
    }

    private static int GetCount(Dictionary<string, int> counts, string key) =>
        counts.TryGetValue(key, out var value) ? value : 0;

    private void RememberJob(string jobId)
    {
        _settings.RecentJobIds.RemoveAll(value => string.Equals(value, jobId, StringComparison.Ordinal));
        _settings.RecentJobIds.Insert(0, jobId);
        _ = _settingsStore.SaveAsync(_settings);
    }

    private void TargetComboBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateDeckOptionsVisibility();
        if (GenerateButton is not null)
        {
            UpdateActionState();
        }
    }

    private void AdvancedToggle_Click(object sender, RoutedEventArgs e) => UpdateDeckOptionsVisibility();

    private void AdvancedToggle_Checked(object sender, RoutedEventArgs e) => UpdateDeckOptionsVisibility();

    private void UpdateDeckOptionsVisibility()
    {
        if (DeckOptionsPanel is null || DepthPanel is null || AdvancedToggle is null)
        {
            return;
        }
        // 简洁/高级渐进披露：高级选项只在选中 PPT 且用户展开时显示；不改变任务请求格式
        var deckSelected = CurrentTarget() == "deck";
        DeckOptionsPanel.Visibility = deckSelected && AdvancedToggle.IsChecked == true
            ? Visibility.Visible
            : Visibility.Collapsed;
        DepthPanel.Visibility = deckSelected ? Visibility.Visible : Visibility.Collapsed;
    }

    private string CurrentTarget() => ComboTag(TargetComboBox, "deck");

    private static string ComboTag(ComboBox comboBox, string fallback) =>
        comboBox.SelectedItem is ComboBoxItem item && item.Tag is string tag ? tag : fallback;

    private static string CurrentComboText(ComboBox comboBox) =>
        comboBox.SelectedItem is ComboBoxItem item ? item.Content?.ToString() ?? "" : comboBox.Text;

    private static void SelectComboByTag(ComboBox comboBox, string tag)
    {
        foreach (var candidate in comboBox.Items.OfType<ComboBoxItem>())
        {
            if (string.Equals(candidate.Tag?.ToString(), tag, StringComparison.Ordinal))
            {
                comboBox.SelectedItem = candidate;
                return;
            }
        }
        comboBox.SelectedIndex = 0;
    }

    private static void SelectComboByText(ComboBox comboBox, string text)
    {
        foreach (var candidate in comboBox.Items.OfType<ComboBoxItem>())
        {
            if (string.Equals(candidate.Content?.ToString(), text, StringComparison.Ordinal))
            {
                comboBox.SelectedItem = candidate;
                return;
            }
        }
        comboBox.SelectedIndex = 0;
    }

    private void ShowOperationError(Exception exception, string title)
    {
        if (exception is WorkbenchApiException api)
        {
            var location = string.IsNullOrWhiteSpace(api.Failure.Location)
                ? StageLabels.Value(api.Failure.Stage)
                : api.Failure.Location;
            ShowMessage($"{title} · {api.Failure.Code}\n{api.Failure.Message}\n{api.Failure.Suggestion}\n定位：{location}", true);
            return;
        }
        ShowMessage($"{title}：{SafeFailureText(exception)}", true);
    }

    private static string SafeFailureText(Exception exception)
    {
        if (exception is WorkbenchApiException api)
        {
            return $"{api.Failure.Code} · {api.Failure.Message} {api.Failure.Suggestion}";
        }
        if (exception is HttpRequestException)
        {
            return "本地服务暂不可用，请稍后重试。";
        }
        if (exception is TaskCanceledException)
        {
            return "本地服务响应超时，请稍后重试。";
        }
        var value = exception.Message.Replace('\r', ' ').Replace('\n', ' ').Trim();
        return value.Length <= 500 ? value : value[..500];
    }

    private void ShowMessage(string message, bool error)
    {
        TopbarStatusText.Text = message.Replace('\r', ' ').Replace('\n', ' ');
        if (error)
        {
            System.Media.SystemSounds.Exclamation.Play();
        }
    }

    private static string FormatBytes(long value)
    {
        if (value <= 0)
        {
            return "0 KB";
        }
        if (value >= 1024L * 1024 * 1024)
        {
            return $"{value / 1024d / 1024 / 1024:0.0} GB";
        }
        if (value >= 1024L * 1024)
        {
            return $"{value / 1024d / 1024:0.0} MB";
        }
        return $"{Math.Max(1, value / 1024d):0} KB";
    }

    private void GenerateNavButton_Click(object sender, RoutedEventArgs e) => SelectMainPage("generate");
    private async void TasksNavButton_Click(object sender, RoutedEventArgs e)
    {
        SelectMainPage("tasks");
        await RefreshTasksForDisplayAsync();
    }
    private void SettingsNavButton_Click(object sender, RoutedEventArgs e) => SelectMainPage("settings");
    private async void DiagnosticsNavButton_Click(object sender, RoutedEventArgs e)
    {
        SelectMainPage("diagnostics");
        await RefreshDiagnosticsAsync();
    }
    private void AboutNavButton_Click(object sender, RoutedEventArgs e) => SelectMainPage("about");

    private void SelectMainPage(string page)
    {
        GeneratePage.Visibility = page == "generate" ? Visibility.Visible : Visibility.Collapsed;
        TasksPage.Visibility = page == "tasks" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = page == "settings" ? Visibility.Visible : Visibility.Collapsed;
        DiagnosticsPage.Visibility = page == "diagnostics" ? Visibility.Visible : Visibility.Collapsed;
        AboutPage.Visibility = page == "about" ? Visibility.Visible : Visibility.Collapsed;
        GenerateNavButton.Tag = page == "generate" ? "selected" : null;
        TasksNavButton.Tag = page == "tasks" ? "selected" : null;
        SettingsNavButton.Tag = page == "settings" ? "selected" : null;
        DiagnosticsNavButton.Tag = page == "diagnostics" ? "selected" : null;
        AboutNavButton.Tag = page == "about" ? "selected" : null;
        TopbarTitleText.Text = page switch
        {
            "generate" => "生成",
            "tasks" => "任务",
            "settings" => "设置",
            "diagnostics" => "诊断",
            "about" => "关于",
            _ => "文档生成工作台",
        };
    }

    private void GeneralSettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("general");
    private void GeneratorSettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("generator");
    private void StorageSettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("storage");
    private void PrivacySettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("privacy");
    private void SettingsAbout_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("about");

    private void SelectSettingsPage(string page)
    {
        GeneralSettingsPanel.Visibility = page == "general" ? Visibility.Visible : Visibility.Collapsed;
        GeneratorSettingsPanel.Visibility = page == "generator" ? Visibility.Visible : Visibility.Collapsed;
        StorageSettingsPanel.Visibility = page == "storage" ? Visibility.Visible : Visibility.Collapsed;
        PrivacySettingsPanel.Visibility = page == "privacy" ? Visibility.Visible : Visibility.Collapsed;
        SettingsAboutPanel.Visibility = page == "about" ? Visibility.Visible : Visibility.Collapsed;
        GeneralSettingsButton.Tag = page == "general" ? "selected" : null;
        GeneratorSettingsButton.Tag = page == "generator" ? "selected" : null;
        StorageSettingsButton.Tag = page == "storage" ? "selected" : null;
        PrivacySettingsButton.Tag = page == "privacy" ? "selected" : null;
        SettingsAboutButton.Tag = page == "about" ? "selected" : null;
    }

    private sealed record AnalysisTierDisplay(string DepthRange, string Coverage);
    private sealed record AuditDownloadItem(string Key, string Label, DownloadAsset Asset);
}
