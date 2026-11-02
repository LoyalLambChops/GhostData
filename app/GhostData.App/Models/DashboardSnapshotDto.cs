using System.Text.Json.Serialization;

namespace GhostData.App.Models;

public sealed class DashboardSnapshotDto
{
    [JsonPropertyName("deck_library")] public List<DashboardDeckListDto> DeckLibrary { get; set; } = new();
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; }
    [JsonPropertyName("generated_at")] public string GeneratedAt { get; set; } = "";
    [JsonPropertyName("active_hearthstone_build")] public string ActiveHearthstoneBuild { get; set; } = "";
    [JsonPropertyName("overall")] public DashboardSummaryDto Overall { get; set; } = new();
    [JsonPropertyName("deck_versions")] public List<DashboardDeckVersionDto> DeckVersions { get; set; } = new();
    [JsonPropertyName("by_opponent_class")] public List<DashboardBreakdownDto> ByOpponentClass { get; set; } = new();
    [JsonPropertyName("by_initiative")] public List<DashboardBreakdownDto> ByInitiative { get; set; } = new();
    [JsonPropertyName("mulligan_history")] public List<DashboardMulliganCardDto> MulliganHistory { get; set; } = new();
    [JsonPropertyName("recent_matches")] public List<DashboardMatchDto> RecentMatches { get; set; } = new();
    [JsonPropertyName("total_recorded_matches")] public int TotalRecordedMatches { get; set; }
    [JsonPropertyName("data_quality")] public DashboardDataQualityDto DataQuality { get; set; } = new();
}

public class DashboardSummaryDto
{
    [JsonPropertyName("games")] public int Games { get; set; }
    [JsonPropertyName("wins")] public int Wins { get; set; }
    [JsonPropertyName("losses")] public int Losses { get; set; }
    [JsonPropertyName("record")] public string Record { get; set; } = "0-0";
    [JsonPropertyName("win_rate")] public double WinRate { get; set; }
    [JsonPropertyName("average_duration_seconds")] public int AverageDurationSeconds { get; set; }
    [JsonPropertyName("average_duration")] public string AverageDuration { get; set; } = "—";
}

public class DashboardBreakdownDto : DashboardSummaryDto
{
    [JsonPropertyName("key")] public string Key { get; set; } = "";
    [JsonPropertyName("label")] public string Label { get; set; } = "";
}

