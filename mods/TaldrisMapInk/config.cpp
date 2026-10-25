class CfgPatches
{
    class TaldrisMapInk
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Gear_Navigation"};
    };
};

class CfgMods
{
    class TaldrisMapInk
    {
        dir = "TaldrisMapInk";
        name = "Taldris Map Ink";
        author = "Krussedull86";
        type = "mod";
        dependencies[] = {"World", "Mission"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"TaldrisMapInk/scripts/4_World"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"TaldrisMapInk/scripts/5_Mission"};
            };
        };
    };
};
