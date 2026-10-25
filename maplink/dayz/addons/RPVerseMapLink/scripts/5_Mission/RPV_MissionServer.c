modded class MissionServer
{
    override void OnInit()
    {
        super.OnInit();
        ref RPV_Manifest manifest = RPV_Settings.LoadManifest();
        if (manifest && manifest.terminals)
            Print("[RPVerse MapLink] Manifest loaded; terminal definitions: " + manifest.terminals.Count().ToString());
        // Intentionally no automatic spawns yet: naive CreateObject on restart duplicates persistent objects.
        // Add persisted server-owned terminal IDs + restart-safe reconciliation before enabling auto_spawn.
    }
};
