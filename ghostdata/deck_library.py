"""Exact local deck versions; never reconstruct lists from observed match cards."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import tempfile
from .paths import data_paths


def save_deck(snapshot, *, data_dir=None):
    from .deck_sensor import _stable_composition_hash
    if snapshot.sensor_status != "EXACT" or snapshot.format != "STANDARD" or not snapshot.selected_deck_id:
        return False
    if not snapshot.cards or any(not isinstance(c,dict) or not c.get("card_id") or type(c.get("count")) is not int or c["count"]<=0 for c in snapshot.cards):
        return False
    if any(not isinstance(c,dict) or not c.get("card_id") or not c.get("owner_card_id") or type(c.get("count")) is not int or c["count"]<=0 for c in snapshot.sideboards):
        return False
    if sum(c["count"] for c in snapshot.cards) not in (20,30):
        return False
    if snapshot.composition_hash != _stable_composition_hash(snapshot.cards,snapshot.sideboards):
        return False
    directory=data_paths(data_dir).root/'deck_library'
    directory.mkdir(exist_ok=True)
    key=sha256((snapshot.selected_deck_id+":"+snapshot.composition_hash).encode()).hexdigest()
    path=directory/(key+'.json')
    payload=asdict(snapshot)
    payload.pop('game_context',None)
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True)
    if path.exists() and path.read_text(encoding='utf-8')==text:
        return False
    fd,tmp=tempfile.mkstemp(dir=directory,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return True


def sync_collection(project_root, *, data_dir=None):
    from .deck_sensor import sensor_executable, _snapshot_from_payload
    try:
        proc=subprocess.run([str(sensor_executable(project_root)),"deck-library","--json"],capture_output=True,text=True,timeout=8,check=False)
        payload=json.loads(proc.stdout or '{}')
        if proc.returncode or payload.get('status')!='OK':return
        for deck in payload.get('decks',[])[:100]:
            snapshot=_snapshot_from_payload(deck)
            if snapshot:save_deck(snapshot,data_dir=data_dir)
    except (OSError,ValueError,TypeError,subprocess.SubprocessError):
        return  # Offline use preserves the previously captured library.


def dashboard_decks(records, *, data_dir=None):
    from .deck_sensor import load_cached_deck, _stable_composition_hash
    from .tracking.card_db import CardDatabase
    from .deck_codes import deck_code
    root=data_paths(data_dir).root
    cached=load_cached_deck(data_dir=data_dir)
    if cached:save_deck(cached,data_dir=data_dir)
    db=CardDatabase(root/'local_cards');db.load_latest_cache()
    output={}
    def card_row(row):
        cid=str(row.get('card_id') or '')
        card=db.get(cid)
        owner=str(row.get('owner_card_id') or '')
        parent=db.get(owner) if owner else None
        return dict(card_id=cid,name=card.name if card else cid,cost=card.cost if card else None,
                    count=int(row['count']),text=card.text if card else '',
                    owner=parent.name if parent else owner)
    for path in sorted((root/'deck_library').glob('*.json')):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            cards=raw['cards']; side=raw.get('sideboards',[])
            version=raw['composition_hash'];deck_id=raw['selected_deck_id']
            if raw.get('sensor_status')!='EXACT' or raw.get('format')!='STANDARD' or version!=_stable_composition_hash(cards,side):continue
            main=sorted((card_row(c) for c in cards),key=lambda c:(c['cost'] if c['cost'] is not None else 999,c['name']))
            output[(deck_id,version)]=dict(key=deck_id+':'+version,deck_id=deck_id,version=version,
                name=raw.get('deck_name') or 'Unnamed deck',player_class=raw.get('player_class',''),
                available=True,cards=main,sideboard=sorted((card_row(c) for c in side),key=lambda c:(c['owner'],c['name'])),
                total=sum(c['count'] for c in main),deck_code=deck_code(raw,db),status='Exact saved composition - card wording from installed game definitions')
        except (OSError,ValueError,KeyError,TypeError):continue
    from .tracking.scope import is_standard_constructed
    for match in records:
        if not is_standard_constructed(match.format,match.game_type):continue
        if not match.deck_id or not match.deck_version:continue
        key=(match.deck_id,match.deck_version)
        if key not in output:
            output[key]=dict(key=':'.join(key),deck_id=match.deck_id,version=match.deck_version,
                name=match.deck_name or match.player_class.title(),player_class=match.player_class,
                available=False,cards=[],sideboard=[],total=0,
                status='This historical version was not captured. Its card list cannot be recovered from match observations.')
    return sorted(output.values(),key=lambda d:(d['name'].casefold(),not d['available'],d['version']))
