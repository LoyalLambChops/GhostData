using GhostData.App.Models;
using GhostData.App.ViewModels;
using GhostData.App.Services;
using Avalonia;

static void Check(bool value, string message)
{
    if (!value) throw new Exception(message);
}

Check(CardTextFormatter.Format("In 1 turn, Steal 2 cards from your opponent's hand. Restore #12 Health to your hero.")
    == "In 1 turn, Steal 2 cards from your opponent's hand. Restore 12 Health to your hero.", "Resolved modular objective text has no game formatting markers");

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

Check(CardTextFormatter.Format("[x]<b>Battlecry:</b>_Deal $3 damage.&\nRestore #2 Health.")=="Battlecry: Deal 3 damage.\nRestore 2 Health.","Strip layout and numeric markers");
Check(CardTextFormatter.Format("A &amp; B<br/>C")=="A & B\nC","Preserve literal punctuation and line breaks");
Check(CardTextFormatter.Format("Destroy a minion.@ <i>({0} left!)</i>")=="Destroy a minion.","Do not concatenate description variants");
Check(!CardTextFormatter.Format("Cast @ |4(spell,spells)").Contains('@'),"Never expose unresolved template syntax");
var handState=new TrackerStateDto {Active=true,PlayerHand=new(){new(){EntityId=20,CardId="CAP_805t",Name="Ectoplasm",Text="Resummon minions.",RelatedLabel="Stored minions",RelatedCards=new(){new(){CardId="A",Name="A"},new(){CardId="A",Name="A"}}}}};
Check(RailHoverPreview.ResolveHand(handState,20,"CAP_805t") is not null && RailHoverPreview.ResolveHand(handState,21,"CAP_805t") is null,"Hover resolves entity not name");
Check(RailHoverPreview.ResolveHand(handState,20,"WRONG") is null,"Stale transformed card rejected");
Check(RailHoverPreview.HandDetail(handState.PlayerHand[0],"Deal 7 damage.").Contains("Deal 7 damage."),"Rendered wording wins");
Check(RailHoverPreview.HandDetail(handState.PlayerHand[0],null).Split("• A").Length==3,"Related duplicates retained");
handState.Complete=true;Check(RailHoverPreview.ResolveHand(handState,20,"CAP_805t") is null,"Completed match hover cleared");
Console.WriteLine("Passed 9 card text and hand-preview checks.");

var effectSlot = new HandSlotDto {EntityId=41,CardId="CAP_805t",Name="Ectoplasm",Text="SOURCE DESCRIPTION MUST NOT APPEAR",RelatedKind="STORED",RelatedLabel="Stored minions",RelatedCards=new(){new(){CardId="A",Name="First minion",Text="[x]<b>Taunt</b>"},new(){CardId="A",Name="First minion",Text="[x]<b>Taunt</b>"},new(){CardId="B",Name="Second minion",Text="Deal $3 damage."}}};
var effectDetail = RailHoverPreview.HandEffectDetail(effectSlot);
Check(!effectDetail.Contains("SOURCE DESCRIPTION"),"Game hand popup omits the hovered card description");
Check(effectDetail.Split("• First minion").Length==3 && effectDetail.LastIndexOf("First minion") < effectDetail.IndexOf("Second minion"),"Stored results retain duplicates and order");
Check(effectDetail.Contains("Taunt") && effectDetail.Contains("Deal 3 damage.") && !effectDetail.Contains("<b>") && !effectDetail.Contains("[x]"),"Result cards use cleaned local card text");
Check(RailHoverPreview.HandDetail(effectSlot,"Current rail description").Contains("Current rail description"),"Rail hover retains current full description");
Check(RailHoverPreview.HandEffectDetail(new(){CardId="FIREBALL",Text="Deal 6 damage."})=="","Ordinary game-hand cards do not spawn a popup");
Check(RailHoverPreview.HandEffectDetail(new(){RelatedKind="STORED",RelatedLabel="No minions stored"})=="","Empty stored pools do not spawn blank popups");
Check(RailHoverPreview.HandEffectDetail(null)=="","Missing hand entity hides effect popup");
foreach(var excludedKind in new[]{"DECK","DISCOVER","HISTORY","SELF","TARGET","RETURN","COPY","GENERATED",""})
{
    effectSlot.RelatedKind=excludedKind;
    Check(RailHoverPreview.HandEffectDetail(effectSlot)=="","Hand preview excludes unrelated context: "+excludedKind);
}
effectSlot.RelatedKind="RESULT";
Check(RailHoverPreview.HandEffectDetail(effectSlot).Contains("First minion"),"Summon/replay results remain eligible");
var separateHand = new TrackerStateDto {Active=true,PlayerHand=new(){effectSlot,new(){EntityId=42,CardId="CAP_805t",RelatedKind="STORED",RelatedCards=new(){new(){CardId="C",Name="Other cast minion"}}}}};
Check(!RailHoverPreview.HandEffectDetail(RailHoverPreview.ResolveHand(separateHand,41,"CAP_805t")).Contains("Other cast minion") && RailHoverPreview.HandEffectDetail(RailHoverPreview.ResolveHand(separateHand,42,"CAP_805t")).Contains("Other cast minion"),"Same-card hand copies use separate stored effects");
Console.WriteLine("Passed 18 effect-only hand-preview checks.");
