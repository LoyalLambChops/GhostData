# Third-party notices

## Game content

Hearthstone and its game content belong to Blizzard Entertainment. GhostData
does not ship card artwork or download card images. The current candidate reads
public definitions from the installed Blizzard client and displays text. This does not grant ownership
of, or redistribution rights to, Blizzard content. Local game asset support is
pending implementation and is not claimed as a shipped feature.

## UnitySpy

The selected-deck sensor uses the pinned open-source UnitySpy implementation
under its MIT license. See `sensor/third_party` and the license preserved beside
`sensor/bin/GhostData.Sensor.exe`. This change preserves the existing sensor.

## UI dependencies

Avalonia and its transitive dependencies remain governed by their respective
licenses. The build restores these dependencies. Portable packages preserve the exact
restored packages' license text, notices and attribution under `licenses/`. No browser engine, chart
package or new production dependency was added for text-only rails.

## Sensor dependencies

The packaged sensor also uses JetBrains.Annotations, Newtonsoft.Json and
System.ValueTuple. Their own license and attribution files are collected from
the exact restored NuGet packages under `licenses/`, separately from UnitySpy.
Build-only .NET Framework reference assemblies are not distributed as app runtime files.

## Bundled runtimes

Portable packages include the official Python embeddable runtime and its
LICENSE.txt, plus the self-contained Microsoft .NET runtime and its license
and third-party notices. These are runtime dependencies, not game artwork.
