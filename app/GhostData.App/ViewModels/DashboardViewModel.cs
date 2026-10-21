using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;
using GhostData.App.Models;

namespace GhostData.App.ViewModels;

public sealed class DashboardBreakdownItemViewModel
{
    public string Label { get; init; } = "";
    public int Games { get; init; }
    public string Record { get; init; } = "0-0";
    public string WinRate { get; init; } = "—";
    public string AverageDuration { get; init; } = "—";
    public string GamesText => Games == 1 ? "1 game" : $"{Games} games";
    public static DashboardBreakdownItemViewModel From(DashboardBreakdownDto dto) => new()
    {
        Label = dto.Label, Games = dto.Games, Record = dto.Record,
        WinRate = dto.Games > 0 ? $"{dto.WinRate:0.0}%" : "—", AverageDuration = dto.AverageDuration,
    };
}

public sealed class DashboardDeckVersionItemViewModel
{
    public string DeckName { get; init; } = "Deck";
    public string Detail { get; init; } = "";
    public int Games { get; init; }
    public string Record { get; init; } = "0-0";
    public string WinRate { get; init; } = "—";
    public string AverageDuration { get; init; } = "—";
    public string GamesText => Games == 1 ? "1 game" : $"{Games} games";
    public static DashboardDeckVersionItemViewModel From(DashboardDeckVersionDto dto) => new()
    {
        DeckName = string.IsNullOrWhiteSpace(dto.DeckName) ? dto.Label : dto.DeckName,
        Detail = dto.Detail, Games = dto.Games, Record = dto.Record,
        WinRate = dto.Games > 0 ? $"{dto.WinRate:0.0}%" : "—", AverageDuration = dto.AverageDuration,
    };
}

public sealed class DashboardMulliganCardItemViewModel
{
    public string CardName { get; init; } = "";
    public int OfferedGames { get; init; }
    public int KeptGames { get; init; }
    public int ReplacedGames { get; init; }
    public string KeptRecord { get; init; } = "—";
    public string ReplacedRecord { get; init; } = "—";
    public string ChoiceText => $"Offered {OfferedGames} · Kept {KeptGames} · Replaced {ReplacedGames}";
    public string ResultText => $"Kept {KeptRecord} · Replaced {ReplacedRecord}";
    public static DashboardMulliganCardItemViewModel From(DashboardMulliganCardDto dto) => new()
    {
        CardName = dto.CardName, OfferedGames = dto.OfferedGames, KeptGames = dto.KeptGames,
        ReplacedGames = dto.ReplacedGames, KeptRecord = dto.KeptRecord, ReplacedRecord = dto.ReplacedRecord,
    };
}

public sealed class DashboardMatchItemViewModel
{
    public DashboardMatchDto Source { get; init; } = new();
    public string DeckKey => string.IsNullOrEmpty(Source.DeckId) ? $"{PlayerClass}|{DisplayDeckName}" : Source.DeckId;
    public DateTimeOffset? Timestamp => DateTimeOffset.TryParse(Source.RecordedAt, out var d) ? d : null;
    public string MatchId { get; init; } = "";
    public string RecordedAt { get; init; } = "";
    public string ResultLabel { get; init; } = "";
    public string DeckLabel { get; init; } = "";
    public string DeckName { get; init; } = "";
    public string ArchetypeName { get; init; } = "";
    public string PlayerClass { get; init; } = "";
    public string DeckVersion { get; init; } = "";
    public string OpponentClass { get; init; } = "";
    public string Mode { get; init; } = "Standard";
    public string Initiative { get; init; } = "Unknown";
    public int TurnCount { get; init; }
    public string Duration { get; init; } = "—";
    public string Build { get; init; } = "";
    public string MulliganOffered { get; init; } = "—";
    public string MulliganKept { get; init; } = "—";
    public string MulliganReplaced { get; init; } = "—";
    public string CardsDrawn { get; init; } = "—";
    public string CardsPlayed { get; init; } = "—";
    public string OpponentObserved { get; init; } = "—";
    public string DataQuality { get; init; } = "Complete";
    public string DisplayDeckName => string.IsNullOrWhiteSpace(DeckName) ? DeckLabel : DeckName;
    public string DisplayArchetype => !string.IsNullOrWhiteSpace(ArchetypeName) ? ArchetypeName : (!string.IsNullOrWhiteSpace(PlayerClass) ? CultureInfo.InvariantCulture.TextInfo.ToTitleCase(PlayerClass.Replace("_", " ").ToLowerInvariant()) : "Unclassified");
    public string VersionLabel => string.IsNullOrWhiteSpace(DeckVersion) ? "Unresolved" : DeckVersion;
    public string OpponentLabel => string.IsNullOrWhiteSpace(OpponentClass) ? "Unknown" : CultureInfo.InvariantCulture.TextInfo.ToTitleCase(OpponentClass.Replace("_", " ").ToLowerInvariant());
    public string TurnLabel => TurnCount > 0 ? TurnCount.ToString(CultureInfo.InvariantCulture) : "—";

