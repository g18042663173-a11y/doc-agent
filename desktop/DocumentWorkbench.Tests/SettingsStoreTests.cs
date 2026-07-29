using System.Text.Json;

namespace DocumentWorkbench.Tests;

public sealed class SettingsStoreTests
{
    [Fact]
    public async Task SettingsRoundTripStoresOnlyNonSensitiveNgaConfiguration()
    {
        var root = Path.Combine(Path.GetTempPath(), $"document-workbench-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var store = new SettingsStore(root);
            var settings = new WorkbenchSettings
            {
                NgaEnabled = true,
                Nga = new NgaStoredConfig
                {
                    BaseUrl = "https://nga.example.internal",
                    EndpointPath = "/v1/chat/completions",
                    Model = "internal-model",
                },
                RecentJobIds = ["job-one", "job-one", "job-two"],
            };

            await store.SaveAsync(settings);
            var loaded = await store.LoadAsync();
            var raw = await File.ReadAllTextAsync(store.SettingsPath);

            Assert.True(loaded.NgaEnabled);
            Assert.Equal("internal-model", loaded.Nga.Model);
            Assert.Equal(["job-one", "job-two"], loaded.RecentJobIds);
            Assert.DoesNotContain("token", raw, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("credential", raw, StringComparison.OrdinalIgnoreCase);
            using var document = JsonDocument.Parse(raw);
            Assert.Equal("1.0", document.RootElement.GetProperty("settings_version").GetString());
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    [Fact]
    public void CredentialTargetAndStageLabelsRemainStable()
    {
        Assert.Equal("HuaweiDocumentGenerator/NGA", CredentialManager.NgaCredentialTarget);
        Assert.Equal("分析模板", StageLabels.Value("profiling_template"));
        Assert.Equal("校验包结构", StageLabels.Value("validating_package"));
    }
}
