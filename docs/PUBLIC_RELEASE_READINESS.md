# Public release readiness

Assessment: October 27, 2026. The maintainer reports successful clean-machine installation and a completed Standard match on build 1.3.5. Build 1.3.6 is the next beta candidate with expanded deck previews. The release scope prioritizes accurate supported mechanics and hover behavior; turn timers and additional counters follow after beta. Universal feature parity is not a release requirement. Remaining preview limits are explicit in HAND_PREVIEWS.md.

## Current state

- The self-contained Windows x64 package already bundles Python and .NET. End users can run `GhostData.App.exe` directly; build scripts are for contributors.
- The .NET 10 candidate payload is approximately 129 MiB unpacked. This is a package-size measurement, not a CPU/RAM performance claim.
- GitHub has no release assets published. The repository is private.
- MIT was selected by the copyright holder on October 25. LICENSE covers original software, is embedded in the UI and included in both package formats. Third-party components retain their own notices.
- An unsigned installer candidate is implemented and tested locally. The candidate CI workflow passed on a fresh Windows runner; see the recorded evidence below. The maintainer chose an unsigned initial release on October 25; signing is optional future work.
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
- [x] Add first-run SETUP with custom game paths, explicit safe logging edits, sensor availability and missing/expired/mismatched definition checks. Live unsupported mechanics remain partial/unknown; current metadata does not certify complete mechanics support.
- [x] Migrate UI and harness to .NET 10, bundle runtime 10.0.13, and validate installed UI plus the regression suites.
- [x] Run separate app/sensor dependency vulnerability scans, including transitive packages. No known vulnerabilities were reported at this validation; repeat during release CI.
- [x] Extend the exact-package notice collector to include shipped sensor dependencies (JetBrains.Annotations, Newtonsoft.Json and System.ValueTuple), excluding build-only reference assemblies.
- [x] Review current tracked paths and reachable-history paths for private media/data/archives. No matching paths were found on October 27. Candidate CI separately validates shipped inventory and notices. Remote cached commit access remains a separate unresolved privacy gate below.
- [x] Ship a dedicated offline package README referencing the included manuals; repository screenshot links remain in the repository README.

## License and signing decisions

The maintainer selected MIT on October 25. The root LICENSE, C# package metadata, offline dashboard license viewer, portable payload and website reflect this decision. MIT permits modification and commercial reuse with the required notice; no additional anti-modification restrictions are imposed. Third-party and game-content rights remain separate.

The initial release will be unsigned, as chosen by the maintainer on October 25. A code-signing certificate is not a release gate. Clearly label the downloads as unsigned, publish SHA-256 checksums, and test Windows download-origin behavior. Checksums do not authenticate the publisher. SmartScreen may warn, and Smart App Control or managed policies may block execution; do not promise every Windows device can run the unsigned build. Signing identifies a publisher and can help build reputation, but does not guarantee warning-free installation.

Signing can be reconsidered later if installation friction warrants it. No certificate purchase or signing-service enrollment is authorized or required for the initial release.

## Release and acceptance gates

- [x] Build a candidate from a clean Windows CI checkout with dependency audits and Python/UI checks. Manual dispatch has passed; matching numeric tag triggering is implemented, but the first tagged public release remains pending.
- [x] Produce the unsigned installer and portable assets from the same tested source with manifest, checksums, build provenance and an unsigned notice, available as private CI artifacts. Public release publication remains a separate gate below.
- [x] Maintainer-reported install, launch and completed Standard match on a separate clean Windows machine with build 1.3.5. Standard-user/non-ASCII path variants and the new 1.3.6 mechanics were not separately confirmed.
- [ ] Repeat Desktop/Start Menu, duplicate-launch, upgrade, failed/interrupted-update and uninstall/reinstall acceptance on a clean VM. Local isolated install, shortcut, reinstall, update-success, startup-rollback and uninstall/data-preservation checks already pass; power-loss and interruption scenarios remain open.
- [ ] Exercise a real downloaded release and update path, including Windows download-origin/security behavior. Do not treat locally copied unsigned builds as equivalent evidence.
- [ ] Complete documented live deck-switch/late-start, reconnect, quest, Secret, overdraw and mixed-DPI/focus tests. See FIELD_TEST_CHECKLIST.md and parity_validation.md.
- [ ] Measure whole-process-tree CPU, RAM and idle behavior before claiming comparative lightweight performance.
- [ ] Confirm normal tracking does not transmit match history; document what UPDATE contacts and what stays local. Diagnostics should be local and any sharing user initiated.
- [x] Add PRIVACY.md, SUPPORT.md, CONTRIBUTING.md, SECURITY.md and a bug-report template, plus the release runbook. End-user installation is separate from contributor build instructions.
- [ ] Publish a clearly labeled beta first if live acceptance remains incomplete. Text-only card hover is the current supported feature; locally extracted full-card artwork remains unfinished and must not be advertised as shipped.
- [ ] Resolve the previously removed promotional commit's remaining GitHub cached access before treating those excluded files as local-only in a public repository. Clean branch history alone is not a purge of cached commits.
- [ ] Publish GitHub Release assets with release notes, supported Windows architecture, known limitations, checksums and matching source tag; verify unauthenticated downloads and updater behavior when access is opened.

