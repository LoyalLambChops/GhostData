using GhostData.App.Models;
using GhostData.App.ViewModels;
using GhostData.App.Services;
using Avalonia;

static void Check(bool value, string message)
{
    if (!value) throw new Exception(message);
}

var snapshot = new DashboardSnapshotDto
{
    RecentMatches = new()
    {
        new() { MatchId="1", DeckId="a", DeckName="Mage A", PlayerClass="MAGE", OpponentClass="PRIEST", Result="WIN", ResultLabel="Win", DurationSeconds=600, TurnCount=12, DeckVersion="abcdefgh111", InitiativeLabel="First" },
        new() { MatchId="2", DeckId="a", DeckName="Mage A", PlayerClass="MAGE", OpponentClass="PRIEST", Result="TIE", ResultLabel="Tie", DurationSeconds=300, TurnCount=6, DeckVersion="abcdefgh222", InitiativeLabel="Second" },
        new() { MatchId="3", DeckId="b", DeckName="Priest B", PlayerClass="PRIEST", OpponentClass="MAGE", Result="LOSS", ResultLabel="Loss", DurationSeconds=900, TurnCount=18, InitiativeLabel="Second" }
    }
};
var vm = new DashboardViewModel();
vm.Apply(snapshot);
Check(vm.Games == "3" && vm.WinRate == "50.0%", "Tie denominator");
Check(vm.DeckStatistics.Count == 3, "Full version identity");
Check(vm.DeckMatchups.Count == 3 && vm.DeckMatchups[0].Cells.Count == 11, "Deck-by-class matrix");
Check(vm.Results[0].Percent == 50 && vm.Results[1].Percent == 50, "Chart excludes ties");
Check(vm.Highlights.Count == 5 && vm.Highlights[1].Stats.Name == "Mage A" && vm.Highlights[3].Stats.Name == "Mage A", "Deck highlights aggregate versions and require two games for speed");
Check(vm.WinrateAsClass.Single(x => x.Label == "MAGE").Percent == 100 && vm.WinrateByCoin.Single(x => x.Label == "Without Coin").Percent == 100, "Class and coin win rates");
vm.SelectedDeckFilter = "Mage A";
Check(vm.Games == "2" && vm.Record == "1-0" && vm.WinRate == "100.0%", "Filter summary");
Check(vm.Opponents.Count == 1 && vm.MatchupMatrix.Count == 1, "Filter breakdowns");
Check(vm.AverageTurns == "9.0", "Average turns");
vm.Apply(snapshot);
Check(vm.SelectedDeckFilter == "Mage A" && vm.Games == "2", "Refresh preserves selection");
vm.SelectedVersionFilter = "abcdefgh111";
Check(vm.Games == "1", "Full hash filter");
vm.SelectedResultFilter = "Loss";
Check(vm.Games == "0" && vm.WinRate == "—" && vm.DeckStatistics.Count == 0, "Empty filter");
Check(vm.Highlights[1].Stats.Name == "—" && vm.WinrateAsClass.All(x => x.Percent == 0), "Empty highlight and chart filters");
var state = new TrackerStateDto
{
    PlayerDisplayRows = new() { new() { Name="Depleted", Count=0, Exhausted=true }, new() { Name="Held", Count=0, Exhausted=true, InHand=1 } },
    PlayerHeroZoneEffects = new() { new() { Kind="SECRET", Known=true, Name="Secret" }, new() { Kind="QUEST", Known=true, Name="Quest", Progress=2, ProgressTotal=5 } },
    SecretReads = new() { new() { CandidateCount=7, CandidateNames=new() { "A","B","C","D","E","F","G" }, EliminatedNames=new() { "H" } } }
};
var rail = new PlayerRailViewModel(); rail.Apply(state);
Check(rail.DisplayCards.Count == 2 && rail.DisplayCards[0].Opacity < 1 && rail.DisplayCards[1].Opacity == 1, "Depleted/hand presentation");
Check(rail.HeroZoneEffects.Count == 1 && rail.HeroZoneEffects[0].Detail.Contains("2/5"), "Quest preserved and secrets separated");
var secrets = new SecretRailViewModel(); secrets.Apply(state);
Check(secrets.PlayerSecrets.Count == 1 && secrets.OpponentSecrets[0].Candidates.Count == 7, "Secret separation and no truncation");
Check(secrets.OpponentSecrets[0].Eliminated.Single() == "H", "Eliminated secret presentation");
state.PlayerHeroZoneEffects.Clear(); state.SecretReads.Clear(); secrets.Apply(state);
Check(!secrets.HasSecrets, "Resolved secrets hide overlay");
Check(RailHoverPreview.CardFor(new HeroZoneEffectViewModel(new() {CardId="SECRET",Known=false})).Id == "", "Hidden secrets have no hover identity");
Check(RailHoverPreview.CardFor(new HandSlotDto {Name="Unknown card"}).Id == "", "Unknown hand has no hover identity");
Check(RailHoverPreview.CardFor(new SecretCandidateViewModel("CANDIDATE","Possible", "Text")).Id == "CANDIDATE", "Candidates preview their possible card");
Check(RailHoverPreview.Position(new PixelRect(2200,100,288,1000),new PixelRect(0,0,2560,1400),new PixelSize(300,450),1300)==new PixelPoint(1892,950),"Right hover opens inward and clamps bottom");
Check(RailHoverPreview.Position(new PixelRect(-1900,100,360,1100),new PixelRect(-1920,0,1920,1080),new PixelSize(375,563),-100)==new PixelPoint(-1532,0),"Left hover with scaling and negative monitor coordinates");
state.PlayerPortal=true;state.PlayerDeckCount=0;rail.Apply(state);
Check(rail.CountLine.Contains("∞") && rail.FatigueLine=="", "Portal hides finite deck and fatigue");
Console.WriteLine("Passed 24 dashboard, rail and hover contract checks.");
LayoutChecks.Run();
state.PlayerOverdrawRows.Add(new(){CardId="EXAMPLE",Name="Recoverable card",Cost=2,Count=1,Zone="OVERDRAW",State="AWAITING SPACE",Text="Local rules"});
rail.Apply(state);
Check(rail.HasOverdraw && rail.Overdraw.Single().Detail=="AWAITING SPACE", "Separate overdraw section");
Check(RailHoverPreview.CardFor(rail.Overdraw.Single()).Id=="EXAMPLE", "Recoverable card hover");
state.PlayerOverdrawRows.Clear();rail.Apply(state);
Check(!rail.HasOverdraw, "Empty overdraw section disappears");
Console.WriteLine("Passed 3 recoverable-overdraw UI checks.");

if (OperatingSystem.IsWindows())
{
    var id = Guid.NewGuid().ToString("N");
    using (var primary = new SingleInstance("Local\\GhostData.Test." + id, "Local\\GhostData.Test.Activate." + id))
    {
        Check(primary.IsPrimary, "First instance owns the session");
        using var activated = new ManualResetEventSlim();
        primary.OnActivate(() => activated.Set());
        using var duplicate = new SingleInstance("Local\\GhostData.Test." + id, "Local\\GhostData.Test.Activate." + id);
        Check(!duplicate.IsPrimary, "Second instance cannot start a recorder");
        Check(activated.Wait(TimeSpan.FromSeconds(3)), "Second launch signals the primary window");
    }
    using var restarted = new SingleInstance("Local\\GhostData.Test." + id, "Local\\GhostData.Test.Activate." + id);
    Check(restarted.IsPrimary, "Closed instance releases ownership");
    Console.WriteLine("Passed 4 single-instance lifecycle checks.");
}
