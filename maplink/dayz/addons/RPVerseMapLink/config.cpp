class CfgPatches
{
    class RPVerseMapLink
    {
        units[] = {"RPV_FerryTicket", "RPV_TravelTerminal"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Gear_Consumables"};
    };
};
class CfgMods
{
    class RPVerseMapLink
    {
        dir = "RPVerseMapLink";
        name = "RPVerse MapLink";
        author = "RPVerse";
        type = "mod";
        dependencies[] = {"Game", "World", "Mission"};
        class defs
        {
            class gameScriptModule
            {
                value = "";
                files[] = {"RPVerseMapLink/scripts/3_Game"};
            };
            class worldScriptModule
            {
                value = "";
                files[] = {"RPVerseMapLink/scripts/4_World"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"RPVerseMapLink/scripts/5_Mission"};
            };
        };
    };
};
class CfgVehicles
{
    class Inventory_Base;
    class Paper;
    class RPV_FerryTicket: Paper
    {
        scope = 2;
        displayName = "RPVerse Ferry Ticket";
        descriptionShort = "Travel ticket for RPVerse MapLink terminals.";
    };
    class RPV_TravelTerminal: Inventory_Base
    {
        scope = 2;
        displayName = "RPVerse Travel Terminal";
        descriptionShort = "Use this terminal to view available travel destinations.";
        model = "\\dz\\gear\\camping\\radio.p3d";
        weight = 10000;
        itemSize[] = {3,3};
    };
};
