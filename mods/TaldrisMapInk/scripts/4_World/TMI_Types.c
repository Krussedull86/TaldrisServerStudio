// Shared types live in World so both ItemMap and the mission UI can use them.
class TMI_Protocol
{
    static const int REQUEST = 7512401;
    static const int SNAPSHOT = 7512402;
    static const int APPEND = 7512403;
    static const int ACK = 7512404;
    static const int MAX_SEGMENTS = 4096;
    static const int MAX_BATCH = 48;

    static int ColorForPen(string type)
    {
        if (type == "Pen_Black") return ARGB(255, 25, 25, 25);
        if (type == "Pen_Blue")  return ARGB(255, 35, 82, 210);
        if (type == "Pen_Red")   return ARGB(255, 205, 36, 38);
        if (type == "Pen_Green") return ARGB(255, 34, 144, 58);
        return 0;
    }

    static bool HasPen(PlayerBase player, int color)
    {
        if (!player) return false;
        ref array<EntityAI> contents = new array<EntityAI>;
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, contents);
        foreach (EntityAI entity : contents)
        {
            ItemBase item = ItemBase.Cast(entity);
            if (item && !item.IsRuined() && ColorForPen(item.GetType()) == color)
                return true;
        }
        return false;
    }

    static bool ValidCoordinate(float coordinate)
    {
        // Keep invalid, infinite and nonsensical values away from persistence.
        return coordinate > -100000.0 && coordinate < 100000.0;
    }
};

class TMI_Stroke
{
    float m_X1;
    float m_Z1;
    float m_X2;
    float m_Z2;
    int m_Color;
    int m_Width;

    bool IsValid()
    {
        if (!TMI_Protocol.ValidCoordinate(m_X1) || !TMI_Protocol.ValidCoordinate(m_Z1))
            return false;
        if (!TMI_Protocol.ValidCoordinate(m_X2) || !TMI_Protocol.ValidCoordinate(m_Z2))
            return false;
        return m_Width >= 1 && m_Width <= 4;
    }
};
