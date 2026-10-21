"""Invented parser input; no captured game, player account or local history."""
from pathlib import Path


def completed_match_log() -> str:
    rows: list[str] = []

    def emit(body: str, method: str = "DebugPrintPower", time: str = "12:00:00.000"):
        rows.append(f"D {time} GameState.{method}() - {body}\n")

    def entity(eid: int, card: str, owner: int, zone: str, kind: str = "SPELL"):
        emit(f"FULL_ENTITY - Creating ID={eid} CardID={card}")
        for tag, value in (("CONTROLLER", owner), ("CARDTYPE", kind), ("ZONE", zone)):
            emit(f"tag={tag} value={value}")

    def inline(eid: int, card: str, owner: int, zone: str = "HAND") -> str:
        return f"[entityName={card} id={eid} zone={zone} zonePos=1 cardId={card} player={owner}]"

    emit("CREATE_GAME")
    emit("GameEntity EntityID=1")
    for eid, pid, hero in ((2, 1, 11), (3, 2, 12)):
        emit(f"Player EntityID={eid} PlayerID={pid}")
        emit(f"tag=HERO_ENTITY value={hero}")
    entity(11, "HERO_09", 1, "PLAY", "HERO")
    entity(12, "HERO_07", 2, "PLAY", "HERO")
    emit("TAG_CHANGE Entity=3 tag=FIRST_PLAYER value=1")
    emit("PlayerID=1, PlayerName=SyntheticPlayer", "DebugPrintGame")
    emit("PlayerID=2, PlayerName=SyntheticOpponent", "DebugPrintGame")
    emit("FormatType=FT_STANDARD", "DebugPrintGame")
    emit("GameType=GT_RANKED", "DebugPrintGame")
    for eid in (20, 21, 22):
        entity(eid, f"SYNTHETIC_{eid}", 1, "HAND")
    emit("id=1 Player=SyntheticPlayer TaskList=1 ChoiceType=MULLIGAN CountMin=0 CountMax=3", "DebugPrintEntityChoices")
    for index, eid in enumerate((20, 21, 22)):
        emit(f"Entities[{index}]={inline(eid, f'SYNTHETIC_{eid}', 1)}", "DebugPrintEntityChoices")
    emit("id=1 ChoiceType=MULLIGAN", "SendChoices")
    for index, eid in enumerate((20, 21)):
        emit(f"m_chosenEntities[{index}]={inline(eid, f'SYNTHETIC_{eid}', 1)}", "SendChoices")
    emit("TAG_CHANGE Entity=GameEntity tag=STEP value=MAIN_ACTION")
    emit("TAG_CHANGE Entity=GameEntity tag=TURN value=2")
    entity(30, "SYNTHETIC_DRAW", 1, "DECK")
    emit("TAG_CHANGE Entity=30 tag=ZONE value=HAND")
    emit(f"BLOCK_START BlockType=PLAY Entity={inline(20, 'SYNTHETIC_20', 1)} EffectCardId= EffectIndex=0 Target=0 SubOption=-1")
    emit("TAG_CHANGE Entity=20 tag=ZONE value=GRAVEYARD")
    emit("BLOCK_END")
    emit("TAG_CHANGE Entity=GameEntity tag=TURN value=3")
    entity(40, "SYNTHETIC_OPPONENT_CARD", 2, "HAND")
    emit(f"BLOCK_START BlockType=PLAY Entity={inline(40, 'SYNTHETIC_OPPONENT_CARD', 2)} EffectCardId= EffectIndex=0 Target=0 SubOption=-1")
    emit("BLOCK_END")
    emit("TAG_CHANGE Entity=2 tag=PLAYSTATE value=WON", time="12:02:00.000")
    emit("TAG_CHANGE Entity=3 tag=PLAYSTATE value=LOST", time="12:02:00.000")
    return "".join(rows)


def write_match_log(path: Path) -> None:
    path.write_text(completed_match_log(), encoding="utf-8")