    public static DashboardMatchItemViewModel From(DashboardMatchDto dto)
    {
        static string JoinOrDash(IEnumerable<string> values) { var a = values.Where(x => !string.IsNullOrWhiteSpace(x)).ToList(); return a.Count == 0 ? "—" : string.Join(", ", a); }
        static string Events(IEnumerable<DashboardCardEventDto> values) { var a = values.Where(x => !string.IsNullOrWhiteSpace(x.CardName)).Select(x => x.Turn > 0 ? $"T{x.Turn} {x.CardName}" : x.CardName).ToList(); return a.Count == 0 ? "—" : string.Join(" · ", a); }
        var when = dto.RecordedAt;
        if (DateTimeOffset.TryParse(dto.RecordedAt, out var parsed)) when = parsed.ToLocalTime().ToString("MMM d · h:mm tt", CultureInfo.CurrentCulture);
        return new DashboardMatchItemViewModel
        {
            Source=dto, MatchId=dto.MatchId, RecordedAt=when, ResultLabel=dto.ResultLabel, DeckLabel=dto.DeckLabel,
            DeckName=dto.DeckName, ArchetypeName=dto.ArchetypeName, PlayerClass=dto.PlayerClass,
            DeckVersion=dto.DeckVersion, OpponentClass=dto.OpponentClass, Mode=dto.ModeLabel, Initiative=dto.InitiativeLabel,
            TurnCount=dto.TurnCount, Duration=dto.DurationText, Build=dto.HearthstoneBuild,
            MulliganOffered=JoinOrDash(dto.MulliganOffered), MulliganKept=JoinOrDash(dto.MulliganKept),
            MulliganReplaced=JoinOrDash(dto.MulliganReplaced), CardsDrawn=Events(dto.CardsDrawn),
            CardsPlayed=Events(dto.CardsPlayed), OpponentObserved=Events(dto.OpponentObserved),
            DataQuality=string.Equals(dto.DataQuality,"COMPLETE",StringComparison.OrdinalIgnoreCase)?"Complete":"Limited",
        };
    }
}

public sealed class DashboardViewModel : INotifyPropertyChanged
{
    private const string AllDecks="All decks", AllVersions="All versions", AllOpponents="All opponents", AllModes="All modes", AllResults="All results", AllOrders="All orders";
    private readonly List<DashboardMatchItemViewModel> _allMatches = new();
    private string _games="0", _record="0-0", _winRate="—", _averageDuration="—", _build="—", _status="Loading local match history…", _dataQuality="";
    private DashboardMatchItemViewModel? _selectedMatch;
    private string _selectedDeckFilter=AllDecks, _selectedVersionFilter=AllVersions, _selectedOpponentFilter=AllOpponents, _selectedModeFilter=AllModes, _selectedResultFilter=AllResults, _selectedOrderFilter=AllOrders;
    private bool _isBusy;
    private string _selectedPeriod = "All time", _selectedClass = "All classes", _selectedType = "All deck types";
    private string _averageTurns = "—", _totalTime = "—", _bestMatchup = "—", _worstMatchup = "—";
    public ObservableCollection<DeckStatistics> DeckStatistics { get; } = new();
    public ObservableCollection<MatchupMatrixRow> MatchupMatrix { get; } = new();
    public ObservableCollection<MatchupMatrixRow> DeckMatchups { get; } = new();
    public ObservableCollection<ChartBar> Results { get; } = new();
    public ObservableCollection<DeckHighlight> Highlights { get; } = new();
    public ObservableCollection<ChartBar> WinrateAsClass { get; } = new();
    public ObservableCollection<ChartBar> WinrateAgainstClass { get; } = new();
    public ObservableCollection<ChartBar> WinrateByCoin { get; } = new();
    public ObservableCollection<ChartBar> PlayedClasses { get; } = new();
    public ObservableCollection<ChartBar> OpponentClasses { get; } = new();
    public ObservableCollection<ChartBar> WinrateHistory { get; } = new();
    public ObservableCollection<string> ClassFilterOptions { get; } = new() { "All classes" };
    public ObservableCollection<string> TypeFilterOptions { get; } = new() { "All deck types" };
    public string[] PeriodFilterOptions { get; } = { "All time", "Today", "Last 7 days", "Last 30 days" };
    public string SelectedPeriod { get => _selectedPeriod; set { if(Set(ref _selectedPeriod,value)) ApplyFilters(); } }
    public string SelectedClass { get => _selectedClass; set { if(Set(ref _selectedClass,value)) ApplyFilters(); } }
    public string SelectedType { get => _selectedType; set { if(Set(ref _selectedType,value)) ApplyFilters(); } }
    public string AverageTurns { get => _averageTurns; private set => Set(ref _averageTurns,value); }
    public string TotalTime { get => _totalTime; private set => Set(ref _totalTime,value); }
    public string BestMatchup { get => _bestMatchup; private set => Set(ref _bestMatchup,value); }
    public string WorstMatchup { get => _worstMatchup; private set => Set(ref _worstMatchup,value); }


