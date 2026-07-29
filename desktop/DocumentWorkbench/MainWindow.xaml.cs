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
    };

    private readonly BackendProcessHost _backend;
    private readonly SettingsStore _settingsStore;
    private readonly WorkbenchApiClient _api;
    private readonly CancellationTokenSource _lifetime = new();
    private WorkbenchSettings _settings = new();
    private string? _inputPath;
    private string? _templatePath;
    private readonly ObservableCollection<string> _assetPaths = [];
    private JobInfo? _currentJob;
    private bool _serviceReady;
    private bool _generatorBlocked;
    private bool _busy;
    private bool _ngaDraftTested;

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
        _lifetime.Cancel();
        _api.Dispose();
    }

    private async Task InitializeServiceAsync()
    {
        var version = await _api.GetVersionAsync(_lifetime.Token);
        if (version.ApiVersion != "1.0" || version.DeckIrVersion != "2.0")
        {
            _generatorBlocked = true;
            SetServiceState(false, "版本不兼容");
            GenerateGuardText.Text = $"需要 API 1.0 / DeckIR 2.0，当前为 {version.ApiVersion} / {version.DeckIrVersion}";
            return;
        }

        SidebarVersionText.Text = $"本地服务 v{version.AppVersion}";
        _serviceReady = true;
        SetServiceState(true, "本地服务已连接");

        if (!_settings.NgaEnabled)
        {
            await _api.ConfigureGeneratorAsync("stub", null, null, false, _lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            _generatorBlocked = false;
            GeneratorStateText.Text = "生成器：stub";
            NgaActiveStateText.Text = "当前生成器：stub";
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
            await _api.ConfigureGeneratorAsync("nga", _settings.Nga, token, false, _lifetime.Token);
            var tested = await _api.TestGeneratorAsync(_lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            _ngaDraftTested = true;
            _generatorBlocked = false;
            GeneratorStateText.Text = "生成器：NGA";
            NgaActiveStateText.Text = "当前生成器：NGA";
            NgaOperationStatusText.Text = $"已恢复连接，延迟 {tested.Connection?.LatencyMs ?? 0} ms";
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
        NgaActiveStateText.Text = "当前生成器：NGA 未就绪";
        NgaOperationStatusText.Text = message;
        GenerateGuardText.Text = message;
    }

    private void ApplySettingsToControls()
    {
        SelectComboByTag(DefaultTargetComboBox, _settings.DefaultTarget);
        SelectComboByText(DefaultDepthComboBox, _settings.DefaultDepth);
        SelectComboByTag(TargetComboBox, _settings.DefaultTarget);
        SelectComboByText(DepthComboBox, _settings.DefaultDepth);

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
        UpdateDeckOptionsVisibility();
    }

    private void SetServiceState(bool connected, string text)
    {
        ServiceDot.Fill = connected
            ? (Brush)FindResource("SuccessBrush")
            : (Brush)FindResource("DangerBrush");
        ServiceStateText.Text = text;
        TopbarStatusText.Text = text;
    }

    private void UpdateActionState()
    {
        var available = _serviceReady && !_generatorBlocked && !_busy && File.Exists(_inputPath);
        AnalyzeButton.IsEnabled = available;
        GenerateButton.IsEnabled = available;
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

    private void BrowseTemplate_Click(object sender, RoutedEventArgs e)
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
        TemplateFileTextBox.Text = $"{info.Name}  ·  {FormatBytes(info.Length)}";
    }

    private void RemoveTemplate_Click(object sender, RoutedEventArgs e)
    {
        if (_busy)
        {
            return;
        }
        _templatePath = null;
        TemplateFileTextBox.Text = "使用默认主题";
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
        var consecutiveFailures = 0;
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var job = await _api.GetJobAsync(jobId, cancellationToken);
                _currentJob = job;
                ShowJob(job);
                consecutiveFailures = 0;
                if (job.Status is "done" or "failed" or "canceled")
                {
                    SetBusy(false);
                    await RefreshJobsAsync();
                    return;
                }
                await Task.Delay(700, cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
            catch (HttpRequestException)
            {
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

    private void ShowJob(JobInfo job)
    {
        ProgressPanel.Visibility = Visibility.Visible;
        JobProgressBar.Value = Math.Clamp(job.Progress.Percent, 0, 100);
        ProgressPercentText.Text = $"{Math.Clamp(job.Progress.Percent, 0, 100)}%";
        ProgressTitleText.Text = StageLabels.Value(job.Progress.Stage);
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

    private async void Retry_Click(object sender, RoutedEventArgs e) => await SubmitGenerationAsync();

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

    private async Task RefreshJobsAsync()
    {
        var jobs = await _api.GetJobsAsync(_lifetime.Token);
        Jobs.Clear();
        foreach (var job in jobs)
        {
            Jobs.Add(job);
        }
    }

    private async void RefreshTasks_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await RefreshJobsAsync();
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "任务列表刷新失败");
        }
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
        _settings.DefaultTarget = ComboTag(DefaultTargetComboBox, "deck");
        _settings.DefaultDepth = CurrentComboText(DefaultDepthComboBox);
        await _settingsStore.SaveAsync(_settings);
        SelectComboByTag(TargetComboBox, _settings.DefaultTarget);
        SelectComboByText(DepthComboBox, _settings.DefaultDepth);
        ShowMessage("常规设置已保存。", false);
    }

    private NgaStoredConfig ReadNgaControls()
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
        if (string.IsNullOrWhiteSpace(NgaBaseUrlTextBox.Text) || string.IsNullOrWhiteSpace(NgaModelTextBox.Text))
        {
            throw new InvalidDataException("服务地址和模型不能为空。");
        }
        return new NgaStoredConfig
        {
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

    private async Task<GeneratorSettingsResponse> SaveNgaDraftAsync()
    {
        var config = ReadNgaControls();
        if (!string.IsNullOrWhiteSpace(NgaTokenPasswordBox.Password))
        {
            CredentialManager.WriteNgaToken(NgaTokenPasswordBox.Password);
            NgaTokenPasswordBox.Clear();
        }
        var token = CredentialManager.ReadNgaToken();
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new InvalidDataException("请先输入 NGA Token。");
        }
        _settings.Nga = config;
        await _settingsStore.SaveAsync(_settings);
        _ngaDraftTested = false;
        var response = await _api.ConfigureGeneratorAsync("nga", config, token, false, _lifetime.Token);
        NgaCredentialStateText.Text = "Token 已保存在 Windows 凭据管理器";
        NgaOperationStatusText.Text = "配置已保存，启用前需要测试连接。";
        return response;
    }

    private async void SaveNga_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetNgaControlsEnabled(false);
            await SaveNgaDraftAsync();
        }
        catch (Exception ex)
        {
            ShowNgaError(ex);
        }
        finally
        {
            SetNgaControlsEnabled(true);
        }
    }

    private async void TestNga_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetNgaControlsEnabled(false);
            await SaveNgaDraftAsync();
            var response = await _api.TestGeneratorAsync(_lifetime.Token);
            _ngaDraftTested = true;
            NgaOperationStatusText.Text = $"连接测试成功 · {response.Connection?.LatencyMs ?? 0} ms";
        }
        catch (Exception ex)
        {
            _ngaDraftTested = false;
            ShowNgaError(ex);
        }
        finally
        {
            SetNgaControlsEnabled(true);
        }
    }

    private async void ActivateNga_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetNgaControlsEnabled(false);
            if (!_ngaDraftTested)
            {
                throw new InvalidOperationException("请先保存配置并通过连接测试。");
            }
            var response = await _api.ActivateGeneratorAsync(_lifetime.Token);
            _settings.NgaEnabled = true;
            await _settingsStore.SaveAsync(_settings);
            _generatorBlocked = false;
            GeneratorStateText.Text = "生成器：NGA";
            NgaActiveStateText.Text = $"当前生成器：NGA · 配置版本 {response.Active.Revision}";
            NgaOperationStatusText.Text = "NGA 已启用。新任务将固定使用当前配置快照。";
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowNgaError(ex);
        }
        finally
        {
            SetNgaControlsEnabled(true);
        }
    }

    private async void ActivateStub_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetNgaControlsEnabled(false);
            await _api.ConfigureGeneratorAsync("stub", null, null, false, _lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            _settings.NgaEnabled = false;
            await _settingsStore.SaveAsync(_settings);
            _generatorBlocked = false;
            _ngaDraftTested = false;
            GeneratorStateText.Text = "生成器：stub";
            NgaActiveStateText.Text = "当前生成器：stub";
            NgaOperationStatusText.Text = "已切换到离线 Stub。";
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowNgaError(ex);
        }
        finally
        {
            SetNgaControlsEnabled(true);
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
            await _api.ConfigureGeneratorAsync("stub", null, null, false, _lifetime.Token);
            await _api.ActivateGeneratorAsync(_lifetime.Token);
            CredentialManager.DeleteNgaToken();
            _settings.NgaEnabled = false;
            await _settingsStore.SaveAsync(_settings);
            NgaCredentialStateText.Text = "未保存凭据";
            NgaOperationStatusText.Text = "Token 已删除，当前生成器为 Stub。";
            GeneratorStateText.Text = "生成器：stub";
            NgaActiveStateText.Text = "当前生成器：stub";
            _generatorBlocked = false;
            _ngaDraftTested = false;
            UpdateActionState();
        }
        catch (Exception ex)
        {
            ShowNgaError(ex);
        }
    }

    private void SetNgaControlsEnabled(bool enabled)
    {
        SaveNgaButton.IsEnabled = enabled;
        TestNgaButton.IsEnabled = enabled;
        ActivateNgaButton.IsEnabled = enabled;
    }

    private void ShowNgaError(Exception exception)
    {
        var message = SafeFailureText(exception);
        NgaOperationStatusText.Text = message;
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
        try
        {
            var info = await _api.GetDiagnosticsAsync(_lifetime.Token);
            var generator = await _api.GetGeneratorSettingsAsync(_lifetime.Token);
            DiagnosticAppVersion.Text = info.Application.Version;
            DiagnosticApiVersion.Text = $"API {info.Application.ApiVersion} · DeckIR {info.Application.DeckIrVersion}";
            DiagnosticGenerator.Text = $"{info.Generator.Name} · 修订 {info.Generator.Revision}";
            DiagnosticQueue.Text = $"{info.Runner.QueueDepth} / {info.Runner.QueueCapacity} · 工作线程{(info.Runner.WorkerAlive ? "正常" : "异常")}";
            DiagnosticJobs.Text = $"共 {GetCount(info.Jobs, "total")} · 运行 {GetCount(info.Jobs, "running")} · 完成 {GetCount(info.Jobs, "done")} · 失败 {GetCount(info.Jobs, "failed")}";
            DiagnosticDisk.Text = $"{FormatBytes(info.Storage.FreeBytes)} 可用";
            DiagnosticGraphviz.Text = info.Graphviz.Available
                ? $"可用 · {info.Graphviz.Source} · {info.Graphviz.Version ?? "版本未知"}"
                : "未安装 · 使用确定性降级布局";
            DiagnosticNga.Text = generator.Active.Name == "nga"
                ? $"已启用 · 修订 {generator.Active.Revision}"
                : _generatorBlocked ? "配置异常 · 生成已阻断" : "未启用";
            DiagnosticUpdatedText.Text = $"更新时间：{DateTime.Now:yyyy-MM-dd HH:mm:ss}";
        }
        catch (Exception ex)
        {
            ShowOperationError(ex, "诊断刷新失败");
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

    private void TargetComboBox_SelectionChanged(object sender, SelectionChangedEventArgs e) => UpdateDeckOptionsVisibility();

    private void UpdateDeckOptionsVisibility()
    {
        if (DeckOptionsPanel is null || DepthPanel is null)
        {
            return;
        }
        var visibility = CurrentTarget() == "deck" ? Visibility.Visible : Visibility.Collapsed;
        DeckOptionsPanel.Visibility = visibility;
        DepthPanel.Visibility = visibility;
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
        await RefreshJobsAsync();
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
    private void NgaSettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("nga");
    private void StorageSettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("storage");
    private void PrivacySettings_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("privacy");
    private void SettingsAbout_Click(object sender, RoutedEventArgs e) => SelectSettingsPage("about");

    private void SelectSettingsPage(string page)
    {
        GeneralSettingsPanel.Visibility = page == "general" ? Visibility.Visible : Visibility.Collapsed;
        NgaSettingsPanel.Visibility = page == "nga" ? Visibility.Visible : Visibility.Collapsed;
        StorageSettingsPanel.Visibility = page == "storage" ? Visibility.Visible : Visibility.Collapsed;
        PrivacySettingsPanel.Visibility = page == "privacy" ? Visibility.Visible : Visibility.Collapsed;
        SettingsAboutPanel.Visibility = page == "about" ? Visibility.Visible : Visibility.Collapsed;
        GeneralSettingsButton.Tag = page == "general" ? "selected" : null;
        NgaSettingsButton.Tag = page == "nga" ? "selected" : null;
        StorageSettingsButton.Tag = page == "storage" ? "selected" : null;
        PrivacySettingsButton.Tag = page == "privacy" ? "selected" : null;
        SettingsAboutButton.Tag = page == "about" ? "selected" : null;
    }

    private sealed record AnalysisTierDisplay(string DepthRange, string Coverage);
    private sealed record AuditDownloadItem(string Key, string Label, DownloadAsset Asset);
}
