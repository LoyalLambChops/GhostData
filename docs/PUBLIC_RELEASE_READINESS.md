# Public release readiness

Assessment: October 22, 2026. Version 1.3.0 is a locally validated packaging candidate. This checklist separates completed engineering from public-release gates.

## Current state

- The self-contained Windows x64 package already bundles Python and .NET. End users can run `GhostData.App.exe` directly; build scripts are for contributors.
- The .NET 10 candidate payload is approximately 129 MiB unpacked. This is a package-size measurement, not a CPU/RAM performance claim.
- GitHub has no release assets published. The repository is private.
- There is no root project LICENSE. Third-party notices do not license GhostData's own code.
- An unsigned installer candidate is implemented and tested locally. A release CI workflow and publisher signing remain outstanding.
- The Update button supports verified release ZIPs in portable and installed layouts, staging, install-on-exit and startup rollback; uninstall metadata stays outside the swapped payload. Public download/update acceptance is outstanding.
- App screenshots in the README are synthetic-data renders.

## Recommended user experience

1. Click **Download for Windows** in the README to obtain `GhostData-Setup-<version>-x64.exe` from GitHub Releases.
2. Run the installer; install for the current user under `%LOCALAPPDATA%\Programs\GhostData` without requiring administrator privileges for setup.
3. Create the Start Menu shortcut with the embedded GhostData icon; offer a clearly labeled optional Desktop shortcut.
4. Offer **Launch GhostData** on completion. Subsequent launches use the shortcut; no command prompt, build step, SDK or separate Python installation.
5. First-run guidance explains Hearthstone discovery, Power.log configuration, whether the game needs restarting, local card-definition availability and the local data location. Any configuration change should be clear to the user.
6. Keep updates explicitly user initiated. Provide ordinary Windows uninstall support and preserve user match history by default.

Inno Setup is a suitable lightweight installer builder: it supports a single setup EXE, non-administrative installs, shortcuts and uninstall. Keep the portable ZIP as a secondary option.

## Required engineering work

- [x] Versioned Inno Setup definition with stable identity, embedded branded icon, installation checks, shortcut options, launch checkbox and uninstall entry.
- [x] Separate verified `app/` payload from `maintenance/` uninstall files and installation identity. Actual successful and failed-start updates preserve uninstall support without relaxing payload verification.
- [x] Keep `GhostData-win-x64.zip` as the verified payload contract for both layouts; Setup embeds the same payload.
- [x] Keep user data outside program files. Setup, updates and uninstall preserve the external data directory; no data-path migration was introduced.
- [x] Handle a second launch with a named mutex/activation event, restoring and activating the existing dashboard. Ownership/signaling regression checks pass.
- [ ] Provide clear first-run, missing-game, missing-logs, sensor-unavailable and unsupported-game-build states. Avoid silently presenting incomplete accounting as exact.
- [x] Migrate UI and harness to .NET 10, bundle runtime 10.0.13, and validate installed UI plus the regression suites.
- [x] Run separate app/sensor dependency vulnerability scans, including transitive packages. No known vulnerabilities were reported at this validation; repeat during release CI.
- [ ] Keep release builds free of personal logs, data, credentials and private promotional material. Review tracked game-definition/reference files and preserve required third-party licenses.
- [x] Ship a dedicated offline package README referencing the included manuals; repository screenshot links remain in the repository README.

## License and signing decisions

Select a project license before calling the public repository open-source. Making a repository public alone does not grant general reuse rights.

- **MIT:** simple permissive reuse, including proprietary derivatives; attribution/license notices remain required.
- **GPL-3.0:** distributed derivative versions must preserve the applicable source-sharing and same-license obligations. Better aligned if the goal is to keep distributed modifications open. Both licenses allow commercial use; free/open does not prohibit resale.

The copyright holder must choose the license. Review contributions and dependency compatibility, then add LICENSE, source/package metadata, About/license links, and include the license in both installer and portable distributions. Keep third-party/game-content rights separate.

An ordinary desktop EXE can be distributed unsigned, but signing identifies the publisher and protects integrity. For a polished release, sign and timestamp the installer and owned Windows executables before computing final package hashes. Verify signatures in the release pipeline. Signing is not a guarantee that SmartScreen will never warn.

Evaluate SignPath Foundation eligibility for open-source signing, or a trusted commercial signing service/certificate. Approval and identity verification are external prerequisites, not something a build script can manufacture. Do not use a self-signed certificate as the public trust solution.

## Release and acceptance gates

- [ ] Build from a clean tagged checkout in a reproducible, documented Windows CI workflow; run Python and UI regression checks and dependency scans.
- [ ] Sign artifacts, then produce manifests/checksums; create installer and portable assets from the same tested source version.
- [ ] Test installation and launch on a clean supported Windows VM with no development Python or .NET SDK, using a standard user account and paths containing spaces/non-ASCII characters.
- [ ] Repeat Desktop/Start Menu, duplicate-launch, upgrade, failed/interrupted-update and uninstall/reinstall acceptance on a clean VM. Local isolated install, shortcut, reinstall, update-success, startup-rollback and uninstall/data-preservation checks already pass; power-loss and interruption scenarios remain open.
- [ ] Exercise a real downloaded release and update path, including Windows download-origin/security behavior. Do not treat locally copied unsigned builds as equivalent evidence.
- [ ] Complete documented live deck-switch/late-start, reconnect, quest, Secret, overdraw and mixed-DPI/focus tests. See FIELD_TEST_CHECKLIST.md and parity_validation.md.
- [ ] Measure whole-process-tree CPU, RAM and idle behavior before claiming comparative lightweight performance.
- [ ] Confirm normal tracking does not transmit match history; document what UPDATE contacts and what stays local. Diagnostics should be local and any sharing user initiated.
- [ ] Add concise privacy, support, contribution and security-reporting documentation plus issue templates. Separate end-user installation from contributor build instructions.
- [ ] Publish a clearly labeled beta first if live acceptance remains incomplete. Text-only card hover is the current supported feature; locally extracted full-card artwork remains unfinished and must not be advertised as shipped.
- [ ] Resolve the previously removed promotional commit's remaining GitHub cached access before treating those excluded files as local-only in a public repository. Clean branch history alone is not a purge of cached commits.
- [ ] Publish GitHub Release assets with release notes, supported Windows architecture, known limitations, checksums and matching source tag; verify unauthenticated downloads and updater behavior when access is opened.

Do not change repository visibility, buy a certificate, accept signing-service terms, or select a license as an incidental packaging operation.

## References

- Inno Setup capabilities: https://jrsoftware.org/isinfo.php
- GitHub licensing: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- MIT: https://choosealicense.com/licenses/mit/
- GPL-3.0: https://choosealicense.com/licenses/gpl-3.0/
- Windows signing/reputation: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- .NET support: https://dotnet.microsoft.com/en-us/platform/support/policy
- SignPath eligibility: https://signpath.org/terms
- GitHub history/cache limitations: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
