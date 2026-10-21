"""Maintainer packaging helper; does not download or include game content."""
import hashlib
import json
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
sys.dont_write_bytecode = True
from ghostdata import __version__
from ghostdata.updates import validate_package
files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'ghostdata-release.json'}
(root / 'ghostdata-release.json').write_text(json.dumps(dict(product='GhostData', version=__version__, files=files), indent=2), encoding='utf-8')
validate_package(root, __version__)
print(f'Validated {len(files)} files; {sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) / 1048576:.1f} MiB unpacked.')