    public ObservableCollection<DashboardDeckVersionItemViewModel> DeckVersions { get; } = new();
    public ObservableCollection<DashboardBreakdownItemViewModel> Opponents { get; } = new();
    public ObservableCollection<DashboardBreakdownItemViewModel> Initiatives { get; } = new();
    public ObservableCollection<DashboardMulliganCardItemViewModel> Mulligans { get; } = new();
    public ObservableCollection<DashboardMatchItemViewModel> Matches { get; } = new();
    public ObservableCollection<string> DeckFilterOptions { get; } = new(){AllDecks};
    public ObservableCollection<string> VersionFilterOptions { get; } = new(){AllVersions};
    public ObservableCollection<string> OpponentFilterOptions { get; } = new(){AllOpponents};
    public ObservableCollection<string> ModeFilterOptions { get; } = new(){AllModes};
    public ObservableCollection<string> ResultFilterOptions { get; } = new(){AllResults,"Win","Loss"};
    public ObservableCollection<string> OrderFilterOptions { get; } = new(){AllOrders,"First","Second"};
    public string Games { get=>_games; private set=>Set(ref _games,value); }
    public string Record { get=>_record; private set=>Set(ref _record,value); }
    public string WinRate { get=>_winRate; private set=>Set(ref _winRate,value); }
    public string AverageDuration { get=>_averageDuration; private set=>Set(ref _averageDuration,value); }
    public string BuildLabel { get=>_build; private set=>Set(ref _build,value); }
    public string Status { get=>_status; set=>Set(ref _status,value); }
    public string DataQuality { get=>_dataQuality; private set=>Set(ref _dataQuality,value); }
    public bool IsBusy { get=>_isBusy; set=>Set(ref _isBusy,value); }
    public DashboardMatchItemViewModel? SelectedMatch { get=>_selectedMatch; set=>Set(ref _selectedMatch,value); }
    public string SelectedDeckFilter { get=>_selectedDeckFilter; set { if(Set(ref _selectedDeckFilter,value??AllDecks)) ApplyFilters(); } }
    public string SelectedVersionFilter { get=>_selectedVersionFilter; set { if(Set(ref _selectedVersionFilter,value??AllVersions)) ApplyFilters(); } }
    public string SelectedOpponentFilter { get=>_selectedOpponentFilter; set { if(Set(ref _selectedOpponentFilter,value??AllOpponents)) ApplyFilters(); } }
    public string SelectedModeFilter { get=>_selectedModeFilter; set { if(Set(ref _selectedModeFilter,value??AllModes)) ApplyFilters(); } }
    public string SelectedResultFilter { get=>_selectedResultFilter; set { if(Set(ref _selectedResultFilter,value??AllResults)) ApplyFilters(); } }
    public string SelectedOrderFilter { get=>_selectedOrderFilter; set { if(Set(ref _selectedOrderFilter,value??AllOrders)) ApplyFilters(); } }

