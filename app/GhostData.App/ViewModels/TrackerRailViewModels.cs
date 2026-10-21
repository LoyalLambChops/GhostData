using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using GhostData.App.Models;
using GhostData.App.Services;
using Avalonia.Media;

namespace GhostData.App.ViewModels;

public abstract class RailViewModelBase : INotifyPropertyChanged
{
    public ObservableCollection<DisplayCardViewModel> Overdraw { get; } = new();
    private bool _hasOverdraw;
    public bool HasOverdraw { get => _hasOverdraw; private set => Set(ref _hasOverdraw,value); }
    protected void ApplyOverdraw(IEnumerable<RailCardRowDto> rows)
    {
        Overdraw.Clear(); foreach(var row in rows)Overdraw.Add(new DisplayCardViewModel(row));
        HasOverdraw=Overdraw.Count>0;
    }
    public event PropertyChangedEventHandler? PropertyChanged;

    protected void Set<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
            return;
        field = value;
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    protected static string TitleCase(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return "";
        var normalized = value.Replace("_", " ").ToLowerInvariant();
        if (normalized == "demonhunter") normalized = "demon hunter";
        if (normalized == "deathknight") normalized = "death knight";
        return System.Globalization.CultureInfo.InvariantCulture.TextInfo.ToTitleCase(normalized);
    }

    protected static string CountOrQuestion(int? value) => value?.ToString() ?? "?";
}

public sealed class PlayerRailViewModel : RailViewModelBase
{
    private string _deckName = "Your Deck", _classLine = "PLAYER", _countLine = "WAITING FOR EXACT DECK", _accountingText = "", _fatigueLine = "";
    public string DeckName { get => _deckName; private set => Set(ref _deckName,value); }
    public string ClassLine { get => _classLine; private set => Set(ref _classLine,value); }
    public string CountLine { get => _countLine; private set => Set(ref _countLine,value); }
    public string AccountingText { get => _accountingText; private set => Set(ref _accountingText,value); }
    public string FatigueLine { get => _fatigueLine; private set => Set(ref _fatigueLine,value); }
    public ObservableCollection<DisplayCardViewModel> DisplayCards { get; } = new();
    public ObservableCollection<DisplayCardViewModel> Sideboards { get; } = new();
    public ObservableCollection<HeroZoneEffectViewModel> HeroZoneEffects { get; } = new();
    public void Apply(TrackerStateDto state)
    {
        DeckName=string.IsNullOrWhiteSpace(state.PlayerDeckName)?"Your Deck":state.PlayerDeckName;
        ClassLine=TitleCase(state.PlayerClass);
        CountLine=$"DECK {CountOrQuestion(state.PlayerDeckCount)} · HAND {CountOrQuestion(state.PlayerHandCount)}";
        if(state.PlayerPortal)CountLine=$"DECK ∞ · HAND {CountOrQuestion(state.PlayerHandCount)}";
        AccountingText=state.PlayerAccountingStatus switch { "EXACT"=>"SYNCED", "PORTAL"=>"DEMON PORTAL", "PARTIAL"=>$"PARTIAL {state.PlayerAccountingDelta:+0;-0;0}", _=>"" };
        FatigueLine=!state.PlayerPortal && state.PlayerDeckCount==0?$"NEXT FATIGUE {state.PlayerFatigue+1}":"";
        DisplayCards.Clear(); foreach(var row in state.PlayerDisplayRows) DisplayCards.Add(new DisplayCardViewModel(row));
        Sideboards.Clear(); foreach(var row in state.PlayerSideboardRows) Sideboards.Add(new DisplayCardViewModel(row));
        ApplyOverdraw(state.PlayerOverdrawRows);
        HeroZoneEffects.Clear(); foreach(var row in state.PlayerHeroZoneEffects.Where(e=>e.Kind!="SECRET")) HeroZoneEffects.Add(new HeroZoneEffectViewModel(row));
    }
}

