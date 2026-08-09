using Microsoft.Win32;

namespace DocumentWorkbench;

public static class AppearanceResolver
{
    public const string System = "system";
    public const string Light = "light";
    public const string Dark = "dark";

    public static string Normalize(string? appearance) => appearance switch
    {
        Light => Light,
        Dark => Dark,
        _ => System,
    };

    public static string PaletteResource(string? appearance, bool highContrast, bool systemUsesLightTheme)
    {
        if (highContrast)
        {
            return "Themes/Palette.HighContrast.xaml";
        }

        return Normalize(appearance) switch
        {
            Light => "Themes/Palette.Light.xaml",
            Dark => "Themes/Palette.Dark.xaml",
            _ when systemUsesLightTheme => "Themes/Palette.Light.xaml",
            _ => "Themes/Palette.Dark.xaml",
        };
    }

    public static bool SystemUsesLightTheme()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
            return key?.GetValue("AppsUseLightTheme") is not int value || value != 0;
        }
        catch (Exception) when (OperatingSystem.IsWindows())
        {
            // Settings remains usable when the personalization value is unavailable.
            return true;
        }
    }
}
