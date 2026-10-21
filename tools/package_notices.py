"""Collect notices from the exact restored packages used by the portable build."""
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

project, output = map(Path, sys.argv[1:3])
assets = json.loads((project / 'app/GhostData.App/obj/project.assets.json').read_text())
deps = json.loads((output / 'GhostData.App.deps.json').read_text())
roots = [Path(p) for p in assets['packageFolders']]
runtime = json.loads((output / 'GhostData.App.runtimeconfig.json').read_text())
framework = next(f for f in runtime['runtimeOptions']['includedFrameworks'] if f['name'] == 'Microsoft.NETCore.App')
packages = {key: value['path'] for key, value in assets['libraries'].items()
            if value['type'] == 'package' and key in deps['libraries']}
packages['Microsoft.NETCore.App.Runtime.win-x64/' + framework['version']] = (
    'microsoft.netcore.app.runtime.win-x64/' + framework['version'])
mit = (project / 'sensor/vendor/unityspy/LICENSE').read_text(encoding='utf-8')
mit = mit[mit.index('Permission is hereby granted'):]
for name, relative in sorted(packages.items()):
    package = next((root / relative for root in roots if (root / relative).is_dir()), None)
    if package is None:
        raise RuntimeError('Missing restored package: ' + name)
    destination = output / 'licenses' / name.replace('/', '-')
    destination.mkdir(parents=True, exist_ok=True)
    notices = [p for p in package.iterdir() if p.is_file()
               and any(word in p.name.lower() for word in ('license', 'notice', 'copying'))]
    for notice in notices:
        shutil.copyfile(notice, destination / notice.name)
    spec = next(package.glob('*.nuspec'))
    shutil.copyfile(spec, destination / spec.name)
    metadata = ET.parse(spec).getroot()
    values = {node.tag.rsplit('}', 1)[-1]: node.text or '' for node in metadata.iter()}
    if not notices:
        if values.get('license') != 'MIT' or not values.get('copyright'):
            raise RuntimeError('Review missing license text/attribution: ' + name)
        (destination / 'LICENSE.txt').write_text(values['copyright'] + '\n\n' + mit, encoding='utf-8')
print(f'Collected notices for {len(packages)} shipped packages.')
