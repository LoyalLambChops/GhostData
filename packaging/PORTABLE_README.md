# GhostData

Developed by LoyalLambChops · LoyalLambChops@gmail.com

## Start

Open GhostData.App.exe, or use the GhostData shortcut if you installed with Setup. No command prompt, SDK or separate Python installation is required. Windows 11 x64 is supported.

The portable ZIP must be fully extracted to a writable folder. Keep its files together.

Start Hearthstone and reach the main menu for local card definitions. Power.log logging must be enabled; see docs/USER_MANUAL.md for setup and troubleshooting.

## Your data

Match history stays in %USERPROFILE%\GhostDataData (unless you explicitly configured GHOSTDATA_DATA_DIR). Updating or uninstalling the app does not erase that folder. Normal tracking does not upload match history.

UPDATE refreshes locally available card definitions and checks the GhostData GitHub release endpoint. A verified engine update installs when you close the dashboard. Installation mode keeps uninstall support separate from the verified app payload. Private/no published releases may report unavailable.

## Help

Read docs/USER_MANUAL.md and docs/TECHNICAL_MANUAL.md. Dependency licenses are in licenses/ and THIRD_PARTY_NOTICES.md. This build is a packaging candidate; public licensing/signing and remaining live acceptance are separate release gates.

Project: https://github.com/LoyalLambChops/GhostData
