using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace DocumentWorkbench;

public sealed class WorkbenchApiClient : IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };
    private readonly HttpClient _client;

    public WorkbenchApiClient(HttpClient client)
    {
        _client = client;
    }

    public Task<ApiVersionInfo> GetVersionAsync(CancellationToken cancellationToken = default) =>
        SendJsonAsync<ApiVersionInfo>(HttpMethod.Get, "api/version", null, cancellationToken);

    public Task<DiagnosticsInfo> GetDiagnosticsAsync(CancellationToken cancellationToken = default) =>
        SendJsonAsync<DiagnosticsInfo>(HttpMethod.Get, "api/diagnostics", null, cancellationToken);

    public async Task<List<JobInfo>> GetJobsAsync(CancellationToken cancellationToken = default) =>
        (await SendJsonAsync<JobListResponse>(HttpMethod.Get, "api/jobs", null, cancellationToken)).Jobs;

    public Task<JobInfo> GetJobAsync(string jobId, CancellationToken cancellationToken = default) =>
        SendJsonAsync<JobInfo>(HttpMethod.Get, $"api/status/{Uri.EscapeDataString(jobId)}", null, cancellationToken);

    public Task<JobInfo> CancelJobAsync(string jobId, CancellationToken cancellationToken = default) =>
        SendJsonAsync<JobInfo>(HttpMethod.Post, $"api/jobs/{Uri.EscapeDataString(jobId)}/cancel", new { }, cancellationToken);

    public async Task<AnalysisInfo> AnalyzeAsync(string inputPath, CancellationToken cancellationToken = default)
    {
        using var content = new MultipartFormDataContent();
        AddFile(content, "input_file", inputPath);
        using var response = await _client.PostAsync("api/analyze", content, cancellationToken);
        return await ReadJsonAsync<AnalysisInfo>(response, cancellationToken);
    }

    public async Task<JobInfo> GenerateAsync(
        string inputPath,
        string target,
        string? depth,
        string? theme,
        string? templatePath,
        IReadOnlyList<string> assetPaths,
        string idempotencyKey,
        CancellationToken cancellationToken = default)
    {
        using var content = new MultipartFormDataContent();
        content.Add(new StringContent(target), "type");
        if (target == "deck" && !string.IsNullOrWhiteSpace(depth))
        {
            content.Add(new StringContent(depth), "depth");
        }
        if (target == "deck" && !string.IsNullOrWhiteSpace(theme))
        {
            content.Add(new StringContent(theme), "theme");
        }
        AddFile(content, "input_file", inputPath);
        if (target == "deck" && !string.IsNullOrWhiteSpace(templatePath))
        {
            AddFile(content, "template_file", templatePath);
        }
        if (target == "deck")
        {
            foreach (var path in assetPaths)
            {
                AddFile(content, "asset_files", path);
            }
        }

        using var request = new HttpRequestMessage(HttpMethod.Post, "api/generate") { Content = content };
        request.Headers.Add("Idempotency-Key", idempotencyKey);
        using var response = await _client.SendAsync(request, cancellationToken);
        return await ReadJsonAsync<JobInfo>(response, cancellationToken);
    }

    public Task<GeneratorSettingsResponse> ConfigureGeneratorAsync(
        string generator,
        object? config,
        string? credential,
        bool clearCredential,
        string? mode = null,
        CancellationToken cancellationToken = default)
    {
        object payload = generator == "stub"
            ? new { generator = "stub", mode }
            : new
            {
                generator,
                config,
                credential,
                clear_credential = clearCredential,
                mode,
            };
        return SendJsonAsync<GeneratorSettingsResponse>(HttpMethod.Put, "api/settings/generator", payload, cancellationToken);
    }

    public Task<GeneratorSettingsResponse> GetGeneratorSettingsAsync(CancellationToken cancellationToken = default) =>
        SendJsonAsync<GeneratorSettingsResponse>(HttpMethod.Get, "api/settings/generator", null, cancellationToken);

    public Task<GeneratorSettingsResponse> TestGeneratorAsync(CancellationToken cancellationToken = default) =>
        SendJsonAsync<GeneratorSettingsResponse>(HttpMethod.Post, "api/settings/generator/test", new { }, cancellationToken);

    public Task<GeneratorSettingsResponse> ActivateGeneratorAsync(CancellationToken cancellationToken = default) =>
        SendJsonAsync<GeneratorSettingsResponse>(HttpMethod.Post, "api/settings/generator/activate", new { }, cancellationToken);

    public async Task DownloadAsync(string relativeUrl, string outputPath, CancellationToken cancellationToken = default)
    {
        using var response = await _client.GetAsync(relativeUrl, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var temporary = $"{outputPath}.{Guid.NewGuid():N}.download";
        try
        {
            await using (var input = await response.Content.ReadAsStreamAsync(cancellationToken))
            await using (var output = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                await input.CopyToAsync(output, cancellationToken);
            }
            File.Move(temporary, outputPath, true);
        }
        finally
        {
            File.Delete(temporary);
        }
    }

    private static void AddFile(MultipartFormDataContent content, string fieldName, string path)
    {
        var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        var fileContent = new StreamContent(stream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
        content.Add(fileContent, fieldName, Path.GetFileName(path));
    }

    private async Task<T> SendJsonAsync<T>(
        HttpMethod method,
        string url,
        object? payload,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, url);
        if (payload is not null)
        {
            request.Content = JsonContent.Create(payload, options: JsonOptions);
        }
        using var response = await _client.SendAsync(request, cancellationToken);
        return await ReadJsonAsync<T>(response, cancellationToken);
    }

    private static async Task<T> ReadJsonAsync<T>(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (!response.IsSuccessStatusCode)
        {
            await EnsureSuccessAsync(response, cancellationToken);
        }
        var value = await response.Content.ReadFromJsonAsync<T>(JsonOptions, cancellationToken);
        return value ?? throw new InvalidDataException("本地 API 返回了空响应。");
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        try
        {
            var payload = await response.Content.ReadFromJsonAsync<ApiErrorResponse>(JsonOptions, cancellationToken);
            if (payload?.Error is not null)
            {
                throw new WorkbenchApiException(payload.Error, (int)response.StatusCode);
            }
        }
        catch (JsonException)
        {
        }
        throw new HttpRequestException($"本地 API 请求失败（{(int)response.StatusCode}）。");
    }

    public void Dispose() => _client.Dispose();
}
