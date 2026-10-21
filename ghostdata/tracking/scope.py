def is_standard_constructed(format_type: str | None, game_type: str | None) -> bool:
    """Allow legacy records without mode tags; reject explicit non-Standard modes."""
    return str(format_type or "").upper() in {"", "STANDARD", "FT_STANDARD"} and str(game_type or "").upper() in {
        "", "GT_RANKED", "GT_CASUAL", "GT_VS_FRIEND", "GT_FRIENDLY",
    }
