// Extends the vanilla physical-map screen. No custom map item is spawned.
modded class MapMenu
{
    protected Widget m_TMI_Root;
    protected Widget m_TMI_Input;
    protected CanvasWidget m_TMI_Canvas;
    protected TextWidget m_TMI_Status;
    protected ButtonWidget m_TMI_Toggle;
    protected ButtonWidget m_TMI_Save;
    protected ButtonWidget m_TMI_Undo;
    protected ButtonWidget m_TMI_Black;
    protected ButtonWidget m_TMI_Blue;
    protected ButtonWidget m_TMI_Red;
    protected ButtonWidget m_TMI_Green;

    protected bool m_TMI_EditMode;
    protected bool m_TMI_Drawing;
    protected int m_TMI_PenColor = 0;
    protected vector m_TMI_LastWorld;
    protected int m_TMI_LastMouseX;
    protected int m_TMI_LastMouseY;
    protected ref array<ref TMI_Stroke> m_TMI_Pending = new array<ref TMI_Stroke>;

    protected int m_TMI_Transaction;
    protected int m_TMI_InFlightCount;
    protected int m_TMI_SentAt;
    protected int m_TMI_Attempts;
    protected ref array<ref TMI_Stroke> m_TMI_InFlight;

    override Widget Init()
    {
        Widget main = super.Init();
        m_TMI_Root = GetGame().GetWorkspace().CreateWidgets("TaldrisMapInk/gui/layouts/map_ink.layout", layoutRoot);
        if (m_TMI_Root)
        {
            m_TMI_Input = m_TMI_Root.FindAnyWidget("TMI_Input");
            m_TMI_Canvas = CanvasWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Canvas"));
            m_TMI_Status = TextWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Status"));
            m_TMI_Toggle = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Toggle"));
            m_TMI_Save = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Save"));
            m_TMI_Undo = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Undo"));
            m_TMI_Black = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Black"));
            m_TMI_Blue = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Blue"));
            m_TMI_Red = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Red"));
            m_TMI_Green = ButtonWidget.Cast(m_TMI_Root.FindAnyWidget("TMI_Green"));
            m_TMI_Input.Show(false);
        }
        return main;
    }

    override void InitMapItem(EntityAI item)
    {
        super.InitMapItem(item);
        m_TMI_Pending.Clear();
        m_TMI_InFlightCount = 0;
        m_TMI_InFlight = NULL;
        m_TMI_Transaction = Math.RandomInt(1, 1000000000);
        m_TMI_EditMode = false;
        m_TMI_Drawing = false;
        if (m_TMI_Input) m_TMI_Input.Show(false);
        if (m_Map) m_Map.TMI_RequestSnapshot();
    }

    protected void TMI_UpdateStatus()
    {
        if (!m_TMI_Status) return;
        if (!m_Map) { m_TMI_Status.SetText("No physical map"); return; }
        if (!m_Map.TMI_IsLoaded()) { m_TMI_Status.SetText("Loading map ink..."); return; }
        if (m_TMI_InFlightCount > 0)
        {
            m_TMI_Status.SetText("Waiting for server | ink retained");
            return;
        }
        if (m_TMI_EditMode)
            m_TMI_Status.SetText(string.Format("INK ON | unsaved segments: %1", m_TMI_Pending.Count()));
        else
            m_TMI_Status.SetText(string.Format("READ | saved segments: %1", m_Map.TMI_GetStrokes().Count()));
    }

    protected bool TMI_ChoosePen(string penType)
    {
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        int inkColor = TMI_Protocol.ColorForPen(penType);
        if (!TMI_Protocol.HasPen(player, inkColor)) return false;
        m_TMI_PenColor = inkColor;
        return true;
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        // Keep the queued prefix stable until its receipt arrives.
        if (m_TMI_InFlightCount > 0)
        {
            if (w == m_TMI_Save) TMI_Resend();
            if (w == m_TMI_Save || w == m_TMI_Undo || w == m_TMI_Toggle || w == m_TMI_Black || w == m_TMI_Blue || w == m_TMI_Red || w == m_TMI_Green) return true;
        }
        if (w == m_TMI_Black) { TMI_ChoosePen("Pen_Black"); return true; }
        if (w == m_TMI_Blue)  { TMI_ChoosePen("Pen_Blue"); return true; }
        if (w == m_TMI_Red)   { TMI_ChoosePen("Pen_Red"); return true; }
        if (w == m_TMI_Green) { TMI_ChoosePen("Pen_Green"); return true; }

        if (w == m_TMI_Toggle)
        {
            PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
            if (!m_Map || !m_Map.TMI_IsLoaded()) return true;
            if (!m_TMI_EditMode && !TMI_Protocol.HasPen(player, m_TMI_PenColor))
            {
                if (!TMI_ChoosePen("Pen_Black") && !TMI_ChoosePen("Pen_Blue") && !TMI_ChoosePen("Pen_Red"))
                    TMI_ChoosePen("Pen_Green");
            }
            if (!m_TMI_EditMode && !TMI_Protocol.HasPen(player, m_TMI_PenColor)) return true;
            m_TMI_EditMode = !m_TMI_EditMode;
            m_TMI_Drawing = false;
            m_TMI_Input.Show(m_TMI_EditMode);
            return true;
        }
        if (w == m_TMI_Undo)
        {
            if (m_TMI_Pending.Count() > 0) m_TMI_Pending.Remove(m_TMI_Pending.Count() - 1);
            return true;
        }
        if (w == m_TMI_Save)
        {
            TMI_CommitPending();
            return true;
        }
        return super.OnClick(w, x, y, button);
    }

    override bool OnMouseButtonDown(Widget w, int x, int y, int button)
    {
        if (w == m_TMI_Input && m_TMI_EditMode && button == MouseState.LEFT && m_Map && m_Map.TMI_IsLoaded())
        {
            PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
            if (!TMI_Protocol.HasPen(player, m_TMI_PenColor)) return true;
            m_TMI_Drawing = true;
            m_TMI_LastMouseX = x;
            m_TMI_LastMouseY = y;
            m_TMI_LastWorld = m_MapWidgetInstance.ScreenToMap(Vector(x, y, 0));
            return true;
        }
        return super.OnMouseButtonDown(w, x, y, button);
    }

    override bool OnMouseButtonUp(Widget w, int x, int y, int button)
    {
        if (m_TMI_Drawing && button == MouseState.LEFT)
        {
            TMI_AddPoint(x, y);
            m_TMI_Drawing = false;
            return true;
        }
        return super.OnMouseButtonUp(w, x, y, button);
    }

    protected void TMI_AddPoint(int x, int y)
    {
        if (!m_TMI_Drawing || m_TMI_InFlightCount > 0 || !m_MapWidgetInstance || m_TMI_Pending.Count() + m_Map.TMI_GetStrokes().Count() >= TMI_Protocol.MAX_SEGMENTS)
            return;
        int dx = x - m_TMI_LastMouseX;
        int dy = y - m_TMI_LastMouseY;
        if (dx * dx + dy * dy < 16) return;  // At least 4 screen pixels.
        vector now = m_MapWidgetInstance.ScreenToMap(Vector(x, y, 0));
        ref TMI_Stroke s = new TMI_Stroke;
        s.m_X1 = m_TMI_LastWorld[0];
        s.m_Z1 = m_TMI_LastWorld[2];
        s.m_X2 = now[0];
        s.m_Z2 = now[2];
        s.m_Color = m_TMI_PenColor;
        s.m_Width = 2;
        if (s.IsValid()) m_TMI_Pending.Insert(s);
        m_TMI_LastWorld = now;
        m_TMI_LastMouseX = x;
        m_TMI_LastMouseY = y;
    }

    protected void TMI_Resend()
    {
        if (!m_Map || !m_TMI_InFlight || m_TMI_InFlightCount == 0) return;
        m_Map.TMI_SaveBatch(m_TMI_InFlight, m_TMI_InFlight[0].m_Color, m_TMI_Transaction);
        m_TMI_SentAt = GetGame().GetTime();
        m_TMI_Attempts++;
    }

    protected void TMI_CommitPending()
    {
        if (!m_Map || !m_Map.TMI_IsLoaded() || m_TMI_Pending.Count() == 0 || m_TMI_InFlightCount > 0) return;
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        int color = m_TMI_Pending[0].m_Color;
        if (!TMI_Protocol.HasPen(player, color)) return;
        m_TMI_Drawing = false;
        m_TMI_InFlight = new array<ref TMI_Stroke>;
        for (int i = 0; i < m_TMI_Pending.Count() && i < TMI_Protocol.MAX_BATCH; i++)
        {
            if (m_TMI_Pending[i].m_Color != color) break;
            m_TMI_InFlight.Insert(m_TMI_Pending[i]);
        }
        m_TMI_Transaction++;
        m_TMI_InFlightCount = m_TMI_InFlight.Count();
        m_TMI_Attempts = 0;
        TMI_Resend();
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        if (!m_TMI_Root || !m_Map || !m_TMI_Canvas || !m_MapWidgetInstance) return;

        if (m_TMI_InFlightCount > 0)
        {
            if (m_Map.TMI_GetAck() == m_TMI_Transaction)
            {
                for (int acknowledged = 0; acknowledged < m_TMI_InFlightCount; acknowledged++)
                    m_TMI_Pending.Remove(0);
                m_TMI_InFlightCount = 0;
                m_TMI_InFlight = NULL;
                TMI_CommitPending();
            }
            else if (m_TMI_Attempts < 3 && GetGame().GetTime() - m_TMI_SentAt >= 3000)
                TMI_Resend();
        }
        if (m_TMI_Drawing)
        {
            int px;
            int py;
            GetMousePos(px, py);
            TMI_AddPoint(px, py);
        }

        m_TMI_Canvas.Clear();
        if (m_Map.TMI_IsLoaded())
        {
            foreach (TMI_Stroke saved : m_Map.TMI_GetStrokes())
                TMI_RenderSegment(saved);
        }
        foreach (TMI_Stroke unsaved : m_TMI_Pending)
            TMI_RenderSegment(unsaved);
        TMI_UpdateStatus();
    }

    protected void TMI_RenderSegment(TMI_Stroke stroke)
    {
        vector a = m_MapWidgetInstance.MapToScreen(Vector(stroke.m_X1, 0, stroke.m_Z1));
        vector b = m_MapWidgetInstance.MapToScreen(Vector(stroke.m_X2, 0, stroke.m_Z2));
        m_TMI_Canvas.DrawLine(a[0], a[1], b[0], b[1], stroke.m_Width, stroke.m_Color);
    }
};
