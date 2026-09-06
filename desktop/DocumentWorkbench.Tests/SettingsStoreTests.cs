using System.Text.Json;
using System.Xml.Linq;

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
    public async Task GeneratorModeDefaultsToAutoAndRoundTrips()
    {
        var root = Path.Combine(Path.GetTempPath(), $"document-workbench-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var store = new SettingsStore(root);
            var settings = new WorkbenchSettings();
            await store.SaveAsync(settings);

            var loaded = await store.LoadAsync();
            Assert.Equal("auto", loaded.GeneratorMode);

            loaded.GeneratorMode = "strict";
            await store.SaveAsync(loaded);
            var reloaded = await store.LoadAsync();
            Assert.Equal("strict", reloaded.GeneratorMode);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    [Theory]
    [InlineData("system", "system")]
    [InlineData("light", "light")]
    [InlineData("dark", "dark")]
    [InlineData("unexpected", "system")]
    public async Task AppearancePreservesLegacyOverridesAndNormalizesUnknownValues(string storedAppearance, string expectedAppearance)
    {
        var root = Path.Combine(Path.GetTempPath(), $"document-workbench-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var store = new SettingsStore(root);
            await File.WriteAllTextAsync(
                store.SettingsPath,
                $$"""{ "settings_version": "1.0", "appearance": "{{storedAppearance}}" }""");

            var loaded = await store.LoadAsync();

            Assert.Equal(expectedAppearance, loaded.Appearance);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    [Fact]
    public async Task AppearanceDefaultsToFollowSystem()
    {
        var root = Path.Combine(Path.GetTempPath(), $"document-workbench-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var settings = await new SettingsStore(root).LoadAsync();

            Assert.Equal(AppearanceResolver.System, settings.Appearance);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    [Fact]
    public async Task NullNgaAndRecentJobIdsAreNormalizedToNonNull()
    {
        var root = Path.Combine(Path.GetTempPath(), $"document-workbench-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var store = new SettingsStore(root);
            await File.WriteAllTextAsync(
                store.SettingsPath,
                """{ "settings_version": "1.0", "nga": null, "recent_job_ids": null }""");

            var loaded = await store.LoadAsync();

            Assert.NotNull(loaded.Nga);
            Assert.NotNull(loaded.RecentJobIds);
            Assert.Equal("http", loaded.Nga.Transport);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    [Theory]
    [InlineData("system", false, true, "Themes/Palette.Light.xaml")]
    [InlineData("system", false, false, "Themes/Palette.Dark.xaml")]
    [InlineData("light", false, false, "Themes/Palette.Light.xaml")]
    [InlineData("dark", false, true, "Themes/Palette.Dark.xaml")]
    [InlineData("dark", true, true, "Themes/Palette.HighContrast.xaml")]
    public void AppearanceResolverSelectsSystemAndHighContrastPalettes(
        string appearance,
        bool highContrast,
        bool systemUsesLightTheme,
        string expectedResource)
    {
        Assert.Equal(expectedResource, AppearanceResolver.PaletteResource(appearance, highContrast, systemUsesLightTheme));
    }

    [Fact]
    public void CredentialTargetAndStageLabelsRemainStable()
    {
        Assert.Equal("HuaweiDocumentGenerator/NGA", CredentialManager.NgaCredentialTarget);
        Assert.Equal("分析模板", StageLabels.Value("profiling_template"));
        Assert.Equal("校验包结构", StageLabels.Value("validating_package"));
    }

    [Fact]
    public void NamedTextStylesInheritTheTokenizedTextStyle()
    {
        var repositoryRoot = FindRepositoryRoot();
        var document = XDocument.Load(Path.Combine(repositoryRoot, "desktop", "DocumentWorkbench", "MainWindow.xaml"));
        var xaml = (XNamespace)"http://schemas.microsoft.com/winfx/2006/xaml/presentation";
        var x = (XNamespace)"http://schemas.microsoft.com/winfx/2006/xaml";

        foreach (var key in new[] { "PageTitle", "SectionTitle", "FieldLabel" })
        {
            var style = document
                .Descendants(xaml + "Style")
                .Single(element => (string?)element.Attribute(x + "Key") == key);

            Assert.Equal("{StaticResource {x:Type TextBlock}}", (string?)style.Attribute("BasedOn"));
        }
    }

    private static string FindRepositoryRoot()
    {
        var cursor = new DirectoryInfo(AppContext.BaseDirectory);
        while (cursor is not null)
        {
            if (File.Exists(Path.Combine(cursor.FullName, "backend", "app", "web_api.py")))
            {
                return cursor.FullName;
            }
            cursor = cursor.Parent;
        }

        throw new DirectoryNotFoundException("Repository root was not found.");
    }
}
