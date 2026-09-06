using System.Net;
using System.Net.Http.Json;

namespace DocumentWorkbench.Tests;

public sealed class WorkbenchApiClientTests
{
    [Fact]
    public async Task ValidateTemplateAsync_UploadsTemplateAndReadsValidationResult()
    {
        var templatePath = Path.Combine(Path.GetTempPath(), $"workbench-template-{Guid.NewGuid():N}.pptx");
        var handler = new CapturingResponseHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = JsonContent.Create(new { valid = true }),
        });

        try
        {
            await File.WriteAllBytesAsync(templatePath, [0x50, 0x4B, 0x03, 0x04]);
            using var httpClient = new HttpClient(handler)
            {
                BaseAddress = new Uri("http://127.0.0.1/"),
            };
            using var api = new WorkbenchApiClient(httpClient);

            var result = await api.ValidateTemplateAsync(templatePath);

            Assert.True(result.Valid);
            Assert.Equal(HttpMethod.Post, handler.Method);
            Assert.Equal("/api/templates/validate", handler.Path);
            Assert.Contains("template_file", handler.Content);
            Assert.Contains("workbench-template-", handler.Content);
        }
        finally
        {
            File.Delete(templatePath);
        }
    }

    [Fact]
    public async Task SanitizeTemplateAsync_UploadsTemplateAndWritesSafeCopy()
    {
        var templatePath = Path.Combine(Path.GetTempPath(), $"workbench-template-{Guid.NewGuid():N}.pptx");
        var outputPath = Path.Combine(Path.GetTempPath(), $"workbench-template-safe-{Guid.NewGuid():N}.pptx");
        var payload = new byte[] { 0x50, 0x4B, 0x03, 0x04, 0x01, 0x02, 0x03, 0x04 };
        var handler = new CapturingResponseHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new ByteArrayContent(payload),
        });

        try
        {
            await File.WriteAllBytesAsync(templatePath, [0x50, 0x4B, 0x03, 0x04]);
            using var httpClient = new HttpClient(handler)
            {
                BaseAddress = new Uri("http://127.0.0.1/"),
            };
            using var api = new WorkbenchApiClient(httpClient);

            await api.SanitizeTemplateAsync(templatePath, outputPath);

            Assert.Equal(HttpMethod.Post, handler.Method);
            Assert.Equal("/api/templates/sanitize", handler.Path);
            Assert.Contains("template_file", handler.Content);
            Assert.Equal(payload, await File.ReadAllBytesAsync(outputPath));
        }
        finally
        {
            File.Delete(templatePath);
            File.Delete(outputPath);
        }
    }

    [Fact]
    public async Task DownloadAsync_WritesSuccessfulBinaryResponse()
    {
        var payload = new byte[] { 0x50, 0x4B, 0x03, 0x04, 0x01, 0x02, 0x03, 0x04 };
        var outputPath = Path.Combine(Path.GetTempPath(), $"workbench-download-{Guid.NewGuid():N}.pptx");

        try
        {
            using var httpClient = new HttpClient(new StaticResponseHandler(() => new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new ByteArrayContent(payload),
            }))
            {
                BaseAddress = new Uri("http://127.0.0.1/"),
            };
            using var api = new WorkbenchApiClient(httpClient);

            await api.DownloadAsync("/api/download/job-123", outputPath);

            Assert.Equal(payload, await File.ReadAllBytesAsync(outputPath));
        }
        finally
        {
            File.Delete(outputPath);
        }
    }

    private sealed class StaticResponseHandler(Func<HttpResponseMessage> createResponse) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(createResponse());
    }

    private sealed class CapturingResponseHandler(Func<HttpResponseMessage> createResponse) : HttpMessageHandler
    {
        public HttpMethod? Method { get; private set; }
        public string? Path { get; private set; }
        public string Content { get; private set; } = "";

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Method = request.Method;
            Path = request.RequestUri?.AbsolutePath;
            Content = request.Content is null
                ? ""
                : await request.Content.ReadAsStringAsync(cancellationToken);
            return createResponse();
        }
    }
}
