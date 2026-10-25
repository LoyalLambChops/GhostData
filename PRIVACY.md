# Privacy

GhostData processes Hearthstone logs and read-only local client state on your Windows PC. Match history, source indexes, settings and imported public card definitions stay in your GhostDataData folder (or your explicitly configured data directory). They can include player names, deck names, game events and local paths. GhostData does not encrypt these files.

Normal tracking, Setup checks and REFRESH LOCAL CARDS do not call external services. UPDATE explicitly checks GitHub for app releases; GitHub receives ordinary request/network information, not your match history. Game definitions are read from your installed Blizzard client. No third-party art downloads, telemetry service or GhostData account is required.

Twitch and Discord buttons open those external sites. Email opens a draft in your chosen mail application. Nothing is attached or sent automatically; review any screenshots or logs before sharing. Those providers have their own policies.

ENABLE POWER LOGGING edits the Power section in your Blizzard log.config only when clicked. It preserves unrelated settings and backs up an existing file next to it. Hearthstone must restart afterward. Enabling logs causes Hearthstone to write game events to disk; GhostData does not delete those logs.

Uninstall preserves your separate match history/settings. CLEAR HISTORY is a distinct confirmed action. See the user manual for deletion and backup details. The public website has no analytics or embedded Twitch/Discord widgets; GitHub Pages handles its hosting.

Contact: LoyalLambChops@gmail.com