    public void Apply(DashboardSnapshotDto snapshot)
    {
        Games=snapshot.Overall.Games.ToString(CultureInfo.InvariantCulture); Record=snapshot.Overall.Record;
        WinRate=snapshot.Overall.Games>0?$"{snapshot.Overall.WinRate:0.0}%":"—"; AverageDuration=snapshot.Overall.AverageDuration;
        BuildLabel=string.IsNullOrWhiteSpace(snapshot.ActiveHearthstoneBuild)?"Build unavailable":"Build "+snapshot.ActiveHearthstoneBuild;
        DataQuality=snapshot.DataQuality.LimitedMatches==0?$"{snapshot.DataQuality.CompleteMatches} complete records":$"{snapshot.DataQuality.CompleteMatches} complete · {snapshot.DataQuality.LimitedMatches} limited";
        DeckVersions.Clear(); foreach(var item in snapshot.DeckVersions) DeckVersions.Add(DashboardDeckVersionItemViewModel.From(item));
        Opponents.Clear(); foreach(var item in snapshot.ByOpponentClass) Opponents.Add(DashboardBreakdownItemViewModel.From(item));
        Initiatives.Clear(); foreach(var item in snapshot.ByInitiative) Initiatives.Add(DashboardBreakdownItemViewModel.From(item));
        Mulligans.Clear(); foreach(var item in snapshot.MulliganHistory.Take(20)) Mulligans.Add(DashboardMulliganCardItemViewModel.From(item));
        var selectedId=SelectedMatch?.MatchId; _allMatches.Clear(); _allMatches.AddRange(snapshot.RecentMatches.Select(DashboardMatchItemViewModel.From));
        RebuildFilterOptions(); ApplyFilters(selectedId);
    }

