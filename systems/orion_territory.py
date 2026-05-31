# ============================================================
# ORION TERRITORY — /พื้นที่ /สงคราม /สงครามรางวัล /พื้นที่แอดมิน
# ============================================================
import discord
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _eph,
)

TERRITORY_FILE = f"{ORION_DATA_DIR}/territories.json"


def load_territories() -> dict:
    return load_json(TERRITORY_FILE, {})


def save_territories(d: dict):
    save_json(TERRITORY_FILE, d)


def _territory_embed(t: dict, tid: str) -> discord.Embed:
    embed = discord.Embed(title=f"🗺️ {t.get('name', tid)}", description=t.get("description", ""), color=0x27ae60)
    owner = t.get("owner_id")
    embed.add_field(name="เจ้าของ", value=f"<@{owner}>" if owner else "_ไม่มีเจ้าของ_", inline=True)
    embed.add_field(name="กำลัง", value=f"`{t.get('power', 0)}`", inline=True)
    if t.get("image_url"):
        embed.set_thumbnail(url=t["image_url"])
    return embed


@bot.tree.command(name="พื้นที่", description="ดูเขตพื้นที่ทั้งหมด", guild=_ORION_GUILD_OBJ)
async def cmd_territory(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    territories = load_territories()
    if not territories:
        embed = discord.Embed(title="🗺️ พื้นที่", description="_ยังไม่มีเขตพื้นที่ — แอดมินสร้างผ่าน `/พื้นที่แอดมิน`_", color=0x27ae60)
        await interaction.response.send_message(embed=embed, ephemeral=_eph("พื้นที่")); return
    options = [
        discord.SelectOption(label=t.get("name", tid)[:100], value=tid)
        for tid, t in list(territories.items())[:25]
    ]

    class TerritorySelect(discord.ui.Select):
        def __init__(self):
            super().__init__(placeholder="เลือกพื้นที่...", options=options)
        async def callback(self, ix):
            t = load_territories().get(self.values[0], {})
            await ix.response.edit_message(embed=_territory_embed(t, self.values[0]), view=TerritoryView())

    class TerritoryView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.add_item(TerritorySelect())
            self.add_item(DoneBtn(row=1))

    embed = discord.Embed(title=f"🗺️ พื้นที่ทั้งหมด — {len(territories)} เขต", color=0x27ae60)
    lines = [f"• **{t.get('name', tid)}**" for tid, t in list(territories.items())[:15]]
    embed.description = "\n".join(lines)
    await interaction.response.send_message(embed=embed, view=TerritoryView(), ephemeral=_eph("พื้นที่"))


@bot.tree.command(name="สงคราม", description="ประกาศสงครามแย่งพื้นที่", guild=_ORION_GUILD_OBJ)
async def cmd_war(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    embed = discord.Embed(title="⚔️ สงคราม", description="_ระบบสงครามอยู่ในการพัฒนา_", color=0xe74c3c)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="สงครามรางวัล", description="ดูรางวัลสงคราม", guild=_ORION_GUILD_OBJ)
async def cmd_war_rewards(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    embed = discord.Embed(title="🏆 รางวัลสงคราม", description="_รางวัลสงครามจะปรากฏที่นี่_", color=0xf1c40f)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="พื้นที่แอดมิน", description="[Admin] จัดการเขตพื้นที่", guild=_ORION_GUILD_OBJ)
async def cmd_territory_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    territories = load_territories()
    embed = make_menu_embed(f"Territory Admin — {len(territories)} เขต", [], color=0x27ae60)

    class TerritoryAdminView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        async def interaction_check(self, ix):
            if not ix.user.guild_permissions.administrator:
                await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
            return True
        @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
        async def done(self, ix, _b):
            await ix.response.edit_message(content="✓", embed=None, view=None)
        @discord.ui.button(label="เพิ่มเขต", style=discord.ButtonStyle.success)
        async def add(self, ix, _b):
            class AddModal(discord.ui.Modal, title="เพิ่มเขตพื้นที่"):
                f_name = discord.ui.TextInput(label="ชื่อเขต", max_length=50)
                f_desc = discord.ui.TextInput(label="คำอธิบาย", required=False, max_length=300)
                async def on_submit(m_self, ix2):
                    import uuid
                    tid = uuid.uuid4().hex[:6]
                    t = load_territories()
                    t[tid] = {"name": m_self.f_name.value.strip(), "description": (m_self.f_desc.value or "").strip(), "owner_id": None, "power": 0}
                    save_territories(t)
                    await ix2.response.send_message(f"✅ เพิ่มเขต **{m_self.f_name.value}** (ID: `{tid}`)", ephemeral=True)
            await ix.response.send_modal(AddModal())

    await interaction.response.send_message(embed=embed, view=TerritoryAdminView(), ephemeral=True)
