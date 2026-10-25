"""Bounded release hygiene checks; not a substitute for reviewing Git history."""
import json
from pathlib import Path
import re
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip()
assert re.fullmatch(r'\d+\.\d+\.\d+',version), 'Invalid VERSION'
sys.path.insert(0,str(root))
from ghostdata import __version__
assert version==__version__, 'Python version mismatch'
for name in ['app/GhostData.App/GhostData.App.csproj','sensor/GhostData.Sensor/GhostData.Sensor.csproj']:
    assert f'<Version>{version}</Version>' in (root/name).read_text(), name+' version mismatch'
assert f'SensorVersion = "{version}"' in (root/'sensor/GhostData.Sensor/Program.cs').read_text()
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
for name in filter(None,tracked):
    path=Path(name);parts={part.casefold() for part in path.parts}
    assert not parts.intersection({'media','ghostdatadata','card_art','card_renders','backups','.aws'}), 'Private path tracked: '+name
    assert path.name.casefold() not in {'matches.json','selected_deck.json','settings.json','log.config','.env'}, 'Local data tracked: '+name
    assert path.suffix.casefold() not in {'.log','.bak','.zip','.pfx','.pem','.key'}, 'Unexpected sensitive/archive file: '+name
assert (root/'LICENSE').read_text().startswith('MIT License')
print('Release versions, MIT license and tracked-path hygiene checks passed. History/content review remains separate.')
