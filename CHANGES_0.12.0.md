# DZSA Tools Android 0.12.0

Redesigned graphite/turquoise dashboard with rounded cards, four metric tiles, collapsible server controls, server search, uptime and an aggregate overview. Missing telemetry remains marked unavailable rather than being reported as zero players. Expanded cards and scroll position survive status refreshes.

A dedicated connection card distinguishes authenticated contact with the Windows background agent from individual DayZ process/telemetry state. It shows connecting, syncing, connected or disconnected, last response time and measured HTTPS round-trip latency. Cached readings are explicitly marked and command acceptance requires a fresh response (35 seconds). While open, the app refreshes every 10 seconds. Background checks retain the existing Android WorkManager schedule and limitations.

Connection details show the endpoint and pinned fingerprint, retry/host switching controls, typed DNS/connection/timeout/certificate/access error guidance and a Windows/router checklist. Certificate errors never disable verification. Hosts can be given local friendly names without changing server permissions or credentials.

The Windows window does not have to remain open: the connection is to the background agent. Existing pairing, package identity, encrypted credentials and signing key configuration are retained. APK build verification does not replace a physical-device UI/network check.
