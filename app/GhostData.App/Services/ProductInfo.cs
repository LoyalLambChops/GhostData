namespace GhostData.App.Services;

internal static class ProductInfo
{
    public const string ReleaseName = "Phantom - Beta 1";
    public static string Version => typeof(ProductInfo).Assembly.GetName().Version!.ToString(3);
    public const string Email = "LoyalLambChops@gmail.com";
    public const string Twitch = "https://www.twitch.tv/loyallambchops";
    public const string Discord = "https://discord.gg/H3Et7NHavZ";
    public static string BugReportUri => "mailto:" + Email
        + "?subject=" + Uri.EscapeDataString($"GhostData {ReleaseName} ({Version}) - bug report / feedback")
        + "&body=" + Uri.EscapeDataString("What happened:\r\n\r\nWhat I expected:\r\n\r\nSteps to reproduce:\r\n\r\nWindows / Hearthstone version:\r\n\r\nPlease review any screenshots or logs before attaching them. GhostData attaches nothing automatically.");
}