public sealed class OpponentRailViewModel : RailViewModelBase
{
    private string _classLine="UNKNOWN CLASS", _countLine="Waiting for match", _fatigueLine="";
    public string ClassLine { get => _classLine; private set => Set(ref _classLine,value); }
    public string CountLine { get => _countLine; private set => Set(ref _countLine,value); }
    public string FatigueLine { get => _fatigueLine; private set => Set(ref _fatigueLine,value); }
    public ObservableCollection<DisplayCardViewModel> DisplayCards { get; } = new();
    public ObservableCollection<HandSlotDto> Hand { get; } = new();
    public ObservableCollection<HeroZoneEffectViewModel> HeroZoneEffects { get; } = new();
    public void Apply(TrackerStateDto state)
    {
        ClassLine=string.IsNullOrWhiteSpace(state.OpponentClass)?"UNKNOWN CLASS":TitleCase(state.OpponentClass).ToUpperInvariant();
        CountLine=$"DECK {CountOrQuestion(state.OpponentDeckCount)} · HAND {CountOrQuestion(state.OpponentHandCount)}";
        if(state.OpponentPortal)CountLine=$"DECK ∞ · HAND {CountOrQuestion(state.OpponentHandCount)}";
        FatigueLine=!state.OpponentPortal && state.OpponentDeckCount==0?$"NEXT FATIGUE {state.OpponentFatigue+1}":"";
        DisplayCards.Clear(); foreach(var row in state.OpponentDisplayRows) DisplayCards.Add(new DisplayCardViewModel(row));
        Hand.Clear(); foreach(var row in state.OpponentHand) Hand.Add(row);
        ApplyOverdraw(state.OpponentOverdrawRows);
        HeroZoneEffects.Clear(); foreach(var row in state.OpponentHeroZoneEffects.Where(e=>e.Kind!="SECRET")) HeroZoneEffects.Add(new HeroZoneEffectViewModel(row));
    }
}

public sealed class SecretReadSlotViewModel
{
    public SecretReadSlotViewModel(SecretReadSlotDto slot)
    {
        var secretClass = string.IsNullOrWhiteSpace(slot.SecretClass) ? "SECRET" : $"{slot.SecretClass.Trim().ToUpperInvariant()} SECRET";
        Label = slot.CandidateCount > 0
            ? $"{secretClass} · {slot.CandidateCount} {(slot.CandidateCount == 1 ? "POSSIBILITY" : "POSSIBILITIES")}"
            : secretClass;
        var status = (slot.InferenceStatus ?? "ACTIVE").Replace("_", " ").Trim();
        if (slot.EliminatedCount > 0)
            Status = $"{status} · {slot.EliminatedCount} ELIMINATED";
        else
            Status = status;

        foreach (var name in slot.CandidateNames.Where(n => !string.IsNullOrWhiteSpace(n)))
            Candidates.Add(name.Trim());
        foreach (var card in slot.CandidateCards) PreviewCandidates.Add(new(card.CardId, card.Name, card.Text));
        if (PreviewCandidates.Count == 0) foreach (var name in Candidates) PreviewCandidates.Add(new("", name, ""));
        foreach (var name in slot.EliminatedNames.Where(n => !string.IsNullOrWhiteSpace(n)))
            Eliminated.Add(name.Trim());
        foreach (var card in slot.EliminatedCards) EliminatedCandidates.Add(new(card.CardId, card.Name, card.Text));
        if (EliminatedCandidates.Count == 0) foreach (var name in Eliminated) EliminatedCandidates.Add(new("", name, ""));

        if (Candidates.Count == 0)
        {
            Candidates.Add("Current options unavailable");
            PreviewCandidates.Add(new("", "Current options unavailable", ""));
        }
    }

    public string Label { get; }
    public string Status { get; }
    public ObservableCollection<string> Candidates { get; } = new();
    public ObservableCollection<string> Eliminated { get; } = new();
    public ObservableCollection<SecretCandidateViewModel> PreviewCandidates { get; } = new();
    public ObservableCollection<SecretCandidateViewModel> EliminatedCandidates { get; } = new();
}

