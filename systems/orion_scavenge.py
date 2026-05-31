# ============================================================
# ORION SCAVENGE SYSTEM — /หาของ /หาของแอดมิน /หาของห้อง
# ค้นหาไอเทม — Configurable cooldown
# ============================================================
import discord
import random
import time
import asyncio

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    get_wallet, add_money, money_str, _parse_int,
    cooldown_remaining, set_cooldown, format_cooldown,
)

SCAVENGE_FILE   = f"{ORION_DATA_DIR}/scavenge_config.json"
SCAVENGE_ROOMS_FILE = f"{ORION_DATA_DIR}/scavenge_rooms.json"

DEFAULT_SCAVENGE_CFG = {
    "cooldown_seconds": 1800,
    "loot_table": [
        {"id": "common_herb",   "name": "สมุนไพรธรรมดา",  "emoji": "🌿", "weight": 40, "min": 1, "max": 3},
        {"id": "rare_crystal",  "name": "คริสตัลหายาก",   "emoji": "💎", "weight": 15, "min": 1, "max": 1},
        {"id": "old_coin",      "name": "เหรียญเก่า",       "emoji": "🪙", "weight": 30, "min": 1, "max": 5, "is_money": True, "money_value": 20},
        {"id": "iron_ore",      "name": "แร่เหล็ก",         "emoji": "⚙️", "weight": 25, "min": 1, "max": 2},
        {"id": "nothing",       "name": "ไม่พบอะไร",        "emoji": "💨", "weight": 20},
    ],
}


def load_scavenge_cfg() -> dict:
    cfg = load_json(SCAVENGE_FILE, {})
    changed = False
    for k, v in DEFAULT_SCAVENGE_CFG.items():
        if k not in cfg:
            cfg[k] = v; changed = True
    if changed:
        save_json(SCAVENGE_FILE, cfg)
    return cfg


def save_scavenge_cfg(cfg: dict):
    save_json(SCAVENGE_FILE, cfg)


def load_scavenge_rooms() -> dict:
    return load_json(SCAVENGE_ROOMS_FILE, {})


def save_scavenge_rooms(d: dict):
    save_json(SCAVENGE_ROOMS_FILE, d)


def _pick_loot(loot_table: list) -> dict | None:
    weights = [max(0, l.get("weight", 10)) for l in loot_table]
    total = sum(weights)
    if total <= 0:
        return None
    r = random.uniform(0, total)
    cumulative = 0
    for loot, w in zip(loot_table, weights):
        cumulative += w
        if r <= cumulative:
            return loot
    return loot_table[-1]


async def _run_scavenge(interaction: discord.Interaction, uid: str, room_name: str = "ทั่วไป"):
    cfg = load_scavenge_cfg()
    cd_key = f"scavenge_{room_name}"
    remaining = cooldown_remaining(uid, cd_key)
    if remaining > 0:
        await interaction.response.send_message(
            f"⏳ ต้องรออีก **{format_cooldown(remaining)}** ก่อนออกค้นหาได้อีกครั้ง",
            ephemeral=True,
        ); return

    # Pick loot
    loot_table = cfg.get("loot_table", DEFAULT_SCAVENGE_CFG["loot_table"])
    loot = _pick_loot(loot_table)

    if not loot or loot.get("id") == "nothing":
        set_cooldown(uid, cd_key, cfg.get("cooldown_seconds", 1800))
        await interaction.response.send_message(
            f"💨 **ออกค้นหาใน {room_name}...**\n\nไม่พบอะไรเลยในรอบนี้...",
            ephemeral=_eph("หาของ"),
        ); return

    qty = random.randint(int(loot.get("min", 1)), int(loot.get("max", 1)))

    if loot.get("is_money"):
        money_val = int(loot.get("money_value", 10)) * qty
        add_money(uid, money_val)
        result_text = f"พบ {money_str(money_val)}!"
    else:
        # Add to player inventory
        from orion_items import load_items_catalog, save_items_catalog, add_player_item
        cat = load_items_catalog()
        lid = loot.get("id", "unknown")
        if lid not in cat:
            cat[lid] = {
                "name": loot.get("name", lid),
                "emoji": loot.get("emoji", "📦"),
                "description": "พบจากการค้นหา",
                "sell_price": 0,
                "type": "resource",
                "stock": -1,
            }
            save_items_catalog(cat)
        add_player_item(uid, lid, qty)
        result_text = f"พบ **{loot.get('emoji', '📦')} {loot.get('name', lid)}** ×{qty}!"

    set_cooldown(uid, cd_key, cfg.get("cooldown_seconds", 1800))

    embed = discord.Embed(
        title=f"🔍 ออกค้นหา — {room_name}",
        description=result_text,
        color=0x00cec9,
    )
    cd = cfg.get("cooldown_seconds", 1800)
    embed.set_footer(text=f"Cooldown: {format_cooldown(cd)}")
    await interaction.response.send_message(embed=embed, ephemeral=_eph("หาของ"))


# ── Admin Views ───────────────────────────────────────────────
class ScavengeCooldownModal(discord.ui.Modal, title="⏱️ ตั้ง Cooldown หาของ"):
    f_cd = discord.ui.TextInput(
        label="Cooldown (วินาที)",
        placeholder="1800  (= 30 นาที)",
        max_length=10,
    )

    async def on_submit(self, ix: discord.Interaction):
        cd = max(60, _parse_int(self.f_cd.value, 1800) or 1800)
        cfg = load_scavenge_cfg()
        cfg["cooldown_seconds"] = cd
        save_scavenge_cfg(cfg)
        await ix.response.send_message(
            f"✅ Cooldown หาของ: **{format_cooldown(cd)}** ({cd}วินาที)",
            ephemeral=True,
        )


class ScavengeAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="ตั้ง Cooldown", style=discord.ButtonStyle.primary, row=1)
    async def set_cd(self, ix, _b):
        cfg = load_scavenge_cfg()
        modal = ScavengeCooldownModal()
        modal.f_cd.default = str(cfg.get("cooldown_seconds", 1800))
        await ix.response.send_modal(modal)

    @discord.ui.button(label="ล้าง Cooldown ผู้เล่น", style=discord.ButtonStyle.danger, row=2)
    async def clear_cd(self, ix, _b):
        class UserSel(discord.ui.UserSelect):
            def __init__(self2):
                super().__init__(placeholder="เลือกผู้เล่นที่จะล้าง cooldown...", min_values=1, max_values=1)
            async def callback(self2, ix2):
                from orion_bot import clear_cooldown
                uid = str(self2.values[0].id)
                clear_cooldown(uid, "scavenge_ทั่วไป")
                await ix2.response.send_message(f"✅ ล้าง cooldown ของ {self2.values[0].display_name} แล้ว", ephemeral=True)
        v = discord.ui.View(timeout=120); v.add_item(UserSel())
        await ix.response.send_message("เลือกผู้เล่น", view=v, ephemeral=True)


# ── Room System ───────────────────────────────────────────────
class ScavengeRoomSelect(discord.ui.Select):
    def __init__(self, uid: str):
        self.uid = uid
        rooms = load_scavenge_rooms()
        options = [discord.SelectOption(label="ทั่วไป", value="ทั่วไป", description="พื้นที่ทั่วไป")]
        for rname, r in list(rooms.items())[:24]:
            options.append(discord.SelectOption(
                label=rname[:100],
                value=rname,
                description=r.get("description", "")[:80],
            ))
        super().__init__(placeholder="🗺️ เลือกพื้นที่ค้นหา...", options=options)

    async def callback(self, ix: discord.Interaction):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return
        await _run_scavenge(ix, self.uid, self.values[0])


class ScavengeRoomView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=120)
        self.add_item(ScavengeRoomSelect(uid))


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="หาของ", description="ออกค้นหาไอเทม (มี cooldown)", guild=_ORION_GUILD_OBJ)
async def cmd_scavenge(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    rooms = load_scavenge_rooms()
    if rooms:
        await interaction.response.send_message(
            "เลือกพื้นที่ที่จะออกค้นหา",
            view=ScavengeRoomView(uid),
            ephemeral=True,
        )
    else:
        await _run_scavenge(interaction, uid, "ทั่วไป")


@bot.tree.command(name="หาของแอดมิน", description="[Admin] จัดการระบบ ค้นหาของ", guild=_ORION_GUILD_OBJ)
async def cmd_scavenge_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cfg = load_scavenge_cfg()
    cd = cfg.get("cooldown_seconds", 1800)
    embed = make_menu_embed(
        "หาของ Admin",
        [
            (f"Cooldown ปัจจุบัน: `{format_cooldown(cd)}`", f"= {cd} วินาที"),
            ("ตั้ง Cooldown", "ปรับเวลา cooldown ของการหาของ"),
            ("ล้าง Cooldown", "ล้าง cooldown ของผู้เล่นที่เลือก"),
        ],
        color=0x00cec9,
    )
    await interaction.response.send_message(embed=embed, view=ScavengeAdminView(), ephemeral=True)


@bot.tree.command(name="หาของห้อง", description="[Admin] จัดการห้องค้นหาของ", guild=_ORION_GUILD_OBJ)
async def cmd_scavenge_rooms(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    rooms = load_scavenge_rooms()
    lines = [f"• **{k}** — {v.get('description', '-')[:50]}" for k, v in list(rooms.items())[:15]]
    embed = discord.Embed(
        title=f"ห้องค้นหาของ — {len(rooms)} ห้อง",
        description="\n".join(lines) or "_ไม่มีห้อง (ใช้พื้นที่ทั่วไป)_",
        color=0x00cec9,
    )

    class RoomAdminView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        async def interaction_check(self, ix):
            if not ix.user.guild_permissions.administrator:
                await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
            return True
        @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
        async def done(self, ix, _b):
            await ix.response.edit_message(content="✓", embed=None, view=None)
        @discord.ui.button(label="เพิ่มห้อง", style=discord.ButtonStyle.success)
        async def add(self, ix, _b):
            class AddModal(discord.ui.Modal, title="เพิ่มห้องค้นหา"):
                f_name = discord.ui.TextInput(label="ชื่อห้อง", max_length=40)
                f_desc = discord.ui.TextInput(label="คำอธิบาย", required=False, max_length=200)
                async def on_submit(m_self, ix2):
                    rname = m_self.f_name.value.strip()
                    rooms2 = load_scavenge_rooms()
                    rooms2[rname] = {"description": (m_self.f_desc.value or "").strip()}
                    save_scavenge_rooms(rooms2)
                    await ix2.response.send_message(f"✅ เพิ่มห้อง **{rname}** แล้ว", ephemeral=True)
            await ix.response.send_modal(AddModal())

    await interaction.response.send_message(embed=embed, view=RoomAdminView(), ephemeral=True)
