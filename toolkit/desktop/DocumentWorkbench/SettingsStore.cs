using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DocumentWorkbench;

public sealed class SettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
    };
    private readonly SemaphoreSlim _saveGate = new(1, 1);

    public SettingsStore(string applicationDataDirectory)
    {
        Directory.CreateDirectory(applicationDataDirectory);
        SettingsPath = Path.Combine(applicationDataDirectory, "settings.json");
    }

    public string SettingsPath { get; }

    public async Task<WorkbenchSettings> LoadAsync()
    {
        try
        {
            if (!File.Exists(SettingsPath))
            {
                return new WorkbenchSettings();
            }

            await using var stream = File.OpenRead(SettingsPath);
            var value = await JsonSerializer.DeserializeAsync<WorkbenchSettings>(stream, JsonOptions);
            if (value is not { SettingsVersion: "1.0" })
            {
                return new WorkbenchSettings();
            }

            value.Appearance = AppearanceResolver.Normalize(value.Appearance);
            // A hand-edited settings.json may contain "nga": null or
            // "recent_job_ids": null; normalize so no consumer sees a null.
            value.Nga ??= new NgaStoredConfig();
            value.Codex ??= new CodexStoredConfig();
            value.RecentJobIds ??= [];
            return value;
        }
        catch (IOException)
        {
            return new WorkbenchSettings();
        }
        catch (JsonException)
        {
            return new WorkbenchSettings();
        }
    }

    public async Task SaveAsync(WorkbenchSettings settings)
    {
        await _saveGate.WaitAsync();
        try
        {
            settings.Appearance = AppearanceResolver.Normalize(settings.Appearance);
            settings.RecentJobIds = settings.RecentJobIds
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.Ordinal)
                .Take(50)
                .ToList();
            var temporary = SettingsPath + ".tmp";
            await using (var stream = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                await JsonSerializer.SerializeAsync(stream, settings, JsonOptions);
                await stream.FlushAsync();
            }
            File.Move(temporary, SettingsPath, true);
        }
        finally
        {
            _saveGate.Release();
        }
    }
}

public sealed class WorkbenchSettings
{
    public string SettingsVersion { get; set; } = "1.0";
    public string DefaultTarget { get; set; } = "deck";
    public string DefaultDepth { get; set; } = "标准";
    public string DefaultTheme { get; set; } = "hw_v1";
    public string Appearance { get; set; } = AppearanceResolver.System;
    public string GeneratorMode { get; set; } = "auto";
    public bool NgaEnabled { get; set; }
    public NgaStoredConfig Nga { get; set; } = new();
    public CodexStoredConfig Codex { get; set; } = new();
    public List<string> RecentJobIds { get; set; } = [];
}

public sealed class NgaStoredConfig
{
    public string ConfigVersion { get; set; } = "1.0";
    public string Transport { get; set; } = "http";
    public string CliPath { get; set; } = "nga";
    public string BaseUrl { get; set; } = "";
    public string EndpointPath { get; set; } = "/v1/chat/completions";
    public string Model { get; set; } = "";
    public int TimeoutSeconds { get; set; } = 120;
    public int MaxRetries { get; set; } = 2;
    public bool VerifyTls { get; set; } = true;
    public string? CaBundlePath { get; set; }
    public string ResponseFormat { get; set; } = "json_object";
    public bool AllowInsecureHttp { get; set; }
}

/// <summary>Non-sensitive opencode-go channel settings (the API key lives in
/// Windows Credential Manager, never in settings.json).</summary>
public sealed class CodexStoredConfig
{
    public string ConfigVersion { get; set; } = "1.0";
    public string BaseUrl { get; set; } = "https://opencode.ai/zen/go/v1";
    public string Model { get; set; } = "deepseek-v4-flash";
    public string ApiMode { get; set; } = "responses";
    public int TimeoutSeconds { get; set; } = 300;
    public string ReasoningEffort { get; set; } = "high";
}
