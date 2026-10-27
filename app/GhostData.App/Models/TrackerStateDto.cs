using System.Text.Json.Serialization;

namespace GhostData.App.Models;

public sealed class TrackerStateDto
{
    [JsonPropertyName("player_hand")] public List<HandSlotDto> PlayerHand { get; set; } = new();
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; }

    [JsonPropertyName("revision")]
    public int Revision { get; set; }

    [JsonPropertyName("game_number")]
    public int GameNumber { get; set; }

    [JsonPropertyName("active")]
    public bool Active { get; set; }

    [JsonPropertyName("complete")]
    public bool Complete { get; set; }

    [JsonPropertyName("source_status")]
    public string SourceStatus { get; set; } = "WAITING";

    [JsonPropertyName("player_deck_hash")]
    public string PlayerDeckHash { get; set; } = "";

    [JsonPropertyName("player_deck_name")]
    public string PlayerDeckName { get; set; } = "";

    [JsonPropertyName("player_class")]
    public string PlayerClass { get; set; } = "";

    [JsonPropertyName("starting_cards")]
    public int StartingCards { get; set; }

    [JsonPropertyName("original_cards_remaining")]
    public int OriginalCardsRemaining { get; set; }

    [JsonPropertyName("player_hand_count")]
    public int? PlayerHandCount { get; set; }

    [JsonPropertyName("player_deck_count")]
    public int? PlayerDeckCount { get; set; }

    [JsonPropertyName("player_known_non_original_in_deck")]
    public int PlayerKnownNonOriginalInDeck { get; set; }

    [JsonPropertyName("player_accounting_delta")]
    public int? PlayerAccountingDelta { get; set; }

    [JsonPropertyName("player_accounting_status")]
    public string PlayerAccountingStatus { get; set; } = "UNAVAILABLE";

    [JsonPropertyName("player_rows")]
    public List<PlayerDeckRowDto> PlayerRows { get; set; } = new();

    [JsonPropertyName("player_extra_deck_rows")]
    public List<PlayerExtraDeckRowDto> PlayerExtraDeckRows { get; set; } = new();

    [JsonPropertyName("opponent_class")]
    public string OpponentClass { get; set; } = "";

    [JsonPropertyName("opponent_hand_count")]
    public int? OpponentHandCount { get; set; }

    [JsonPropertyName("opponent_deck_count")]
    public int? OpponentDeckCount { get; set; }

    [JsonPropertyName("opponent_rows")]
    public List<OpponentObservedRowDto> OpponentRows { get; set; } = new();

    [JsonPropertyName("player_hero_zone_effects")]
    public List<HeroZoneEffectRowDto> PlayerHeroZoneEffects { get; set; } = new();

    [JsonPropertyName("opponent_hero_zone_effects")]
    public List<HeroZoneEffectRowDto> OpponentHeroZoneEffects { get; set; } = new();

    [JsonPropertyName("secret_reads")]
    public List<SecretReadSlotDto> SecretReads { get; set; } = new();

    [JsonPropertyName("unknown_provenance_events")]
    public int UnknownProvenanceEvents { get; set; }

    [JsonPropertyName("player_display_rows")] public List<RailCardRowDto> PlayerDisplayRows { get; set; } = new();
    [JsonPropertyName("opponent_display_rows")] public List<RailCardRowDto> OpponentDisplayRows { get; set; } = new();
    [JsonPropertyName("player_sideboard_rows")] public List<RailCardRowDto> PlayerSideboardRows { get; set; } = new();
    [JsonPropertyName("player_overdraw_rows")] public List<RailCardRowDto> PlayerOverdrawRows { get; set; } = new();
    [JsonPropertyName("opponent_overdraw_rows")] public List<RailCardRowDto> OpponentOverdrawRows { get; set; } = new();
    [JsonPropertyName("opponent_hand")] public List<HandSlotDto> OpponentHand { get; set; } = new();
    [JsonPropertyName("player_fatigue")] public int PlayerFatigue { get; set; }
    [JsonPropertyName("opponent_fatigue")] public int OpponentFatigue { get; set; }
    [JsonPropertyName("player_portal")] public bool PlayerPortal { get; set; }
    [JsonPropertyName("opponent_portal")] public bool OpponentPortal { get; set; }

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; set; } = new();
}

public sealed class SecretReadSlotDto
{
    [JsonPropertyName("candidate_cards")] public List<SecretCandidateDto> CandidateCards { get; set; } = new();
    [JsonPropertyName("eliminated_cards")] public List<SecretCandidateDto> EliminatedCards { get; set; } = new();
    [JsonPropertyName("entity_id")] public int EntityId { get; set; }
    [JsonPropertyName("secret_class")] public string SecretClass { get; set; } = "";
    [JsonPropertyName("candidate_names")] public List<string> CandidateNames { get; set; } = new();
    [JsonPropertyName("eliminated_names")] public List<string> EliminatedNames { get; set; } = new();
    [JsonPropertyName("candidate_count")] public int CandidateCount { get; set; }
    [JsonPropertyName("eliminated_count")] public int EliminatedCount { get; set; }
    [JsonPropertyName("candidate_scope")] public string CandidateScope { get; set; } = "";
    [JsonPropertyName("inference_status")] public string InferenceStatus { get; set; } = "ACTIVE";
    [JsonPropertyName("generated")] public bool Generated { get; set; }
}