    private void RebuildFilterOptions()
    {
        static void Reset(ObservableCollection<string> target,string all,IEnumerable<string> values){var desired=new[]{all}.Concat(values.Where(x=>!string.IsNullOrWhiteSpace(x)).Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(x=>x,StringComparer.OrdinalIgnoreCase)).ToList(); if(target.SequenceEqual(desired))return; for(var i=target.Count-1;i>=0;i--)if(!desired.Contains(target[i]))target.RemoveAt(i); foreach(var v in desired)if(!target.Contains(v))target.Add(v);}
        Reset(DeckFilterOptions,AllDecks,_allMatches.Select(x=>x.DisplayDeckName)); Reset(VersionFilterOptions,AllVersions,_allMatches.Select(x=>x.VersionLabel)); Reset(OpponentFilterOptions,AllOpponents,_allMatches.Select(x=>x.OpponentLabel)); Reset(ModeFilterOptions,AllModes,_allMatches.Select(x=>x.Mode));
        Reset(ClassFilterOptions,"All classes",_allMatches.Select(x=>x.PlayerClass));
        Reset(TypeFilterOptions,"All deck types",_allMatches.Select(x=>x.ArchetypeName).Where(x=>!string.IsNullOrWhiteSpace(x)));
        if(!ClassFilterOptions.Contains(SelectedClass)) SelectedClass="All classes";
        if(!TypeFilterOptions.Contains(SelectedType)) SelectedType="All deck types";
        if(!DeckFilterOptions.Contains(SelectedDeckFilter))_selectedDeckFilter=AllDecks; if(!VersionFilterOptions.Contains(SelectedVersionFilter))_selectedVersionFilter=AllVersions; if(!OpponentFilterOptions.Contains(SelectedOpponentFilter))_selectedOpponentFilter=AllOpponents; if(!ModeFilterOptions.Contains(SelectedModeFilter))_selectedModeFilter=AllModes;
        OnPropertyChanged(nameof(SelectedDeckFilter));OnPropertyChanged(nameof(SelectedVersionFilter));OnPropertyChanged(nameof(SelectedOpponentFilter));OnPropertyChanged(nameof(SelectedModeFilter));
    }
    private void ApplyFilters(string? preferredMatchId=null)
    {
        IEnumerable<DashboardMatchItemViewModel> rows=_allMatches;
        if(SelectedDeckFilter!=AllDecks)rows=rows.Where(x=>string.Equals(x.DisplayDeckName,SelectedDeckFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedVersionFilter!=AllVersions)rows=rows.Where(x=>string.Equals(x.VersionLabel,SelectedVersionFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedOpponentFilter!=AllOpponents)rows=rows.Where(x=>string.Equals(x.OpponentLabel,SelectedOpponentFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedModeFilter!=AllModes)rows=rows.Where(x=>string.Equals(x.Mode,SelectedModeFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedResultFilter!=AllResults)rows=rows.Where(x=>string.Equals(x.ResultLabel,SelectedResultFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedOrderFilter!=AllOrders)rows=rows.Where(x=>string.Equals(x.Initiative,SelectedOrderFilter,StringComparison.OrdinalIgnoreCase));
        if(SelectedClass != "All classes") rows=rows.Where(x=>x.PlayerClass==SelectedClass);
        if(SelectedType != "All deck types") rows=rows.Where(x=>x.ArchetypeName==SelectedType);
        DateTimeOffset? since=SelectedPeriod switch { "Today"=>new DateTimeOffset(DateTime.Today), "Last 7 days"=>DateTimeOffset.Now.AddDays(-7), "Last 30 days"=>DateTimeOffset.Now.AddDays(-30), _=>null };
        if(since is not null) rows=rows.Where(x=>x.Timestamp >= since);
        var filtered=rows.ToList();
        Recalculate(filtered); preferredMatchId??=SelectedMatch?.MatchId; Matches.Clear(); foreach(var row in filtered)Matches.Add(row); SelectedMatch=Matches.FirstOrDefault(x=>x.MatchId==preferredMatchId)??Matches.FirstOrDefault();
        Status=_allMatches.Count==0?"No completed local games recorded yet. Play normally; GhostData will build this history automatically.":$"Showing {Matches.Count} of {_allMatches.Count} recorded matches · local only";
    }
    private void Recalculate(List<DashboardMatchItemViewModel> rows)
    {
        var stats = new DeckStatistics("All decks", "", rows);
        Games=rows.Count.ToString(); Record=stats.Record; WinRate=stats.WinRate;
        AverageDuration=stats.AverageDuration; AverageTurns=stats.AverageTurns; TotalTime=stats.TotalTime;
        BestMatchup=stats.BestMatchup; WorstMatchup=stats.WorstMatchup;
        var decks = rows.Where(x => !string.IsNullOrWhiteSpace(x.DeckName) || !string.IsNullOrWhiteSpace(x.Source.DeckId))
            .GroupBy(x => x.DeckKey).Select(g => g.ToList()).ToList();
        static double Performance(List<DashboardMatchItemViewModel> games)
        {
            var count = games.Count(x => x.Source.Result is "WIN" or "LOSS");
            return count / (games.Count(x => x.Source.Result == "LOSS") + 1.0) * Math.Min(1, count / 10.0);
        }
        DeckStatistics Describe(List<DashboardMatchItemViewModel>? games) => games is null
            ? new DeckStatistics("—", "", new()) : new DeckStatistics(games[0].DisplayDeckName, "", games);
        Highlights.Clear();
        Highlights.Add(new("TOTAL", stats));
        Highlights.Add(new("MOST PLAYED", Describe(decks.OrderByDescending(g => g.Count).FirstOrDefault())));
        Highlights.Add(new("BEST PERFORMING", Describe(decks.OrderByDescending(Performance).FirstOrDefault())));
        Highlights.Add(new("FASTEST", Describe(decks.Where(g => g.Count > 1).OrderBy(g => g.Average(x => x.TurnCount)).FirstOrDefault())));
        Highlights.Add(new("SLOWEST", Describe(decks.Where(g => g.Count > 1).OrderByDescending(g => g.Average(x => x.TurnCount)).FirstOrDefault())));
        static ChartBar WinrateBar(string label, IEnumerable<DashboardMatchItemViewModel> games)
        {
            var decidedGames = games.Where(x => x.Source.Result is "WIN" or "LOSS").ToList();
            return new ChartBar(label, decidedGames.Count(x => x.Source.Result == "WIN"), decidedGames.Count);
        }
        WinrateAsClass.Clear(); WinrateAgainstClass.Clear(); WinrateByCoin.Clear();
        foreach (var cardClass in MatchupMatrixRow.Classes)
        {
            WinrateAsClass.Add(WinrateBar(cardClass, rows.Where(x => x.PlayerClass == cardClass)));
            WinrateAgainstClass.Add(WinrateBar(cardClass, rows.Where(x => x.OpponentClass == cardClass)));
        }
        WinrateByCoin.Add(WinrateBar("Total", rows));
        WinrateByCoin.Add(WinrateBar("Without Coin", rows.Where(x => x.Initiative == "First")));
        WinrateByCoin.Add(WinrateBar("With Coin", rows.Where(x => x.Initiative == "Second")));
        DeckStatistics.Clear();
        DeckMatchups.Clear();
        foreach(var group in rows.GroupBy(x => (x.DeckKey, x.DeckVersion)).OrderByDescending(x=>x.Count()))
        {
            DeckStatistics.Add(new DeckStatistics(group.First().DisplayDeckName, group.Key.DeckVersion, group.ToList()));
            var version = group.Key.DeckVersion;
            DeckMatchups.Add(new MatchupMatrixRow(group.First().DisplayDeckName + (version.Length > 0 ? " · " + version[..Math.Min(8, version.Length)] : ""), group.ToList()));
        }
        Results.Clear();
        var decided = rows.Count(x => x.Source.Result is "WIN" or "LOSS");
        Results.Add(new ChartBar("Wins", rows.Count(x => x.Source.Result == "WIN"), decided));
        Results.Add(new ChartBar("Losses", rows.Count(x => x.Source.Result == "LOSS"), decided));
        Opponents.Clear(); Initiatives.Clear();
        foreach(var group in rows.GroupBy(x=>x.OpponentLabel).OrderByDescending(x=>x.Count())) Opponents.Add(Breakdown(group.Key,group.ToList()));
        foreach(var group in rows.GroupBy(x=>x.Initiative)) Initiatives.Add(Breakdown(group.Key,group.ToList()));
        MatchupMatrix.Clear();
        foreach(var group in rows.GroupBy(x=>x.PlayerClass).OrderBy(x=>x.Key)) MatchupMatrix.Add(new MatchupMatrixRow(group.Key,group.ToList()));
        PlayedClasses.Clear(); OpponentClasses.Clear(); WinrateHistory.Clear();
        foreach(var group in rows.GroupBy(x=>x.PlayerClass).OrderByDescending(x=>x.Count())) PlayedClasses.Add(new ChartBar(group.Key,group.Count(),rows.Count));
        foreach(var group in rows.GroupBy(x=>x.OpponentLabel).OrderByDescending(x=>x.Count())) OpponentClasses.Add(new ChartBar(group.Key,group.Count(),rows.Count));
        foreach(var group in rows.Where(x=>x.Timestamp.HasValue).GroupBy(x=>x.Timestamp!.Value.LocalDateTime.Date).OrderBy(x=>x.Key))
        {
            var dayDecided=group.Count(x=>x.Source.Result is "WIN" or "LOSS");
            WinrateHistory.Add(new ChartBar(group.Key.ToString("MMM d"),group.Count(x=>x.Source.Result=="WIN"),dayDecided));
        }
        Mulligans.Clear();
        foreach(var card in rows.SelectMany(x=>x.Source.MulliganOffered).Distinct().OrderBy(x=>x))
        {
            var kept=rows.Where(x=>x.Source.MulliganKept.Contains(card)).ToList();
            var replaced=rows.Where(x=>x.Source.MulliganReplaced.Contains(card)).ToList();
            Mulligans.Add(new DashboardMulliganCardItemViewModel { CardName=card, OfferedGames=rows.Count(x=>x.Source.MulliganOffered.Contains(card)), KeptGames=kept.Count, ReplacedGames=replaced.Count, KeptRecord=new DeckStatistics("","",kept).Record, ReplacedRecord=new DeckStatistics("","",replaced).Record });
        }
    }
    private static DashboardBreakdownItemViewModel Breakdown(string name, List<DashboardMatchItemViewModel> rows)
    {
        var stats=new DeckStatistics(name,"",rows);
        return new() { Label=name, Games=rows.Count, Record=stats.Record, WinRate=stats.WinRate, AverageDuration=stats.AverageDuration };
    }
    public event PropertyChangedEventHandler? PropertyChanged;
    private bool Set<T>(ref T field,T value,[CallerMemberName]string? propertyName=null){if(EqualityComparer<T>.Default.Equals(field,value))return false;field=value;OnPropertyChanged(propertyName);return true;}
    private void OnPropertyChanged([CallerMemberName]string? propertyName=null)=>PropertyChanged?.Invoke(this,new PropertyChangedEventArgs(propertyName));
}

public sealed record DeckHighlight(string Title, DeckStatistics Stats);

public sealed class DeckStatistics
{
    public string Name { get; }
    public string Version { get; }
    public string Class { get; }
    public string Type { get; }
    public int Games { get; }
    public string Record { get; }
    public string WinRate { get; }
    public string AverageDuration { get; }
    public string AverageTurns { get; }
    public string TotalTime { get; }
    public string BestMatchup { get; }
    public string WorstMatchup { get; }
    public DeckStatistics(string name,string version,List<DashboardMatchItemViewModel> rows)
    {
        Name=name; Version=version.Length>8?version[..8]:version;
        Class=rows.FirstOrDefault()?.PlayerClass ?? "";
        Type=rows.FirstOrDefault()?.ArchetypeName is { Length: >0 } type ? type : "Unclassified";
        Games=rows.Count;
        var wins=rows.Count(x=>x.Source.Result=="WIN"); var losses=rows.Count(x=>x.Source.Result=="LOSS");
        Record=$"{wins}-{losses}"; WinRate=wins+losses>0?$"{100.0*wins/(wins+losses):0.0}%":"—";
        var durations=rows.Where(x=>x.Source.DurationSeconds>0).Select(x=>(double)x.Source.DurationSeconds).ToList();
        AverageDuration=durations.Count>0?$"{durations.Average()/60:0.0} min":"—";
        var turns=rows.Where(x=>x.TurnCount>0).Select(x=>(double)x.TurnCount).ToList();
        AverageTurns=turns.Count>0?$"{turns.Average():0.0}":"—";
        TotalTime=$"{durations.Sum()/3600:0.0} h";
        var matchups=rows.Where(x=>x.Source.Result is "WIN" or "LOSS").GroupBy(x=>x.OpponentLabel)
            .Select(g=>new { Name=g.Key, Wins=g.Count(x=>x.Source.Result=="WIN"), Losses=g.Count(x=>x.Source.Result=="LOSS"), Rate=g.Count(x=>x.Source.Result=="WIN")/(double)g.Count() }).ToList();
        var best=matchups.OrderByDescending(x=>x.Rate).ThenBy(x=>x.Losses).ThenByDescending(x=>x.Wins).FirstOrDefault();
        var worst=matchups.OrderBy(x=>x.Rate).ThenByDescending(x=>x.Losses).ThenBy(x=>x.Wins).FirstOrDefault();
        BestMatchup=best is null?"—":$"{best.Name} · {best.Wins}-{best.Losses} ({best.Rate:0%})";
        WorstMatchup=worst is null?"—":$"{worst.Name} · {worst.Wins}-{worst.Losses} ({worst.Rate:0%})";
    }
}
public sealed class MatchupMatrixRow
{
    public static readonly string[] Classes={"DEATHKNIGHT","DEMONHUNTER","DRUID","HUNTER","MAGE","PALADIN","PRIEST","ROGUE","SHAMAN","WARLOCK","WARRIOR"};
    public string Class { get; }
    public List<string> Cells { get; } = new();
    public MatchupMatrixRow(string player,List<DashboardMatchItemViewModel> rows)
    {
        Class=player;
        foreach(var opponent in Classes)
        {
            var games=rows.Where(x=>x.OpponentClass==opponent).ToList();
            var stats=new DeckStatistics("","",games);
            Cells.Add(games.Count==0?"—":$"{stats.Record}\n{stats.WinRate}");
        }
    }
}
public sealed class ChartBar
{
    public string Label { get; }
    public double Percent { get; }
    public string Detail { get; }
    public Avalonia.Media.IBrush Color => Avalonia.Media.Brush.Parse(Label.Replace(" ", "").ToUpperInvariant() switch
    {
        "WINS" => "#78BEAE", "LOSSES" => "#CF7785", "DEATHKNIGHT" => "#A9455C", "DEMONHUNTER" => "#67A641",
        "DRUID" => "#DC9444", "HUNTER" => "#8AB75E", "MAGE" => "#66BBDD", "PALADIN" => "#DBB95A",
        "PRIEST" => "#CCD3D9", "ROGUE" => "#D7C878", "SHAMAN" => "#547ECA", "WARLOCK" => "#A986BE",
        "WARRIOR" => "#B4866D", _ => "#82909D"
    });
    public ChartBar(string label,int value,int total) { Label=label; Percent=total>0?100.0*value/total:0; Detail=total>0?$"{value}/{total} · {Percent:0.0}%":"—"; }
}
