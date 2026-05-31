# ============================================================
# ORION TRAINING SYSTEM — /ฝึกสกิล /ฝึกแอดมิน
# Skill training (เรียนสกิลจากผู้สอน)
# ============================================================
import discord
import random
import asyncio
import json

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    get_wallet, add_money, money_str, load_currency_cfg, _parse_int,
    cooldown_remaining, set_cooldown, format_cooldown, clear_cooldown,
    load_skill_cats, get_skill_cat, grant_skill_slot,
)

TRAINING_FILE = f"{ORION_DATA_DIR}/training_config.json"

DEFAULT_TRAINING_CFG = {
    "cost": 200,
    "cooldown_seconds": 3600,
    "sessions": [],
}


def load_training_cfg() -> dict:
    cfg = load_json(TRAINING_FILE, {})
    for k, v in DEFAULT_TRAINING_CFG.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def save_training_cfg(cfg: dict):
    save_json(TRAINING_FILE, cfg)


class TrainingSessionSelect(discord.ui.Select):
    def __init__(self, uid: str):
        self.uid = uid
        cfg = load_training_cfg()
        sessions = cfg.get("sessions", [])
        options = []
        for s in sessions[:25]:
            options.append(discord.SelectOption(
                label=s.get("name", "?")[:100],
                value=s.get("id", "?"),
                description=f"หมวด: {s.get('category', '?')} · {s.get('description', '')[:50]}"[:80],
                emoji=_safe_emoji(s.get("emoji"), "📚"),
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มีหลักสูตรฝึก", value="none")]
        super().__init__(placeholder="📚 เลือกหลักสูตรที่จะฝึก...", options=options)

    async def callback(self, ix: discord.Interaction):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return
        if self.values[0] == "none":
            await ix.response.defer(); return
        sid = self.values[0]
        cfg = load_training_cfg()
        session = next((s for s in cfg.get("sessions", []) if s.get("id") == sid), None)
        if not session:
            await ix.response.send_message("❌ ไม่พบหลักสูตร", ephemeral=True); return

        # Cooldown check
        cd_key = f"train_{sid}"
        remaining = cooldown_remaining(self.uid, cd_key)
        if remaining > 0:
            await ix.response.send_message(
                f"⏳ cooldown: **{format_cooldown(remaining)}**",
                ephemeral=True,
            ); return

        cost = cfg.get("cost", 200)
        if get_wallet(self.uid) < cost:
            await ix.response.send_message(
                f"❌ เงินไม่พอ — ต้องการ {money_str(cost)}",
                ephemeral=True,
            ); return

        add_money(self.uid, -cost)
        set_cooldown(self.uid, cd_key, cfg.get("cooldown_seconds", 3600))
        cat_id = session.get("category", "any")
        grant_skill_slot(self.uid, cat_id, 1)

        await ix.response.send_message(
            f"✅ ฝึก **{session['name']}** สำเร็จ!\n"
            f"ได้รับสิทธิ์สร้างสกิล 1 ครั้ง (หมวด: **{cat_id}**)\n"
            f"ใช้ `/orion` → **สร้างสกิลใหม่** เพื่อสร้างสกิลของคุณ",
            ephemeral=True,
        )


class TrainingView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=300)
        self.add_item(TrainingSessionSelect(uid))
        self.add_item(DoneBtn(row=1))

    async def interaction_check(self, ix):
        if str(ix.user.id) != str(ix.user.id):  # always passes
            return False
        return True


# ── Admin Views ───────────────────────────────────────────────
class AddSessionModal(discord.ui.Modal, title="➕ เพิ่มหลักสูตรฝึก"):
    f_name = discord.ui.TextInput(label="ชื่อหลักสูตร", max_length=60)
    f_cat  = discord.ui.TextInput(label="หมวดสกิล ID (เช่น artifact, any)", placeholder="any", max_length=40)
    f_desc = discord.ui.TextInput(label="คำอธิบาย", style=discord.TextStyle.paragraph, required=False, max_length=300)
    f_emoji= discord.ui.TextInput(label="Emoji (ไม่บังคับ)", required=False, max_length=10)

    async def on_submit(self, ix: discord.Interaction):
        import uuid
        cfg = load_training_cfg()
        sid = uuid.uuid4().hex[:6]
        cfg.setdefault("sessions", []).append({
            "id": sid,
            "name": self.f_name.value.strip(),
            "category": (self.f_cat.value or "any").strip() or "any",
            "description": (self.f_desc.value or "").strip(),
            "emoji": (self.f_emoji.value or "📚").strip() or "📚",
        })
        save_training_cfg(cfg)
        await ix.response.send_message(f"✅ เพิ่มหลักสูตร **{self.f_name.value}** (ID: `{sid}`)", ephemeral=True)


class TrainingCostModal(discord.ui.Modal, title="💰 ตั้งค่าระบบฝึก"):
    f_cost = discord.ui.TextInput(label="ค่าใช้จ่ายต่อครั้ง", placeholder="200", max_length=10)
    f_cd   = discord.ui.TextInput(label="Cooldown (วินาที)", placeholder="3600", max_length=10)

    async def on_submit(self, ix: discord.Interaction):
        cfg = load_training_cfg()
        cfg["cost"] = max(0, _parse_int(self.f_cost.value, 200) or 200)
        cfg["cooldown_seconds"] = max(60, _parse_int(self.f_cd.value, 3600) or 3600)
        save_training_cfg(cfg)
        await ix.response.send_message(
            f"✅ Cost: `{cfg['cost']}` · CD: `{cfg['cooldown_seconds']}s`",
            ephemeral=True,
        )


class TrainingAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="ตั้งค่าราคา/CD", style=discord.ButtonStyle.primary, row=1)
    async def settings(self, ix, _b):
        cfg = load_training_cfg()
        m = TrainingCostModal()
        m.f_cost.default = str(cfg.get("cost", 200))
        m.f_cd.default = str(cfg.get("cooldown_seconds", 3600))
        await ix.response.send_modal(m)

    @discord.ui.button(label="เพิ่มหลักสูตร", style=discord.ButtonStyle.success, row=2)
    async def add(self, ix, _b):
        await ix.response.send_modal(AddSessionModal())


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="ฝึกสกิล", description="ฝึกฝนและเรียนรู้สกิลใหม่", guild=_ORION_GUILD_OBJ)
async def cmd_training(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    cfg = load_training_cfg()
    sessions = cfg.get("sessions", [])
    cost = cfg.get("cost", 200)
    embed = make_menu_embed(
        "📚 ฝึกสกิล",
        [
            (f"ค่าใช้จ่าย: {money_str(cost)}", "ต่อการฝึก 1 ครั้ง"),
            (f"หลักสูตร: `{len(sessions)}`", "เลือกจาก dropdown ด้านล่าง"),
        ],
        color=0xfdcb6e,
    )
    await interaction.response.send_message(
        embed=embed,
        view=TrainingView(uid),
        ephemeral=_eph("ฝึกสกิล"),
    )


@bot.tree.command(name="ฝึกแอดมิน", description="[Admin] จัดการระบบฝึกสกิล", guild=_ORION_GUILD_OBJ)
async def cmd_training_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cfg = load_training_cfg()
    sessions = cfg.get("sessions", [])
    lines = [f"• **{s['name']}** — หมวด `{s.get('category', 'any')}`" for s in sessions[:10]]
    embed = make_menu_embed(
        "Training Admin",
        [
            (f"Cost: `{cfg.get('cost', 200)}`  CD: `{cfg.get('cooldown_seconds', 3600)}s`", ""),
            (f"หลักสูตร: `{len(sessions)}`", "\n".join(lines) or "_ไม่มี_"),
        ],
        color=0xfdcb6e,
    )
    await interaction.response.send_message(embed=embed, view=TrainingAdminView(), ephemeral=True)