public sealed record SecretCandidateViewModel(string CardId, string Name, string Text);

public sealed class HeroZoneEffectViewModel
{
    public HeroZoneEffectViewModel(HeroZoneEffectRowDto row)
    {
        CardId = row.Known ? row.CardId : "";
        PreviewText = row.Text;
        Kind = string.IsNullOrWhiteSpace(row.Kind) ? "EFFECT" : row.Kind.ToUpperInvariant();
        Name = row.Known && !string.IsNullOrWhiteSpace(row.Name)
            ? row.Name
            : Kind == "SECRET" ? "Unknown Secret" : "Unknown effect";

        var detail = new List<string>();
        if (!string.IsNullOrWhiteSpace(row.SpellSchool))
            detail.Add(row.SpellSchool.ToUpperInvariant());
        if (row.Progress is not null || row.ProgressTotal is not null)
            detail.Add($"{row.Progress?.ToString() ?? "?"}/{row.ProgressTotal?.ToString() ?? "?"}");
        // Secret candidate detail has its own explicit POSSIBLE SECRETS surface
        // in v48.1; avoid duplicating that cognitive load in the observed-effect row.
        if (row.CandidateCount > 0 && !row.Known && Kind != "SECRET")
            detail.Add($"{row.CandidateCount} candidates");
        if (!string.IsNullOrWhiteSpace(row.Provenance) && !row.Provenance.Equals("UNKNOWN", StringComparison.OrdinalIgnoreCase))
            detail.Add(row.Provenance.ToUpperInvariant());
        Detail = string.Join(" · ", detail);
    }

    public string Kind { get; }
    public string CardId { get; }
    public string PreviewText { get; }
    public string Name { get; }
    public string Detail { get; }
}


public sealed class DisplayCardViewModel
{
    public DisplayCardViewModel(RailCardRowDto row)
    {
        CardId = row.CardId;
        PreviewText = row.Text;
        Name = row.Name; Cost = row.Cost?.ToString() ?? "?"; Count = row.Count.ToString();
        Opacity = row.Exhausted && row.InHand == 0 ? 0.38 : 1;
        Accent = new SolidColorBrush(Color.Parse(row.InHand > 0 ? "#86E7C0" : row.State.Contains("BURNED") || row.State.Contains("DISCARDED") ? "#EF9B9B" : "#49BDD3"));
        var detail = new List<string>();
        if (!string.IsNullOrWhiteSpace(row.State)) detail.Add(row.State);
        if (row.Provenance is not ("" or "UNKNOWN" or "ORIGINAL_DECK")) detail.Add(row.Provenance);
        if (row.DrawChance is double chance) detail.Add($"{chance:0.#}% DRAW");
        Detail = string.Join(" · ", detail);
    }
    public string Name { get; }
    public string CardId { get; }
    public string PreviewText { get; }
    public string Cost { get; }
    public string Count { get; }
    public string Detail { get; }
    public double Opacity { get; }
    public IBrush Accent { get; }
}
public sealed class SecretRailViewModel : RailViewModelBase
{
    public ObservableCollection<HeroZoneEffectViewModel> PlayerSecrets { get; } = new();
    public ObservableCollection<SecretReadSlotViewModel> OpponentSecrets { get; } = new();
    public bool HasSecrets => PlayerSecrets.Count + OpponentSecrets.Count > 0;
    public void Apply(TrackerStateDto state)
    {
        PlayerSecrets.Clear(); OpponentSecrets.Clear();
        foreach(var row in state.PlayerHeroZoneEffects.Where(e => e.Kind == "SECRET")) PlayerSecrets.Add(new HeroZoneEffectViewModel(row));
        foreach(var row in state.SecretReads) OpponentSecrets.Add(new SecretReadSlotViewModel(row));
    }
}
