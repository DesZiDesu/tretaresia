# ============================================================
# ORION GACHA — /กาชา /กาชาแอดมิน /กาชาดาวน์โหลด /กาชาอัปโหลด
# ============================================================
import discord
import random
import json
import io
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    get_wallet, add_money, money_str, _parse_int,
    ensure_orion_player,
)

GACHA_FILE = f"{ORION_DATA_DIR}/gacha_config.json"

DEFAULT_GACHA = {
    "name": "Gacha",
    "cost": 100,
    "pool": [
        {"id": "common_reward", "name": "รางวัลธรรมดา", "emoji": "📦", "weight": 60, "type": "money", "value": 50},
        {"id": "rare_reward", "name": "รางวัลหายาก", "emoji": "💎", "weight": 30, "type": "money", "value": 200},
        {"id": "epic_reward", "name": "รางวัล Epic", "emoji": "✨", "weight": 10, "type": "money", "value": 500},
    ],
}

def load_gacha() -> dict:
    g = load_json(GACHA_FILE, dict(DEFAULT_GACHA))
    if "pool" not in g: g["pool"] = list(DEFAULT_GACHA["pool"])
    return g

def save_gacha(d: dict):
    save_json(GACHA_FILE, d)

def _pull(pool: list) -> dict | None:
    weights = [max(0, p.get("weight", 10)) for p in pool]
    total = sum(weights)
    if not total: return None
    r = random.uniform(0, total)
    c = 0
    for p, w in zip(pool, weights):
        c += w
        if r <= c: return p
    return pool[-1]


@bot.tree.command(name="กาชา", description="เปิดตู้กาชา", guild=_ORION_GUILD_OBJ)
async def cmd_gacha(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    g = load_gacha()
    cost = int(g.get("cost", 100))
    if get_wallet(uid) < cost:
        await interaction.response.send_message(f"❌ เงินไม่พอ — ต้องการ {money_str(cost)}", ephemeral=True); return
    prize = _pull(g.get("pool", []))
    if not prize:
        await interaction.response.send_message("❌ ไม่มีรางวัลในตู้", ephemeral=True); return
    add_money(uid, -cost)
    if prize.get("type") == "money":
        val = int(prize.get("value", 0))
        add_money(uid, val)
        result = f"ได้ {money_str(val)}!"
    else:
        result = f"ได้ **{prize.get('name', '?')}**!"
    embed = discord.Embed(
        title=f"🎰 {g.get('name', 'Gacha')}",
        description=f"{prize.get('emoji', '🎁')} **{prize.get('name', '?')}**\n{result}\nยอด: {money_str(get_wallet(uid))}",
        color=0xfdcb6e,
    )
    await interaction.response.send_message(embed=embed, ephemeral=_eph("กาชา"))


@bot.tree.command(name="กาชาแอดมิน", description="[Admin] จัดการตู้กาชา", guild=_ORION_GUILD_OBJ)
async def cmd_gacha_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    g = load_gacha()
    embed = make_menu_embed("Gacha Admin", [(f"Cost: {money_str(g.get('cost', 100))}", f"Pool: {len(g.get('pool', []))} items")], color=0xfdcb6e)

    class GachaAdminView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        async def interaction_check(self2, ix):
            if not ix.user.guild_permissions.administrator:
                await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
            return True
        @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
        async def done(self2, ix, _b):
            await ix.response.edit_message(content="✓", embed=None, view=None)
        @discord.ui.button(label="ตั้งราคา", style=discord.ButtonStyle.primary)
        async def set_cost(self2, ix, _b):
            class M(discord.ui.Modal, title="ตั้งราคา Gacha"):
                f_cost = discord.ui.TextInput(label="ราคาต่อ pull", placeholder="100", max_length=10)
                async def on_submit(m_self, ix2):
                    g2 = load_gacha(); g2["cost"] = max(1, _parse_int(m_self.f_cost.value, 100) or 100); save_gacha(g2)
                    await ix2.response.send_message(f"✅ ราคา: {money_str(g2['cost'])}", ephemeral=True)
            await ix.response.send_modal(M())

    await interaction.response.send_message(embed=embed, view=GachaAdminView(), ephemeral=True)


@bot.tree.command(name="กาชาดาวน์โหลด", description="[Admin] ดาวน์โหลด Gacha config JSON", guild=_ORION_GUILD_OBJ)
async def cmd_gacha_dl(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    g = load_gacha()
    f = discord.File(fp=io.BytesIO(json.dumps(g, ensure_ascii=False, indent=2).encode()), filename="gacha_config.json")
    await interaction.response.send_message("📥 Gacha config", file=f, ephemeral=True)


@bot.tree.command(name="กาชาอัปโหลด", description="[Admin] อัปโหลด Gacha config JSON", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(file="ไฟล์ gacha_config.json")
async def cmd_gacha_ul(interaction: discord.Interaction, file: discord.Attachment):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            await interaction.followup.send("❌ ต้องเป็น JSON object", ephemeral=True); return
        save_gacha(data)
        await interaction.followup.send(f"✅ อัปโหลด Gacha config แล้ว · pool {len(data.get('pool', []))} items", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
