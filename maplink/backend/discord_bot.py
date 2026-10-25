"""Optional Discord slash commands (read-only). Guild admin commands to follow later."""
import os
import httpx
import discord
from discord import app_commands

TOKEN = os.environ.get("MAPLINK_DISCORD_BOT_TOKEN")
BASE = os.environ.get("MAPLINK_URL", "http://127.0.0.1:8907").rstrip("/")
ADMIN = os.environ.get("MAPLINK_ADMIN_TOKEN")

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot=Bot()

async def get_data(endpoint: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r=await client.get(BASE+endpoint,headers={"Authorization":"Bearer "+ADMIN})
        r.raise_for_status()
        return r.json()

@bot.tree.command(name="maplink_status",description="Se MapLink-status")
async def maplink_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        d=await get_data("/admin/overview")
        await interaction.followup.send(f"Servere: {d['servers']} | Ruter: {d['routes']} | Overføringer: {d['transfers']}",ephemeral=True)
    except httpx.HTTPError:
        await interaction.followup.send("MapLink API er utilgjengelig.",ephemeral=True)

@bot.tree.command(name="maplink_routes",description="Se åpne MapLink-ruter")
async def maplink_routes(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        rows=await get_data("/admin/routes")
        lines=[f"{r['source_server_id']} → {r['target_server_id']} ({r['name']})" for r in rows if r['enabled']]
        await interaction.followup.send("\n".join(lines)[:1800] or "Ingen aktive ruter.",ephemeral=True)
    except httpx.HTTPError:
        await interaction.followup.send("MapLink API er utilgjengelig.",ephemeral=True)

if __name__=="__main__":
    if not TOKEN or not ADMIN:
        raise SystemExit("Set MAPLINK_DISCORD_BOT_TOKEN and MAPLINK_ADMIN_TOKEN")
    bot.run(TOKEN)
