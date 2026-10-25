# Contributing

GhostData's original software is MIT licensed. Contributions should preserve local processing, Standard scope, honest uncertainty, and the read-only sensor boundary. Do not add game automation, hidden-information disclosure, external card-art fetching or automatic match-history uploads.

Use Python 3.12+ and the .NET 10 SDK. Run `python -m unittest discover -s tests -q`, build and run `tests/GhostData.ParityHarness`, and use synthetic fixtures for regressions. See docs/TECHNICAL_MANUAL.md for packaging and UI previews.

Explain the problem, resulting behavior and validation in a pull request. Keep real logs, credentials, private promotional artwork and runtime caches out of commits. Preserve third-party attribution and disclose new dependencies/licenses. Security reports belong in the private channel described in SECURITY.md.