public sealed class DashboardDeckVersionDto : DashboardBreakdownDto
{
    [JsonPropertyName("deck_name")] public string DeckName { get; set; } = "";
    [JsonPropertyName("archetype_name")] public string ArchetypeName { get; set; } = "";
    [JsonPropertyName("player_class")] public string PlayerClass { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    [JsonPropertyName("detail")] public string Detail { get; set; } = "";
}

public sealed class DashboardMulliganCardDto
{
    [JsonPropertyName("card_name")] public string CardName { get; set; } = "";
    [JsonPropertyName("offered_games")] public int OfferedGames { get; set; }
    [JsonPropertyName("kept_games")] public int KeptGames { get; set; }
    [JsonPropertyName("replaced_games")] public int ReplacedGames { get; set; }
    [JsonPropertyName("kept_record")] public string KeptRecord { get; set; } = "—";
    [JsonPropertyName("replaced_record")] public string ReplacedRecord { get; set; } = "—";
}

public sealed class DashboardCardEventDto
{
    [JsonPropertyName("turn")] public int Turn { get; set; }
    [JsonPropertyName("card_id")] public string CardId { get; set; } = "";
    [JsonPropertyName("card_name")] public string CardName { get; set; } = "";
}

public sealed class DashboardMatchDto
{
    [JsonPropertyName("deck_id")] public string DeckId { get; set; } = "";
    [JsonPropertyName("match_id")] public string MatchId { get; set; } = "";
    [JsonPropertyName("recorded_at")] public string RecordedAt { get; set; } = "";
    [JsonPropertyName("result")] public string Result { get; set; } = "";
    [JsonPropertyName("result_label")] public string ResultLabel { get; set; } = "";
    [JsonPropertyName("player_class")] public string PlayerClass { get; set; } = "";
    [JsonPropertyName("opponent_class")] public string OpponentClass { get; set; } = "";
    [JsonPropertyName("initiative")] public string Initiative { get; set; } = "";
    [JsonPropertyName("initiative_label")] public string InitiativeLabel { get; set; } = "Unknown";
    [JsonPropertyName("deck_label")] public string DeckLabel { get; set; } = "";
    [JsonPropertyName("deck_name")] public string DeckName { get; set; } = "";
    [JsonPropertyName("archetype_name")] public string ArchetypeName { get; set; } = "";
    [JsonPropertyName("deck_version")] public string DeckVersion { get; set; } = "";
    [JsonPropertyName("hearthstone_build")] public string HearthstoneBuild { get; set; } = "";
    [JsonPropertyName("format")] public string Format { get; set; } = "STANDARD";
    [JsonPropertyName("game_type")] public string GameType { get; set; } = "";
    [JsonPropertyName("mode_label")] public string ModeLabel { get; set; } = "Standard";
    [JsonPropertyName("turn_count")] public int TurnCount { get; set; }
    [JsonPropertyName("duration_seconds")] public int DurationSeconds { get; set; }
    [JsonPropertyName("duration_text")] public string DurationText { get; set; } = "—";
    [JsonPropertyName("mulligan_offered")] public List<string> MulliganOffered { get; set; } = new();
    [JsonPropertyName("mulligan_kept")] public List<string> MulliganKept { get; set; } = new();
    [JsonPropertyName("mulligan_replaced")] public List<string> MulliganReplaced { get; set; } = new();
    [JsonPropertyName("cards_drawn")] public List<DashboardCardEventDto> CardsDrawn { get; set; } = new();
    [JsonPropertyName("cards_played")] public List<DashboardCardEventDto> CardsPlayed { get; set; } = new();
    [JsonPropertyName("opponent_observed")] public List<DashboardCardEventDto> OpponentObserved { get; set; } = new();
    [JsonPropertyName("data_quality")] public string DataQuality { get; set; } = "COMPLETE";
}

public sealed class DashboardDataQualityDto
{
    [JsonPropertyName("limited_matches")] public int LimitedMatches { get; set; }
    [JsonPropertyName("complete_matches")] public int CompleteMatches { get; set; }
}

public sealed class DashboardDeckListDto
{
    [JsonPropertyName("key")] public string Key {get;set;}="";
    [JsonPropertyName("deck_id")] public string DeckId {get;set;}="";
    [JsonPropertyName("version")] public string Version {get;set;}="";
    [JsonPropertyName("name")] public string Name {get;set;}="";
    [JsonPropertyName("player_class")] public string PlayerClass {get;set;}="";
    [JsonPropertyName("available")] public bool Available {get;set;}
    [JsonPropertyName("total")] public int Total {get;set;}
    [JsonPropertyName("status")] public string Status {get;set;}="";
    [JsonPropertyName("cards")] public List<DashboardDeckCardDto> Cards {get;set;}=new();
    [JsonPropertyName("sideboard")] public List<DashboardDeckCardDto> Sideboard {get;set;}=new();
    public string Detail => $"{PlayerClass} · Version {(Version.Length>8?Version[..8]:Version)}";
    public string CountLabel => Available?$"{Total} cards · {Cards.Count} distinct · {Sideboard.Sum(c=>c.Count)} sideboard":"List unavailable";
    public bool HasSideboard => Sideboard.Count>0;
    [JsonPropertyName("deck_code")] public string DeckCode {get;set;}="";
    public bool HasDeckCode => !string.IsNullOrWhiteSpace(DeckCode);
    private static string SingleLine(string value) => string.Join(" ",value.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries));
    public string CopyText => "### "+SingleLine(Name)+"\n# "+SingleLine(Detail)+"\n# Format: Standard\n#\n"
        +string.Join("\n",Cards.Select(c=>$"# {c.Count}x {SingleLine(c.Name)} ({c.CostLabel})"))
        +(HasSideboard?"\n#\n# Sideboard\n"+string.Join("\n",Sideboard.Select(c=>$"# {SingleLine(c.Owner)}: {c.Count}x {SingleLine(c.Name)}")):"")
        +(HasDeckCode?"\n#\n"+DeckCode+"\n":"\n# Deck code unavailable: local card or hero identifiers are incomplete.\n");

}
public sealed class DashboardDeckCardDto
{
    [JsonPropertyName("card_id")] public string CardId {get;set;}="";
    [JsonPropertyName("name")] public string Name {get;set;}="";
    [JsonPropertyName("cost")] public int? Cost {get;set;}
    [JsonPropertyName("count")] public int Count {get;set;}
    [JsonPropertyName("text")] public string Text {get;set;}="";
    [JsonPropertyName("owner")] public string Owner {get;set;}="";
    public string CostLabel => Cost?.ToString() ?? "?";
    public string Copies => $"×{Count}";
    public string RulesText => string.IsNullOrWhiteSpace(Text)?"Local card text unavailable.":GhostData.App.Services.CardTextFormatter.Format(Text);
}
