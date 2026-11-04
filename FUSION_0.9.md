# CruzDoodelZ Server Studio 0.9 — fusion

The uploaded `TaldrisServerStudio_0.6_source (1).zip` improvements are merged into the existing 0.8.2 host, not used as a replacement. Existing agent/service, multi-server, updates, BAT import, EXE lifecycle, maps and local client launch remain.

## Merged improvements
- English text from the supplied desktop, Workshop, local mod and update UI. Newer hosting screens retain some Norwegian text.
- Explicit SteamCMD stage label alongside the live console, with completion/failure state.
- Overview runtime checker for DirectX x64 and Visual C++ x64. The existing PE architecture validation remains authoritative at server start. Microsoft download buttons are explicit; runtimes are not silently installed.
- Export/import settings and mods as `.cruz.json`, with legacy flat `.taldris.json` import. No credentials, process state or companion command arguments are exported. Import creates a new stopped profile and never starts it. Review paths and ports before starting.

## Integrated DZSA Loot Editor
The editor UI comes from our `Krussedull86/CrusDoodelz-DayZ-Loot-Editor` stable source, and its loss-aware row model/revisions are adapted to Python and Qt WebChannel. No second EXE, PHP, web server, token or login is required. Credits: CruzDoodelz & NoSignal; original DZSA Tools by NIXON. Third-party library notices remain in the bundled sources.

- Embedded search/filter table, Ctrl/Shift selection, numeric and flag editors, bulk operations and local saved revisions with undo/redo.
- Import XML, export a separate edited XML and starter templates for Chernarus, Livonia, Sakhal and Nasdara from the supplied loot-editor data (not automatically downloaded game updates).
- Reads the active mission from the selected profile's actual server CFG, not just the cached profile dropdown. Resolves `mpmissions/<template>/db/types.xml` and type files registered in `cfgeconomycore.xml`. Choose the target when several files exist.
- The open project shows its target server/file and stays bound to that target even if the main server selector changes. Import and template projects are detached.
- `Save changes`/autosave only creates a local project revision. **Save to mission** saves the table first, then writes through the agent's existing stopped-server guard, compare-before-write and backup. Reopening an old project also checks the original target digest and current active mission.
- Export never writes into registered server roots. Use the guarded mission writer for server files.
- Unknown XML attributes/nodes and comments are preserved (XML formatting can change). Validation covers syntax, duplicate names, integer ranges and flags; no claim of complete XSD/game semantic validation. Existing support for custom nodes is retained.
- No live loot reset is performed. DayZ normally reads mission economy data at server start; saving does not restart servers or reset persistence.

## Compatibility
The visible product name, installer entry, shortcuts, service display name and firewall description use CruzDoodelZ Server Studio. Existing technical data/service/EXE identifiers and GitHub repository remain for upgrade compatibility. Old desktop shortcuts pointing at this installation are removed when installing the new shortcuts. A branded Setup EXE is published alongside the legacy-named updater assets; both contain the same application. Settings, live DayZ processes and worlds are retained.
