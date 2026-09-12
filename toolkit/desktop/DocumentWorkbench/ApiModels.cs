using System.Text.Json.Serialization;

namespace DocumentWorkbench;

public sealed class ApiVersionInfo
{
    [JsonPropertyName("app_version")]
    public string AppVersion { get; set; } = "";

    [JsonPropertyName("api_version")]
    public string ApiVersion { get; set; } = "";

    [JsonPropertyName("deck_ir_version")]
    public string DeckIrVersion { get; set; } = "";
}

public sealed class AnalysisInfo
{
    [JsonPropertyName("recommended_depth")]
    public string RecommendedDepth { get; set; } = "";

    [JsonPropertyName("recommended_reason")]
    public string RecommendedReason { get; set; } = "";

    [JsonPropertyName("metrics")]
    public AnalysisMetrics Metrics { get; set; } = new();

    [JsonPropertyName("tiers")]
    public List<AnalysisTier> Tiers { get; set; } = [];
}

public sealed class TemplateValidationInfo
{
    [JsonPropertyName("valid")]
    public bool Valid { get; set; }
}

public sealed class AnalysisMetrics
{
    [JsonPropertyName("title_count")]
    public int TitleCount { get; set; }

    [JsonPropertyName("max_heading_depth")]
    public int MaxHeadingDepth { get; set; }

    [JsonPropertyName("table_count")]
    public int TableCount { get; set; }

    [JsonPropertyName("character_count")]
    public int CharacterCount { get; set; }
}

public sealed class AnalysisTier
{
    [JsonPropertyName("depth")]
    public string Depth { get; set; } = "";

    [JsonPropertyName("min_pages")]
    public int MinPages { get; set; }

    [JsonPropertyName("max_pages")]
    public int MaxPages { get; set; }

    [JsonPropertyName("coverage")]
    public string Coverage { get; set; } = "";
}

public sealed class JobListResponse
{
    [JsonPropertyName("jobs")]
    public List<JobInfo> Jobs { get; set; } = [];
}

public sealed class JobInfo
{
    [JsonPropertyName("job_id")]
    public string JobId { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("depth")]
    public string? Depth { get; set; }

    [JsonPropertyName("theme")]
    public string? Theme { get; set; }

    [JsonPropertyName("generator")]
    public GeneratorState Generator { get; set; } = new();

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("progress")]
    public JobProgress Progress { get; set; } = new();

    [JsonPropertyName("artifact")]
    public DownloadAsset? Artifact { get; set; }

    [JsonPropertyName("assets")]
    public Dictionary<string, DownloadAsset> Assets { get; set; } = new(StringComparer.Ordinal);

    [JsonPropertyName("error")]
    public ApiFailure? Error { get; set; }

    [JsonIgnore]
    public string DisplayId => JobId.Length > 12 ? JobId[..12] : JobId;

    [JsonIgnore]
    public string DisplayType => Type == "deck" ? "PPT" : "Word";

    [JsonIgnore]
    public string DisplayStatus => Status switch
    {
        "pending" => "排队中",
        "running" => "运行中",
        "done" => "已完成",
        "failed" => "失败",
        "canceled" => "已取消",
        _ => Status,
    };

    [JsonIgnore]
    public string DisplayStage => StageLabels.Value(Progress.Stage);

    [JsonIgnore]
    public string DisplayGenerator => $"{(Generator.Name == "nga" ? "NGA" : "Stub")} r{Generator.Revision}";
}

public sealed class JobProgress
{
    [JsonPropertyName("stage")]
    public string Stage { get; set; } = "queued";

    [JsonPropertyName("percent")]
    public int Percent { get; set; }
}

public sealed class DownloadAsset
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("download_url")]
    public string DownloadUrl { get; set; } = "";
}

public sealed class ApiFailure
{
    [JsonPropertyName("code")]
    public string Code { get; set; } = "E001";

    [JsonPropertyName("stage")]
    public string Stage { get; set; } = "unknown";

    [JsonPropertyName("retryable")]
    public bool Retryable { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = "请求未完成。";

    [JsonPropertyName("suggestion")]
    public string Suggestion { get; set; } = "请检查输入后重试。";

    [JsonPropertyName("support_id")]
    public string? SupportId { get; set; }

    [JsonPropertyName("loc")]
    public string? Location { get; set; }
}

public sealed class ApiErrorResponse
{
    [JsonPropertyName("error")]
    public ApiFailure Error { get; set; } = new();
}

public sealed class GeneratorSettingsResponse
{
    [JsonPropertyName("settings_version")]
    public string SettingsVersion { get; set; } = "";

    [JsonPropertyName("active")]
    public GeneratorState Active { get; set; } = new();

    [JsonPropertyName("draft")]
    public GeneratorState Draft { get; set; } = new();

    [JsonPropertyName("connection")]
    public GeneratorConnection? Connection { get; set; }
}

public sealed class GeneratorState
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "stub";

