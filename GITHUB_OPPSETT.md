# GitHub: dev and stable

Repository: https://github.com/Krussedull86/TaldrisServerStudio

Development is published on `dev`. Stable promotion is a separate, deliberate action. Existing technical repository/executable/service names are retained for upgrade compatibility; visible branding is CruzDoodelZ Server Studio.

## Development releases

A normal code push to `dev` runs Linux/Windows checks, builds the Windows executable, packages it and publishes a prerelease such as `dev-v0.9.3.b30`. Normal pushes do not change stable. A commit explicitly marked `[build only]` skips the automated test steps while still building and publishing; current releases use that mode at the user's request. `[skip ci]` prevents the build entirely and therefore cannot produce a downloadable application update.

Source belongs at the repository root: `app.py`, `requirements.txt` and `.github/` are direct children. Keep the publishing workflow on the default branch so manual stable promotion is available. GitHub Actions must be enabled and the publishing job must be allowed to write repository contents. Workflows use the built-in `GITHUB_TOKEN`; do not embed personal tokens in source.

Only application source/resources are published. Do not commit personal settings, server folders, SteamCMD login data, passwords, private signing keys or private mod content. Releases use a direct public GitHub repository and require no client token or Supabase service. Private release repositories are not supported by the current updater.

## Package contents

The Windows build embeds the CDS icon, local assets, loot editor/map templates and console dependencies. Packaging creates:

- `TaldrisServerStudio-Windows.zip`, containing the application and English usage instructions.
- `CruzDoodelZServerStudio-Setup.exe`, plus the compatible legacy installer filename.
- `build.json`, with version, build, ZIP filename, byte size and SHA-256.
- `SHA256SUMS.txt`.

The compatible ZIP/EXE filenames are required by older installed updaters. A source push alone does not make an update available; the build and publication must finish successfully and publish the expected assets.

## Stable promotion

1. Choose the exact published dev tag that has been verified.
2. Open **Actions → Promote tested dev to stable → Run workflow**.
3. Select `main`, enter the dev tag, enter `STABLE` in the confirmation field and run the workflow.

Promotion downloads the selected package, verifies SHA-256 and metadata, and publishes the same bytes without rebuilding. For example, `dev-v0.9.3.b30` becomes `v0.9.3.b30`. Stable is GitHub's Latest release; dev releases are prereleases with `latest=false`. Existing release tags are not overwritten. A source merge to main is separate from release promotion.

## Application updates

In **Program updates**, choose repository and channel (`dev` or `stable`). Enable startup checks or select **Save and check**. A newer package is downloaded, verified and staged in a separate version directory. The panel switches versions after active work and unsaved editor changes are resolved. Server processes remain running. The background agent upgrades separately and reuses verified processes; use **Update / repair background agent** when needed.

GitHub builds embed the repository address automatically. The initial application channel is stable; development users must select dev. Build numbers come from the workflow's `run_number`. Comparisons use semantic version and build number. Increase `VERSION` in `release_info.py` when changing the semantic version.

## Validation

Build-only releases are packaged without running automated test suites. Successful packaging confirms that a Windows executable and release assets were created; it does not prove live Steam/DayZ/Discord behavior. No Windows code-signing certificate is configured, so builds are unsigned. See the release and Actions run for actual publication status.
