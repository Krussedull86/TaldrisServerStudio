# DZSA Tools Android access — 0.11.1 development release

The Windows background agent can expose a **separate opt-in HTTPS gateway** on TCP 8788 (configurable). Android uses this gateway, not the loopback owner API or a raw RCon connection. The Windows program and Android app are now named DZSA Tools. Windows installations and API identities are preserved. The first Android prototype may require one uninstall/re-pair because its signing key was not persisted correctly.

## Included in this first version

- Native Android app (Android 8+), multiple paired hosts and server cards: process state, player count/native FPS when the DayZ bridge is connected, process CPU/RAM, restart countdown and resource warnings.
- Start, graceful stop/restart with a 1–60 minute announced countdown, cancel countdown and a bounded single-line server message. The existing agent performs these operations; RCon is required for countdowns and messages.
- Aggregate last-hour FPS/CPU/RAM graphs and this phone's command history. No arbitrary RCon, configuration writes, file access, player identities/positions, ban/wipe or force-stop endpoints.
- One-use QR invitation (five minutes), explicit server selections and read/control/message permissions, revocable 90-day device credentials. Permission changes currently require revoking and re-pairing.
- Encrypted phone credentials/cache using Android Keystore AES-GCM. Status is clearly marked cached/offline when requests fail. Commands are disabled for cached status and are never queued offline or automatically retried.
- Optional Android WorkManager checks approximately every 15 minutes, subject to Android battery/network restrictions. They notify on a detected running-to-stopped transition, two consecutive host-access failures and subsequent recovery. An access failure is not presented as proof that DayZ crashed. This is **not real-time push delivery** and cannot guarantee detection of a short outage/recovery between samples. While open, the app refreshes every 15 seconds.
- Windows Firewall rule creation/update/removal for this installation's dedicated TCP port, with UAC if needed. The rule is scoped to the exact port and TCP. Gateway access remains disabled by default.

## Set up on the Windows host

1. Update Studio and its background agent to 0.11.1. Existing DayZ processes can remain managed by the background agent.
2. Open **Android access**. Choose the dedicated TCP port (default 8788).
3. Enter the address the phone will use, e.g. `https://192.168.1.50:8788` on your LAN, or your public hostname/IP and external port for internet use. No path, query or credentials belong in this address.
4. Enable the gateway and choose automatic Windows Firewall management. Save/apply and accept the Windows administrator prompt if required. Check that the page says Listening.
5. For access outside your LAN, configure router TCP port forwarding to the Windows host and allow the port in any hosting-provider firewall. Use a stable LAN address for the Windows host. This application does not change router settings, use UPnP or bypass ISP carrier-grade NAT. With CGNAT, use a reachable VPN address or a separately hosted relay/reverse connection (not included here).
6. Select the server profiles and whether the phone may control servers and/or send messages. Read access is always included. Create the QR invitation.

## Pair on Android

Install `DZSA-Tools-Android-dev.apk` from the same GitHub dev release. Android will ask you to allow installation from the browser/file manager. This is a development-signed sideload APK, not a Play Store release.

Choose Scan pairing QR or paste the invitation JSON, choose a phone name, then review the HTTPS address and SHA-256 certificate fingerprint. Compare the fingerprint to the Windows page before pairing. The app trusts only that exact certificate, including for the pairing request. It does not accept arbitrary self-signed certificates, HTTP redirects or cleartext HTTP.

A self-signed ECDSA certificate/private key is generated locally on first enable and protected with the host-owner ACL. Keep `mobile-key.pem` and `mobile-cert.pem` with the agent data. If the certificate changes, existing phones must be re-paired after verifying the new fingerprint. Do not share the private key, device token or QR invitation.

The app can pair with several host machines; use Hosts to switch/add/forget one. Forgetting a connection removes local credentials/cache only; revoke the device from Windows to remove server-side access. Existing accepted jobs may finish after revocation.

## Reliability and command semantics

The direct connection has no external cloud dependency and cannot reach a Windows host that is offline or disconnected. The Android cache is only the last received snapshot, with a timestamp; it cannot control an offline host or power on a powered-off PC.

Commands carry a unique request ID and a maximum 120-second acceptance window (the Android app requests 60 seconds). Device/request IDs are journalled for 30 days; retries with the same ID do not enqueue a second action. The agent checks expiry again before execution. After a timeout the app tells the operator to refresh status/history before trying again. Jobs accepted before an agent restart can show Unknown; they are not replayed automatically. A Completed restart/stop *command* means that the existing countdown was started; the live server state shows whether the eventual restart finished.

Only chosen server IDs are exposed. Mobile status is an explicit allowlist, not a copy of configuration, secrets, raw logs or the loopback snapshot. The HTTPS listener limits connection concurrency, body/response sizes, request time and request rates. Pair invitations/device tokens are never written to agent logs. Server-side device records store token hashes only.

Disable the gateway and save to stop listening and remove its owned Windows Firewall rule. If UAC is declined or policy prevents firewall removal, an error is shown and the rule needs manual attention. Agent exit closes the listener but keeps the enabled installation's rule for the next agent start.

## Build and distribution

The dev workflow builds both Windows EXE and native Android APK, then publishes them together with SHA-256 checksums. Android uses Java 17, Gradle 8.11.1, AGP 8.9.2 and SDK 35. From a machine with that toolchain: `cd android` then `gradle :app:assembleDebug`.

Development signing uses an explicitly generated key at `android/.signing/debug.keystore`, selected by Gradle and cached in GitHub Actions. The 0.11.0 prototype did not persist its key correctly and may require uninstall/re-pair once. If that cache is lost, Android may require uninstall/re-pair before accepting a differently signed development build. A production distribution requires a separately managed permanent signing key and release process. No signing secret is committed to the repository.

Real Windows UAC/firewall/router behavior and APK installation/QR scanning on a physical phone must be checked on the target setup. Local HTTPS authorization, scope filtering, expiry, replay protection and revocation are verified independently of the DayZ server process. No claim of successful real-device operation follows from an APK/EXE build alone.

Not included yet: external relay hosting, FCM push service, remote schedule editing, full map/player management, remote file editor or Play Store publication.