public sealed class SecretCandidateDto
{
    [JsonPropertyName("card_id")] public string CardId { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("text")] public string Text { get; set; } = "";
}

public sealed class PlayerDeckRowDto
{
    [JsonPropertyName("dbf_id")]
    public int DbfId { get; set; }

    [JsonPropertyName("card_id")]
    public string CardId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("cost")]
    public int? Cost { get; set; }

    [JsonPropertyName("initial_copies")]
    public int InitialCopies { get; set; }

    [JsonPropertyName("remaining_copies")]
    public int RemainingCopies { get; set; }

    [JsonPropertyName("seen_copies")]
    public int SeenCopies { get; set; }

    [JsonPropertyName("drawn_copies")]
    public int DrawnCopies { get; set; }
}

public sealed class PlayerExtraDeckRowDto
{
    [JsonPropertyName("card_id")]
    public string CardId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("cost")]
    public int? Cost { get; set; }

    [JsonPropertyName("copies_in_deck")]
    public int CopiesInDeck { get; set; }

    [JsonPropertyName("provenance")]
    public string Provenance { get; set; } = "UNKNOWN";

    [JsonPropertyName("card_type")]
    public string CardType { get; set; } = "";

    [JsonPropertyName("spell_school")]
    public string SpellSchool { get; set; } = "";
}


public sealed class OpponentObservedRowDto
{
    [JsonPropertyName("dbf_id")]
    public int? DbfId { get; set; }

    [JsonPropertyName("card_id")]
    public string CardId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("cost")]
    public int? Cost { get; set; }

    [JsonPropertyName("observed_copies")]
    public int ObservedCopies { get; set; }

    [JsonPropertyName("known_in_hand")]
    public int KnownInHand { get; set; }

    [JsonPropertyName("last_zone")]
    public string LastZone { get; set; } = "";

    [JsonPropertyName("provenance")]
    public string Provenance { get; set; } = "UNKNOWN";

    [JsonPropertyName("card_type")]
    public string CardType { get; set; } = "";

    [JsonPropertyName("spell_school")]
    public string SpellSchool { get; set; } = "";

    [JsonPropertyName("hero_zone_kind")]
    public string HeroZoneKind { get; set; } = "";
}

public sealed class HeroZoneEffectRowDto
{
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("entity_id")]
    public int EntityId { get; set; }

    [JsonPropertyName("owner")]
    public string Owner { get; set; } = "";

    [JsonPropertyName("kind")]
    public string Kind { get; set; } = "";

    [JsonPropertyName("card_id")]
    public string CardId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("known")]
    public bool Known { get; set; }

    [JsonPropertyName("cost")]
    public int? Cost { get; set; }

    [JsonPropertyName("spell_school")]
    public string SpellSchool { get; set; } = "";

    [JsonPropertyName("progress")]
    public int? Progress { get; set; }

    [JsonPropertyName("progress_total")]
    public int? ProgressTotal { get; set; }

    [JsonPropertyName("candidate_count")]
    public int CandidateCount { get; set; }

    [JsonPropertyName("provenance")]
    public string Provenance { get; set; } = "UNKNOWN";
}


public sealed class RailCardRowDto
{
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("card_id")] public string CardId { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("cost")] public int? Cost { get; set; }
    [JsonPropertyName("count")] public int Count { get; set; }
    [JsonPropertyName("zone")] public string Zone { get; set; } = "";
    [JsonPropertyName("provenance")] public string Provenance { get; set; } = "";
    [JsonPropertyName("in_hand")] public int InHand { get; set; }
    [JsonPropertyName("state")] public string State { get; set; } = "";
    [JsonPropertyName("exhausted")] public bool Exhausted { get; set; }
    [JsonPropertyName("draw_chance")] public double? DrawChance { get; set; }
}
public sealed class HandSlotDto
{
    [JsonPropertyName("entity_id")] public int EntityId { get; set; }
    [JsonPropertyName("related_cards")] public List<RelatedCardDto> RelatedCards { get; set; } = new();
    [JsonPropertyName("related_label")] public string RelatedLabel { get; set; } = "";
    [JsonPropertyName("related_kind")] public string RelatedKind { get; set; } = "";
    [JsonPropertyName("card_id")] public string CardId { get; set; } = "";
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("position")] public int Position { get; set; }
    [JsonPropertyName("turn")] public int Turn { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "Unknown card";
    [JsonPropertyName("origin")] public string Origin { get; set; } = "";
    public string Label => $"{Position} · T{(Turn + 1) / 2} · {Origin.ToLowerInvariant()} · {Name}";
}

public sealed class RelatedCardDto
{
    [JsonPropertyName("card_id")] public string CardId { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("count")] public int Count { get; set; } = 1;
}