    [JsonPropertyName("revision")]
    public int Revision { get; set; }

    [JsonPropertyName("mode")]
    public string Mode { get; set; } = "auto";

    [JsonPropertyName("fallback")]
    public bool Fallback { get; set; }

    [JsonPropertyName("credential_configured")]
    public bool CredentialConfigured { get; set; }

    [JsonPropertyName("tested")]
    public bool Tested { get; set; }

    [JsonPropertyName("latency_ms")]
    public int? LatencyMs { get; set; }

    [JsonPropertyName("config")]
    public GeneratorConfigDto? Config { get; set; }
}

/// <summary>Non-sensitive subset of the active/draft generator configuration
/// (never includes credentials).</summary>
public sealed class GeneratorConfigDto
{
    [JsonPropertyName("base_url")]
    public string? BaseUrl { get; set; }

    [JsonPropertyName("model")]
    public string? Model { get; set; }

    [JsonPropertyName("api_mode")]
    public string? ApiMode { get; set; }

    [JsonPropertyName("transport")]
    public string? Transport { get; set; }

    [JsonPropertyName("cli_path")]
    public string? CliPath { get; set; }

    [JsonPropertyName("endpoint_path")]
    public string? EndpointPath { get; set; }

    [JsonPropertyName("timeout_seconds")]
    public int? TimeoutSeconds { get; set; }

    [JsonPropertyName("reasoning_effort")]
    public string? ReasoningEffort { get; set; }
}

public sealed class GeneratorConnection
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("latency_ms")]
    public int LatencyMs { get; set; }
}

public sealed class DiagnosticsInfo
{
    [JsonPropertyName("application")]
    public DiagnosticsApplication Application { get; set; } = new();

    [JsonPropertyName("generator")]
    public GeneratorState Generator { get; set; } = new();

    [JsonPropertyName("jobs")]
    public Dictionary<string, int> Jobs { get; set; } = new();

    [JsonPropertyName("runner")]
    public DiagnosticsRunner Runner { get; set; } = new();

    [JsonPropertyName("storage")]
    public DiagnosticsStorage Storage { get; set; } = new();

    [JsonPropertyName("graphviz")]
    public DiagnosticsGraphviz Graphviz { get; set; } = new();
}

public sealed class DiagnosticsApplication
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("api_version")]
    public string ApiVersion { get; set; } = "";

    [JsonPropertyName("deck_ir_version")]
    public string DeckIrVersion { get; set; } = "";
}

public sealed class DiagnosticsRunner
{
    [JsonPropertyName("worker_alive")]
    public bool WorkerAlive { get; set; }

    [JsonPropertyName("queue_depth")]
    public int QueueDepth { get; set; }

    [JsonPropertyName("queue_capacity")]
    public int QueueCapacity { get; set; }
}

public sealed class DiagnosticsStorage
{
    [JsonPropertyName("free_bytes")]
    public long FreeBytes { get; set; }

    [JsonPropertyName("minimum_free_bytes")]
    public long MinimumFreeBytes { get; set; }
}

public sealed class DiagnosticsGraphviz
{
    [JsonPropertyName("available")]
    public bool Available { get; set; }

    [JsonPropertyName("source")]
    public string Source { get; set; } = "missing";

    [JsonPropertyName("version")]
    public string? Version { get; set; }

    [JsonPropertyName("fallback")]
    public bool Fallback { get; set; }
}

public sealed class WorkbenchApiException : Exception
{
    public WorkbenchApiException(ApiFailure failure, int httpStatus)
        : base(failure.Message)
    {
        Failure = failure;
        HttpStatus = httpStatus;
    }

    public ApiFailure Failure { get; }
    public int HttpStatus { get; }
}

public static class StageLabels
{
    public static string Value(string stage) => stage switch
    {
        "queued" => "等待执行",
        "parsing" => "解析资料",
        "normalizing_assets" => "检查图片",
        "planning_visuals" => "规划视觉",
        "generating" => "生成内容",
        "profiling_template" => "分析模板",
        "planning_template" => "映射模板",
        "rendering" => "渲染文档",
        "linting" => "合规检查",
        "validating_package" => "校验包结构",
        "validating_analysis" => "校验分析结果",
        "validating_template" => "检查模板安全性",
        "done" => "处理完成",
        "failed" => "处理失败",
        "canceled" => "已取消",
        "canceling" => "正在取消",
        "validation_failed" => "契约校验失败",
        "timed_out" => "任务超时",
        "interrupted" => "任务被中断",
        "falling_back_to_stub" => "生成器降级为 Stub",
        "analyzing" => "分析资料",
        "testing_generator" => "测试生成器连接",
        "activating_generator" => "启用生成器",
        "configuring_generator" => "保存生成器配置",
        "preflight" => "提交前检查",
        "session_authentication" => "会话校验",
        "request_validation" => "请求校验",
        "rate_limited" => "请求过于频繁",
        _ => stage,
    };
}
