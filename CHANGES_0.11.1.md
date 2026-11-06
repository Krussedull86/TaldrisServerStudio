# DZSA Tools 0.11.1 — product rename

Windows and Android are now named **DZSA Tools**, with matching graphite/turquoise icons and the new DZSA / TOOLS lettering. Window titles, the Windows installation entry, desktop/Start menu shortcuts, the service display name, mobile labels/notifications and current documentation use the new name.

New downloads are `DZSA-Tools-Setup.exe` and `DZSA-Tools-Android-dev.apk`. Legacy installer/APK aliases and the updater's existing ZIP name are retained. Existing data folders, service IDs, Android application ID, Android Keystore alias, notification channel ID, TLS certificates/pins, device credentials, telemetry protocol names and named Windows Job Objects remain stable. The GitHub repository is unchanged.

The installed Windows panel refreshes registration and migrates old desktop/Start menu shortcuts only when they point to this installation's launcher. Existing taskbar pins keep their app identity and receive the current icon/description; Windows may still cache an old pin label until it is re-pinned. A service display name is refreshed during service installation/agent replacement. Existing firewall rule IDs are retained and their labels/groups update when rules are next checked.

The Android build reuses the development signing key from the previous build's cache. It can update the existing app while retaining connections and credentials when that key is available; development signing is not a production distribution process.
