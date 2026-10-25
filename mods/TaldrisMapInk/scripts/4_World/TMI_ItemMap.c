// Extends the actual vanilla ItemMap. Data belongs to the item, not the player.
modded class ItemMap
{
    protected ref array<ref TMI_Stroke> m_TMI_Strokes = new array<ref TMI_Stroke>;
    protected bool m_TMI_ClientLoaded;
    protected int m_TMI_Ack;
    protected int m_TMI_LastTransaction;
    protected string m_TMI_LastWriter;

    int TMI_GetAck() { return m_TMI_Ack; }

    array<ref TMI_Stroke> TMI_GetStrokes()
    {
        return m_TMI_Strokes;
    }

    bool TMI_IsLoaded()
    {
        return m_TMI_ClientLoaded;
    }

    override void OnStoreSave(ParamsWriteContext ctx)
    {
        super.OnStoreSave(ctx);
        // Append our own versioned records AFTER the vanilla marker stream.
        ctx.Write(m_TMI_Strokes.Count());
        foreach (TMI_Stroke stroke : m_TMI_Strokes)
            TMI_WriteStroke(ctx, stroke);
    }

    override bool OnStoreLoad(ParamsReadContext ctx, int version)
    {
        if (!super.OnStoreLoad(ctx, version)) return false;

        m_TMI_Strokes.Clear();
        int count;
        // Older vanilla saves did not have our tail. Treat absent data as blank.
        if (!ctx.Read(count)) return true;
        if (count < 0 || count > TMI_Protocol.MAX_SEGMENTS) return false;
        for (int i = 0; i < count; i++)
        {
            ref TMI_Stroke stroke = new TMI_Stroke;
            if (!TMI_ReadStroke(ctx, stroke) || !stroke.IsValid())
                return false;
            m_TMI_Strokes.Insert(stroke);
        }
        return true;
    }

    protected void TMI_WriteStroke(ParamsWriteContext ctx, TMI_Stroke s)
    {
        ctx.Write(s.m_X1);
        ctx.Write(s.m_Z1);
        ctx.Write(s.m_X2);
        ctx.Write(s.m_Z2);
        ctx.Write(s.m_Color);
        ctx.Write(s.m_Width);
    }

    protected bool TMI_ReadStroke(ParamsReadContext ctx, TMI_Stroke s)
    {
        if (!ctx.Read(s.m_X1)) return false;
        if (!ctx.Read(s.m_Z1)) return false;
        if (!ctx.Read(s.m_X2)) return false;
        if (!ctx.Read(s.m_Z2)) return false;
        if (!ctx.Read(s.m_Color)) return false;
        if (!ctx.Read(s.m_Width)) return false;
        return true;
    }

    void TMI_RequestSnapshot()
    {
        if (!GetGame().IsClient()) return;
        m_TMI_ClientLoaded = false;
        ref ScriptRPC rpc = new ScriptRPC;
        rpc.Send(this, TMI_Protocol.REQUEST, true, NULL);
    }

    void TMI_SaveBatch(array<ref TMI_Stroke> pending, int penColor, int transaction)
    {
        if (!GetGame().IsClient() || !pending || pending.Count() == 0) return;
        if (pending.Count() > TMI_Protocol.MAX_BATCH) return;
        ref ScriptRPC rpc = new ScriptRPC;
        rpc.Write(transaction);
        rpc.Write(penColor);
        rpc.Write(pending.Count());
        foreach (TMI_Stroke stroke : pending)
            TMI_WriteStroke(rpc, stroke);
        rpc.Send(this, TMI_Protocol.APPEND, true, NULL);
    }

    protected bool TMI_Authorized(PlayerIdentity sender, out PlayerBase owner)
    {
        owner = PlayerBase.Cast(GetHierarchyRootPlayer());
        if (!sender || !owner || !owner.GetIdentity()) return false;
        if (owner.GetIdentity().GetId() != sender.GetId()) return false;
        // Writing a dropped map or a map inside another player's bag is forbidden.
        return owner.GetHumanInventory().GetEntityInHands() == this;
    }

    protected void TMI_SendSnapshot(PlayerIdentity recipient)
    {
        if (!GetGame().IsServer() || !recipient) return;
        ref ScriptRPC rpc = new ScriptRPC;
        rpc.Write(m_TMI_Strokes.Count());
        foreach (TMI_Stroke stroke : m_TMI_Strokes)
            TMI_WriteStroke(rpc, stroke);
        rpc.Send(this, TMI_Protocol.SNAPSHOT, true, recipient);
    }

    protected void TMI_SendAck(PlayerIdentity recipient, int transaction)
    {
        ref ScriptRPC rpc = new ScriptRPC;
        rpc.Write(transaction);
        rpc.Send(this, TMI_Protocol.ACK, true, recipient);
    }

    override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type == TMI_Protocol.ACK && GetGame().IsClient())
        {
            int receipt;
            if (ctx.Read(receipt)) m_TMI_Ack = receipt;
            return;
        }
        if (rpc_type == TMI_Protocol.SNAPSHOT && GetGame().IsClient())
        {
            int count;
            if (!ctx.Read(count) || count < 0 || count > TMI_Protocol.MAX_SEGMENTS)
                return;
            ref array<ref TMI_Stroke> incoming = new array<ref TMI_Stroke>;
            for (int i = 0; i < count; i++)
            {
                ref TMI_Stroke segment = new TMI_Stroke;
                if (!TMI_ReadStroke(ctx, segment) || !segment.IsValid()) return;
                incoming.Insert(segment);
            }
            m_TMI_Strokes = incoming;
            m_TMI_ClientLoaded = true;
            return;
        }

        if (GetGame().IsServer() && rpc_type == TMI_Protocol.REQUEST)
        {
            PlayerBase reader;
            if (TMI_Authorized(sender, reader)) TMI_SendSnapshot(sender);
            return;
        }

        if (GetGame().IsServer() && rpc_type == TMI_Protocol.APPEND)
        {
            PlayerBase writer;
            if (!TMI_Authorized(sender, writer)) return;

            int transaction;
            if (!ctx.Read(transaction) || transaction <= 0) return;
            // One outstanding transaction per editor. Replays never append twice.
            if (m_TMI_LastWriter == sender.GetId() && m_TMI_LastTransaction == transaction)
            {
                TMI_SendSnapshot(sender);
                TMI_SendAck(sender, transaction);
                return;
            }
            int inkColor;
            int count;
            if (!ctx.Read(inkColor) || !ctx.Read(count)) return;
            if (!TMI_Protocol.HasPen(writer, inkColor)) return;
            if (count < 1 || count > TMI_Protocol.MAX_BATCH) return;
            if (m_TMI_Strokes.Count() + count > TMI_Protocol.MAX_SEGMENTS) return;

            // Validate the WHOLE batch before mutating the server map.
            ref array<ref TMI_Stroke> accepted = new array<ref TMI_Stroke>;
            for (int i = 0; i < count; i++)
            {
                ref TMI_Stroke entry = new TMI_Stroke;
                if (!TMI_ReadStroke(ctx, entry) || !entry.IsValid()) return;
                // An RPC must not smuggle other colours into this pen's batch.
                if (entry.m_Color != inkColor) return;
                accepted.Insert(entry);
            }
            foreach (TMI_Stroke line : accepted)
                m_TMI_Strokes.Insert(line);

            m_TMI_LastWriter = sender.GetId();
            m_TMI_LastTransaction = transaction;
            TMI_SendSnapshot(sender);
            TMI_SendAck(sender, transaction);
            return;
        }
        super.OnRPC(sender, rpc_type, ctx);
    }
};