Do not change repository visibility, buy a certificate or accept signing-service terms as an incidental packaging operation.

## References

- Inno Setup capabilities: https://jrsoftware.org/isinfo.php
- GitHub licensing: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- MIT: https://choosealicense.com/licenses/mit/
- GPL-3.0: https://choosealicense.com/licenses/gpl-3.0/
- Windows signing/reputation: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- .NET support: https://dotnet.microsoft.com/en-us/platform/support/policy
- SignPath eligibility: https://signpath.org/terms
- GitHub history/cache limitations: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

## Candidate validation — October 25, 2026

Phantom · Beta 1, build **1.3.2**, source `9cf8bdb5cd90c4d702b593b86b40ae05bac5f0aa` passed [Windows candidate CI run 40237513928](https://github.com/LoyalLambChops/GhostData/actions/runs/40237513928).

- 200 Python regressions and 40 dashboard/rail/lifecycle checks passed.
- Dependency restores with auditing enabled and warnings treated as errors passed.
- Installer creation, shortcut verification, rendered installed UI, reinstall replacement, failed-start rollback, successful update and uninstall/data preservation passed on the runner. The corrected upgrade fixture explicitly models completed onboarding.
- Local native UI inspection confirmed first-run setup reports unavailable game/card states and Save and Close persists settings in an isolated data folder and returns to the dashboard. Synthetic Setup renders were also inspected.
- The exact CI artifacts were downloaded and their checksums/source provenance verified for the maintainer's separate-PC test. No repository visibility or public-release change was made.
- A bounded tracked-text credential-pattern scan found no matches; locally reachable history contained no private-media/data folders. This is not proof that GitHub's remote cached/unreachable commits are purged.

The clean-machine install and Standard-match evidence has since been reported for build 1.3.5. Real public download/update behavior is still outstanding. Windows Server CI is not a substitute for player-machine evidence.


## Build 1.3.3 candidate validation

The private candidate workflow [40371688503](https://github.com/LoyalLambChops/GhostData/actions/runs/40371688503) passed for executable/source commit `f05ff4e0f4aa3fe72782394fd6606ef5e4ca5430`: 211 Python regressions, 49 UI/lifecycle checks, dependency audits, self-contained packaging, installer creation and isolated install/update/rollback/uninstall checks. Exact CI artifacts and checksums were downloaded for maintainer testing. Subsequent commits recording validation evidence change documentation only. Public release remains gated on the remaining HAND_PREVIEWS.md coverage, supported-Standard field acceptance and the existing privacy/history/download checks.

## Coverage development — October 26, 2026

Source candidate 1.3.4 extends stored/history previews and local reference metadata. Validation so far: 238 Python tests, 49 UI checks, successful local metadata import from client 255790 and 12 READY sensor samples at its main menu. Definitions: 36,390; no changes to previously imported card fields compared with 255130. Expanded compact snapshot: 10.63 MiB; artwork remains absent.

Do not publish this candidate solely on those checks. HAND_PREVIEWS.md lists the contracts and limits. The private product audit is outside the repository. Wider feature parity, live Standard acceptance, and the existing public-release gates remain open.


## Build 1.3.4 candidate validation — October 27, 2026

Executable/source commit `8bf0d608057ef189e1c9770c605eb2b6ca6c4335` passed [private Windows candidate workflow 40494601877](https://github.com/LoyalLambChops/GhostData/actions/runs/40494601877). This includes 238 Python regressions, 49 UI/lifecycle checks, dependency auditing, self-contained packaging, installer creation, installed UI rendering and isolated install/update/rollback/uninstall checks. No public release was published and no existing user installation was replaced.

Remaining implementation is broader than live validation: Discover/random generation pool catalogs, filtered deck-tutor previews, generated-card families, and the wider local analytics/utility roadmap remain under review. The definition fingerprint audit and smoke checks do not establish universal mechanic coverage. Keep these implementation gaps separate from live Standard acceptance and public distribution checks.


## Live integration correction — build 1.3.5

The October 27 Practice hover check exposed a friendly-hand identity gate incorrectly consulting an opponent-only observation set. Build 1.3.4's passing component/installer checks did not detect this; do not use its candidate as evidence that live friendly-hand previews work. Build 1.3.5 fixes the gate, preserves reveal/hide boundaries, and passes 240 Python regressions plus 49 UI checks. Reprocessing the captured match now publishes all four friendly hand identities and matches the sensor's hovered Annihilation entity. The production overlay remains intentionally inactive in Practice. Supported Standard overlay acceptance and broader mechanic coverage remain open.

## October 27 beta preparation

- 1.3.6: 260 Python regressions and 49 UI/lifecycle checks passed locally; reviewed definition fingerprints match client 255790 (2,444 definitions, no changes).
- Clean install and a completed Standard match were reported by the maintainer for 1.3.5. This does not imply every hover mechanic or focus/DPI combination was field-tested.
- GitHub still serves the removed private-media commit to authenticated repository access. The repository remains private. Do not expose that historical material by changing visibility before resolving it or publishing from a fresh repository.
- Initial downloads should present Setup as the primary file. Portable ZIP remains the secondary option and updater payload.
