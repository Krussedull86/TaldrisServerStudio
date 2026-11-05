// Server-only, read-only telemetry. No RPCs, Discord tokens or game-state writes.
class CDSModConfig
{
    string BridgeId;
    bool Enabled = false;
    int IntervalSeconds = 5;
    bool CollectPlayers = true;
    bool CollectNames = false;
    bool ScanLoot = false;
    int LootRadius = 75;
};
class CDSPlayerSample
{
    int CDSSlot;
    string CDSName;
    float CDSX;
    float CDSZ;
    float CDSHealth;
    int CDSPing;
};
class CDSLootSample
{
    string CDSType;
    float CDSX;
    float CDSZ;
};
class CDSSnapshot
{
    int CDSSchema = 1;
    string CDSBridgeId;
    string CDSSession;
    int CDSSequence;
    float CDSUptime;
    string CDSWorldName;
    int CDSWorldSize;
    float CDSEngineFps;
    float CDSEngineMinFps;
    float CDSEngineMaxFps;
    float CDSUpdateFps;
    float CDSMeanFrameMs;
    float CDSPeakFrameMs;
    int CDSSlowFrames;
    int CDSPlayerCount;
    ref array<ref CDSPlayerSample> CDSPlayers = new array<ref CDSPlayerSample>;
    ref array<ref CDSLootSample> CDSLoot = new array<ref CDSLootSample>;
    int CDSLootRadius;
    float CDSLootX;
    float CDSLootZ;
    float CDSLootAge;
    int CDSInfected;
    int CDSVehicles;
    bool CDSLootTruncated;
};
modded class MissionServer
{
    protected ref CDSModConfig m_CDSConfig;
    protected float m_CDSWindow;
    protected int m_CDSFrames;
    protected float m_CDSPeak;
    protected int m_CDSSlow;
    protected int m_CDSSequence;
    protected string m_CDSSession;
    protected ref array<ref CDSLootSample> m_CDSLoot = new array<ref CDSLootSample>;
    protected float m_CDSLastScan;
    protected vector m_CDSScanPosition;
    protected int m_CDSScanIndex;
    protected int m_CDSInfected;
    protected int m_CDSVehicles;
    protected bool m_CDSTruncated;

    override void OnInit()
    {
        super.OnInit();
        MakeDirectory("$profile:CDSTelemetry");
        m_CDSConfig = new CDSModConfig;
        string error;
        if (!JsonFileLoader<CDSModConfig>.LoadFile("$profile:CDSTelemetry/config.json", m_CDSConfig, error))
        {
            Print("[CDS Telemetry] Configure and install the bridge from Server Studio before use.");
            m_CDSConfig.Enabled = false;
        }
        m_CDSConfig.IntervalSeconds = Math.Clamp(m_CDSConfig.IntervalSeconds, 2, 60);
        m_CDSConfig.LootRadius = Math.Clamp(m_CDSConfig.LootRadius, 25, 200);
        m_CDSSession = Math.RandomInt(1, 2000000000).ToString();
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (!GetGame().IsServer() || !m_CDSConfig || !m_CDSConfig.Enabled || m_CDSConfig.BridgeId == "")
            return;
        if (timeslice <= 0)
            return;
        m_CDSWindow += timeslice;
        m_CDSFrames++;
        if (timeslice > m_CDSPeak)
            m_CDSPeak = timeslice;
        if (timeslice > 0.05)
            m_CDSSlow++;
        if (m_CDSWindow < m_CDSConfig.IntervalSeconds)
            return;
        CDSWriteSnapshot();
        m_CDSWindow = 0;
        m_CDSFrames = 0;
        m_CDSPeak = 0;
        m_CDSSlow = 0;
    }

    protected void CDSWriteSnapshot()
    {
        CDSSnapshot sample = new CDSSnapshot;
        sample.CDSBridgeId = m_CDSConfig.BridgeId;
        sample.CDSSession = m_CDSSession;
        m_CDSSequence++;
        sample.CDSSequence = m_CDSSequence;
        sample.CDSUptime = GetGame().GetTickTime();
        sample.CDSWorldName = GetGame().GetWorldName();
        sample.CDSWorldSize = GetGame().GetWorld().GetWorldSize();
        sample.CDSEngineFps = GetGame().GetAvgFPS(64);
        sample.CDSEngineMinFps = GetGame().GetMinFPS(64);
        sample.CDSEngineMaxFps = GetGame().GetMaxFPS(64);
        sample.CDSUpdateFps = m_CDSFrames / m_CDSWindow;
        sample.CDSMeanFrameMs = 1000 * m_CDSWindow / m_CDSFrames;
        sample.CDSPeakFrameMs = 1000 * m_CDSPeak;
        sample.CDSSlowFrames = m_CDSSlow;
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        sample.CDSPlayerCount = players.Count();
        for (int index = 0; index < players.Count() && index < 128; index++)
        {
            PlayerBase player = PlayerBase.Cast(players[index]);
            if (!player || !player.GetIdentity())
                continue;
            if (m_CDSConfig.CollectPlayers)
            {
                CDSPlayerSample point = new CDSPlayerSample;
                vector position = player.GetPosition();
                point.CDSX = position[0];
                point.CDSZ = position[2];
                point.CDSSlot = player.GetIdentity().GetPlayerId();
                point.CDSName = "";
                if (m_CDSConfig.CollectNames)
                    point.CDSName = player.GetIdentity().GetName();
                point.CDSHealth = player.GetHealth("", "Health");
                point.CDSPing = player.GetIdentity().GetPingAvg();
                sample.CDSPlayers.Insert(point);
            }
        }
        // Scan one rotating player area every 15 seconds, never the whole map.
        if (m_CDSConfig.ScanLoot && players.Count() > 0 && sample.CDSUptime - m_CDSLastScan >= 15)
        {
            m_CDSScanIndex = m_CDSScanIndex % players.Count();
            Man anchor = players[m_CDSScanIndex];
            m_CDSScanIndex++;
            if (anchor)
                CDSScanLoot(anchor.GetPosition(), sample.CDSUptime);
        }
        if (m_CDSConfig.ScanLoot && m_CDSLastScan > 0)
        {
            sample.CDSLoot = m_CDSLoot;
            sample.CDSLootRadius = m_CDSConfig.LootRadius;
            sample.CDSLootX = m_CDSScanPosition[0];
            sample.CDSLootZ = m_CDSScanPosition[2];
            sample.CDSLootAge = sample.CDSUptime - m_CDSLastScan;
            sample.CDSInfected = m_CDSInfected;
            sample.CDSVehicles = m_CDSVehicles;
            sample.CDSLootTruncated = m_CDSTruncated;
        }
        string error;
        string output = "$profile:CDSTelemetry/snapshot" + (m_CDSSequence % 2).ToString() + ".json";
        // Alternating files allow the reader to retain the other complete sample.
        if (!JsonFileLoader<CDSSnapshot>.SaveFile(output, sample, error))
            Print("[CDS Telemetry] Snapshot write failed: " + error);
    }

    protected void CDSScanLoot(vector center, float uptime)
    {
        m_CDSLoot.Clear();
        m_CDSInfected = 0;
        m_CDSVehicles = 0;
        m_CDSTruncated = false;
        m_CDSLastScan = uptime;
        m_CDSScanPosition = center;
        array<Object> objects = new array<Object>;
        array<CargoBase> cargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(center, m_CDSConfig.LootRadius, objects, cargo);
        for (int index = 0; index < objects.Count() && index < 10000; index++)
        {
            Object obj = objects[index];
            if (!obj)
                continue;
            if (obj.IsKindOf("ZombieBase"))
                m_CDSInfected++;
            if (obj.IsKindOf("CarScript"))
                m_CDSVehicles++;
            ItemBase item = ItemBase.Cast(obj);
            if (!item || item.GetHierarchyParent())
                continue;
            if (m_CDSLoot.Count() >= 250)
            {
                m_CDSTruncated = true;
                continue;
            }
            CDSLootSample point = new CDSLootSample;
            vector position = item.GetPosition();
            point.CDSType = item.GetType();
            point.CDSX = position[0];
            point.CDSZ = position[2];
            m_CDSLoot.Insert(point);
        }
        if (objects.Count() > 10000)
            m_CDSTruncated = true;
    }
};
