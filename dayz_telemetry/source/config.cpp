class CfgPatches
{
    class CDS_Telemetry
    {
        units[]={};
        weapons[]={};
        requiredVersion=0.1;
        requiredAddons[]={"DZ_Data","DZ_Scripts"};
    };
};
class CfgMods
{
    class CDS_Telemetry
    {
        dir="CDSTelemetry";
        name="CDS Telemetry";
        type="mod";
        dependencies[]={"Mission"};
        class defs
        {
            class missionScriptModule
            {
                value="";
                files[]={"CDSTelemetry/scripts/5_Mission"};
            };
        };
    };
};
