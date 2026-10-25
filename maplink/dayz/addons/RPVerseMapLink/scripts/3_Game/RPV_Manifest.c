// Prototype manifest models. Data comes from backend.sync_config; no credentials in PBO.
class RPV_TerminalRow
{
    string id;
    string name;
    string classname;
    float x;
    float y;
    float z;
    float radius;
    bool auto_spawn;
};
class RPV_RouteRow
{
    string id;
    string name;
    string source_server_id;
    string target_server_id;
    string ticket_id;
    string ticket_classname;
    string video_id;
    string departure_asset;
    string arrival_asset;
    int price;
    float spawn_x;
    float spawn_y;
    float spawn_z;
};
class RPV_TerminalRouteRow
{
    string terminal_id;
    string route_id;
};
class RPV_Manifest
{
    int version;
    ref array<ref RPV_TerminalRow> terminals;
    ref array<ref RPV_RouteRow> routes;
    ref array<ref RPV_TerminalRouteRow> terminal_routes;

    void RPV_Manifest()
    {
        terminals = new array<ref RPV_TerminalRow>;
        routes = new array<ref RPV_RouteRow>;
        terminal_routes = new array<ref RPV_TerminalRouteRow>;
    }
};
class RPV_Settings
{
    static ref RPV_Manifest LoadManifest()
    {
        ref RPV_Manifest manifest = new RPV_Manifest();
        string errorMessage;
        if (!JsonFileLoader<RPV_Manifest>.LoadFile("$profile:RPVerseMapLink/terminals.json", manifest, errorMessage))
        {
            Print("[RPVerse MapLink] Failed reading manifest: " + errorMessage);
        }
        return manifest;
    }
};
