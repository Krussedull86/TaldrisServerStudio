"""Static smoke checks; DOES NOT compile Enforce Script or verify DayZ runtime."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD = (ROOT / "scripts/4_World/TMI_ItemMap.c").read_text(encoding="utf-8")
MISSION = (ROOT / "scripts/5_Mission/TMI_MapMenu.c").read_text(encoding="utf-8")
TYPES = (ROOT / "scripts/4_World/TMI_Types.c").read_text(encoding="utf-8")
LAYOUT = (ROOT / "gui/layouts/map_ink.layout").read_text(encoding="utf-8")

FIELDS = ("m_X1", "m_Z1", "m_X2", "m_Z2", "m_Color", "m_Width")
save = WORLD.split("protected void TMI_WriteStroke", 1)[1].split("protected bool TMI_ReadStroke", 1)[0]
load = WORLD.split("protected bool TMI_ReadStroke", 1)[1].split("void TMI_RequestSnapshot", 1)[0]
assert [x for x in FIELDS if f"ctx.Write(s.{x})" in save] == list(FIELDS)
assert [x for x in FIELDS if f"ctx.Read(s.{x})" in load] == list(FIELDS)
assert "super.OnStoreSave(ctx)" in WORLD and "super.OnStoreLoad(ctx, version)" in WORLD
assert "TMI_Authorized(sender, writer)" in WORLD
assert "TMI_Protocol.HasPen(writer, inkColor)" in WORLD
assert "m_MapWidgetInstance.ScreenToMap" in MISSION
assert "m_MapWidgetInstance.MapToScreen" in MISSION
assert "MAX_SEGMENTS = 4096" in TYPES and "MAX_BATCH = 48" in TYPES
assert all(t in TYPES for t in ("Pen_Black", "Pen_Blue", "Pen_Red", "Pen_Green"))
assert all(x in LAYOUT for x in ("TMI_Canvas", "TMI_Input", "TMI_Save", "TMI_Toggle"))
print("Static checks passed (runtime unverified).")
