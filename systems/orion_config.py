# ============================================================
# ORION CONFIG — /config (unified paginated settings)
# ============================================================
import discord
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _eph, TOGGLEABLE_COMMANDS, load_settings, save_settings,
    _parse_int, load_character_cfg, save_character_cfg,
)

STATS_CFG_FILE        = f"{ORION_DATA_DIR}/stats_config.json"
CREATION_CFG_FILE     = f"{ORION_DATA_DIR}/creation_config.json"
SCAVENGE_CFG_FILE     = f"{ORION_DATA_DIR}/scavenge_config.json"
TRAINING_CFG_FILE     = f"{ORION_DATA_DIR}/training_config.json"

STAT_RANKS = ["E-","E","E+","D-","D","D+","C-","C","C+","B-","B","B+","A-","A","A+","S-","S","S+","EX"]

DEFAULT_STATS_CFG = {
    "max_rank": "B+",
    "special_roles": [],
    "training_cost": 100,
    "training_cooldown_seconds": 3600,
    "xp_per_success": 20,
    "xp_per_fail": 5,
    "xp_to_rank_up": 100,
}


def _load_stats_cfg() -> dict:
    return load_json(STATS_CFG_FILE, dict(DEFAULT_STATS_CFG))


def _save_stats_cfg(d: dict):
    save_json(STATS_CFG_FILE, d)


def _load_creation_cfg() -> dict:
    return load_json(CREATION_CFG_FILE, {"creator_role_ids": [], "review_channel_id": None})


def _save_creation_cfg(d: dict):
    save_json(CREATION_CFG_FILE, d)


def _load_scavenge_cfg() -> dict:
    return load_json(SCAVENGE_CFG_FILE, {"cooldown_seconds": 1800})


def _save_scavenge_cfg(d: dict):
    save_json(SCAVENGE_CFG_FILE, d)


def _load_training_cfg() -> dict:
    return load_json(TRAINING_CFG_FILE, {"cost": 200, "cooldown_seconds": 3600})


def _save_training_cfg(d: dict):
    save_json(TRAINING_CFG_FILE, d)


# ── Page definitions ──────────────────────────────────────────
PAGES = [
    ("visibility",  "👁️ Visibility"),
    ("channels",    "📡 Channels"),
    ("character",   "👤 Character Creation"),
    ("stats",       "📊 Stats System"),
    ("training",    "⚔️ Training & Scavenge"),
    ("creation",    "🔨 Creation System"),
]


def _build_page_embed(page_key: str) -> discord.Embed:
    if page_key == "visibility":
        cfg = load_settings()
        public = set(cfg.get("public_commands", []))
        lines = []
        for cmd_name, desc in TOGGLEABLE_COMMANDS:
            icon = "🌐" if cmd_name in public else "🔒"
            lines.append(f"{icon} `/{cmd_name}` — {desc}")
        embed = discord.Embed(
            title="⚙️ Config — 👁️ Visibility",
            description="🌐 = Public (ทุกคนเห็น) · 🔒 = Private (เห็นแค่คุณ)\n\n" + "\n".join(lines),
            color=0x95a5a6,
        )

    elif page_key == "channels":
        char_cfg = load_character_cfg()
        creation_cfg = _load_creation_cfg()
        forum_id = char_cfg.get("forum_channel_id")
        review_id = creation_cfg.get("review_channel_id")
        embed = discord.Embed(
            title="⚙️ Config — 📡 Channels",
            description=(
                "**Forum Channel** (เปิด thread ตัวละคร):\n"
                + (f"<#{forum_id}>" if forum_id else "_ยังไม่ตั้ง_")
                + "\n\n**Review Channel** (Creation System):\n"
                + (f"<#{review_id}>" if review_id else "_ยังไม่ตั้ง_")
            ),
            color=0x3498db,
        )

    elif page_key == "character":
        char_cfg = load_character_cfg()
        forum_id = char_cfg.get("forum_channel_id")
        admin_id = char_cfg.get("admin_role_id")
        char_role_id = char_cfg.get("character_role_id")
        embed = discord.Embed(
            title="⚙️ Config — 👤 Character Creation",
            description=(
                "**Forum Channel** (เปิด thread):\n"
                + (f"<#{forum_id}>" if forum_id else "_ยังไม่ตั้ง_")
                + "\n\n**Admin Role** (ping เมื่อมี application):\n"
                + (f"<@&{admin_id}>" if admin_id else "_ยังไม่ตั้ง_")
                + "\n\n**Character Role** (มอบเมื่อ Approve):\n"
                + (f"<@&{char_role_id}>" if char_role_id else "_ยังไม่ตั้ง_")
            ),
            color=0x6c5ce7,
        )

    elif page_key == "stats":
        cfg = _load_stats_cfg()
        special = cfg.get("special_roles", [])
        role_txt = " ".join(f"<@&{r}>" for r in special) if special else "_ยังไม่มี_"
        embed = discord.Embed(
            title="⚙️ Config — 📊 Stats System",
            description=(
                f"**Max Rank Cap**: `{cfg.get('max_rank', 'B+')}`\n"
                f"**Stats Training Cost**: `{cfg.get('training_cost', 100):,}` เหรียญ\n"
                f"**Stats Training Cooldown**: `{cfg.get('training_cooldown_seconds', 3600)}` วินาที\n"
                f"**XP per Success**: `{cfg.get('xp_per_success', 20)}`\n"
                f"**XP per Fail**: `{cfg.get('xp_per_fail', 5)}`\n"
                f"**XP to Rank Up**: `{cfg.get('xp_to_rank_up', 100)}`\n\n"
                f"**Special Roles** (ไม่จำกัด rank):\n{role_txt}"
            ),
            color=0x27ae60,
        )

    elif page_key == "training":
        train_cfg = _load_training_cfg()
        scav_cfg = _load_scavenge_cfg()
        embed = discord.Embed(
            title="⚙️ Config — ⚔️ Training & Scavenge",
            description=(
                f"**Skill Training Cost**: `{train_cfg.get('cost', 200):,}` เหรียญ\n"
                f"**Skill Training Cooldown**: `{train_cfg.get('cooldown_seconds', 3600)}` วินาที\n\n"
                f"**Scavenge Cooldown**: `{scav_cfg.get('cooldown_seconds', 1800)}` วินาที"
            ),
            color=0xe67e22,
        )

    elif page_key == "creation":
        cfg = _load_creation_cfg()
        creator_roles = cfg.get("creator_role_ids", [])
        review_id = cfg.get("review_channel_id")
        role_txt = " ".join(f"<@&{r}>" for r in creator_roles) if creator_roles else "_ยังไม่ตั้ง_"
        embed = discord.Embed(
            title="⚙️ Config — 🔨 Creation System",
            description=(
                f"**Creator Roles** (สร้างของได้):\n{role_txt}\n\n"
                "**Review Channel** (ส่งรีวิว):\n"
                + (f"<#{review_id}>" if review_id else "_ยังไม่ตั้ง_")
            ),
            color=0xe74c3c,
        )

    else:
        embed = discord.Embed(title="⚙️ Config", color=0x95a5a6)

    page_label = dict(PAGES).get(page_key, page_key)
    embed.set_footer(text=f"Page: {page_label}")
    return embed


# ── Page navigation select ─────────────────────────────────────
class PageSelect(discord.ui.Select):
    def __init__(self, current_page: str):
        options = [
            discord.SelectOption(label=label, value=key, default=(key == current_page))
            for key, label in PAGES
        ]
        super().__init__(placeholder="📋 เปลี่ยนหน้า...", options=options, row=0)

    async def callback(self, ix: discord.Interaction):
        page = self.values[0]
        await ix.response.edit_message(embed=_build_page_embed(page), view=ConfigView(page))


# ── Visibility multi-select ───────────────────────────────────
class VisibilitySelect(discord.ui.Select):
    def __init__(self):
        cfg = load_settings()
        public = set(cfg.get("public_commands", []))
        options = [
            discord.SelectOption(
                label=f"/{cmd_name}"[:100],
                value=cmd_name,
                description=desc[:80],
                default=(cmd_name in public),
            )
            for cmd_name, desc in TOGGLEABLE_COMMANDS
        ]
        super().__init__(
            placeholder="✅ ติ๊กคำสั่งที่ต้องการให้ public...",
            options=options,
            min_values=0,
            max_values=len(options),
            row=2,
        )

    async def callback(self, ix: discord.Interaction):
        cfg = load_settings()
        cfg["public_commands"] = list(self.values)
        save_settings(cfg)
        await ix.response.edit_message(
            embed=_build_page_embed("visibility"),
            view=ConfigView("visibility"),
        )


# ── Modals ─────────────────────────────────────────────────────
class ChannelIDModal(discord.ui.Modal, title="ตั้ง Channel IDs"):
    f_forum  = discord.ui.TextInput(label="Forum Channel ID (Character Creation)", required=False, max_length=25)
    f_review = discord.ui.TextInput(label="Review Channel ID (Creation System)",  required=False, max_length=25)

    async def on_submit(self, ix: discord.Interaction):
        char_cfg     = load_character_cfg()
        creation_cfg = _load_creation_cfg()
        v = self.f_forum.value.strip()
        if v:
            char_cfg["forum_channel_id"] = int(v) if v.isdigit() else None
        v = self.f_review.value.strip()
        if v:
            creation_cfg["review_channel_id"] = int(v) if v.isdigit() else None
        save_character_cfg(char_cfg)
        _save_creation_cfg(creation_cfg)
        await ix.response.edit_message(embed=_build_page_embed("channels"), view=ConfigView("channels"))


class CharacterCfgModal(discord.ui.Modal, title="ตั้ง Character Creation"):
    f_forum = discord.ui.TextInput(label="Forum Channel ID",        required=False, max_length=25)
    f_admin = discord.ui.TextInput(label="Admin Role ID",           required=False, max_length=25)
    f_role  = discord.ui.TextInput(label="Character Role ID (มอบหลัง Approve)", required=False, max_length=25)

    async def on_submit(self, ix: discord.Interaction):
        cfg = load_character_cfg()
        v = self.f_forum.value.strip()
        if v: cfg["forum_channel_id"]  = int(v) if v.isdigit() else None
        v = self.f_admin.value.strip()
        if v: cfg["admin_role_id"]     = int(v) if v.isdigit() else None
        v = self.f_role.value.strip()
        if v: cfg["character_role_id"] = int(v) if v.isdigit() else None
        save_character_cfg(cfg)
        await ix.response.edit_message(embed=_build_page_embed("character"), view=ConfigView("character"))


class StatsBasicModal(discord.ui.Modal, title="Stats System — ตั้งค่าทั่วไป"):
    f_cost    = discord.ui.TextInput(label="Stats Training Cost (เหรียญ)",       placeholder="100",  max_length=10)
    f_cd      = discord.ui.TextInput(label="Stats Training Cooldown (วินาที)",   placeholder="3600", max_length=10)
    f_xp_ok   = discord.ui.TextInput(label="XP per Success",                     placeholder="20",   max_length=5)
    f_xp_fail = discord.ui.TextInput(label="XP per Fail",                        placeholder="5",    max_length=5)
    f_xp_up   = discord.ui.TextInput(label="XP to Rank Up",                      placeholder="100",  max_length=5)

    async def on_submit(self, ix: discord.Interaction):
        cfg = _load_stats_cfg()
        v = self.f_cost.value.strip()
        if v: cfg["training_cost"]               = max(0,  _parse_int(v, 100) or 100)
        v = self.f_cd.value.strip()
        if v: cfg["training_cooldown_seconds"]   = max(60, _parse_int(v, 3600) or 3600)
        v = self.f_xp_ok.value.strip()
        if v: cfg["xp_per_success"]              = max(1,  _parse_int(v, 20) or 20)
        v = self.f_xp_fail.value.strip()
        if v: cfg["xp_per_fail"]                 = max(0,  _parse_int(v, 5) or 0)
        v = self.f_xp_up.value.strip()
        if v: cfg["xp_to_rank_up"]               = max(10, _parse_int(v, 100) or 100)
        _save_stats_cfg(cfg)
        await ix.response.edit_message(embed=_build_page_embed("stats"), view=ConfigView("stats"))


class StatsMaxRankModal(discord.ui.Modal, title="Stats — Max Rank Cap"):
    f_rank = discord.ui.TextInput(label="Max Rank (E- … EX)", placeholder="B+", max_length=5)

    async def on_submit(self, ix: discord.Interaction):
        rank = self.f_rank.value.strip().upper()
        if rank not in STAT_RANKS:
            await ix.response.send_message(
                f"❌ Rank ไม่ถูกต้อง — ต้องเป็นหนึ่งใน:\n`{', '.join(STAT_RANKS)}`", ephemeral=True
            ); return
        cfg = _load_stats_cfg()
        cfg["max_rank"] = rank
        _save_stats_cfg(cfg)
        await ix.response.edit_message(embed=_build_page_embed("stats"), view=ConfigView("stats"))


class StatsSpecialRoleModal(discord.ui.Modal, title="Stats — Special Role"):
    f_add = discord.ui.TextInput(label="เพิ่ม Role ID (ไม่จำกัด rank)", required=False, max_length=25)
    f_rm  = discord.ui.TextInput(label="ลบ Role ID",                    required=False, max_length=25)

    async def on_submit(self, ix: discord.Interaction):
        cfg = _load_stats_cfg()
        roles = cfg.setdefault("special_roles", [])
        add_v = self.f_add.value.strip()
        if add_v and add_v.isdigit() and add_v not in roles:
            roles.append(add_v)
        rm_v = self.f_rm.value.strip()
        if rm_v in roles:
            roles.remove(rm_v)
        _save_stats_cfg(cfg)
        await ix.response.edit_message(embed=_build_page_embed("stats"), view=ConfigView("stats"))


class TrainingScavengeModal(discord.ui.Modal, title="Training & Scavenge — ตั้งค่า"):
    f_train_cost = discord.ui.TextInput(label="Skill Training Cost (เหรียญ)",      placeholder="200",  max_length=10)
    f_train_cd   = discord.ui.TextInput(label="Skill Training Cooldown (วินาที)", placeholder="3600", max_length=10)
    f_scav_cd    = discord.ui.TextInput(label="Scavenge Cooldown (วินาที)",        placeholder="1800", max_length=10)

    async def on_submit(self, ix: discord.Interaction):
        train_cfg = _load_training_cfg()
        scav_cfg  = _load_scavenge_cfg()
        v = self.f_train_cost.value.strip()
        if v: train_cfg["cost"]             = max(0,  _parse_int(v, 200) or 200)
        v = self.f_train_cd.value.strip()
        if v: train_cfg["cooldown_seconds"] = max(60, _parse_int(v, 3600) or 3600)
        v = self.f_scav_cd.value.strip()
        if v: scav_cfg["cooldown_seconds"]  = max(60, _parse_int(v, 1800) or 1800)
        _save_training_cfg(train_cfg)
        _save_scavenge_cfg(scav_cfg)
        await ix.response.edit_message(embed=_build_page_embed("training"), view=ConfigView("training"))


class CreationCfgModal(discord.ui.Modal, title="Creation System — ตั้งค่า"):
    f_review   = discord.ui.TextInput(label="Review Channel ID",        required=False, max_length=25)
    f_add_role = discord.ui.TextInput(label="เพิ่ม Creator Role ID",    required=False, max_length=25)
    f_rm_role  = discord.ui.TextInput(label="ลบ Creator Role ID",       required=False, max_length=25)

    async def on_submit(self, ix: discord.Interaction):
        cfg = _load_creation_cfg()
        v = self.f_review.value.strip()
        if v:
            cfg["review_channel_id"] = int(v) if v.isdigit() else None
        roles = cfg.setdefault("creator_role_ids", [])
        add_v = self.f_add_role.value.strip()
        if add_v and add_v.isdigit() and add_v not in roles:
            roles.append(add_v)
        rm_v = self.f_rm_role.value.strip()
        if rm_v in roles:
            roles.remove(rm_v)
        _save_creation_cfg(cfg)
        await ix.response.edit_message(embed=_build_page_embed("creation"), view=ConfigView("creation"))


# ── Main ConfigView ────────────────────────────────────────────
class ConfigView(discord.ui.View):
    def __init__(self, page: str = "visibility"):
        super().__init__(timeout=300)
        self.page = page
        self.add_item(PageSelect(page))
        self.add_item(DoneBtn(row=1))
        self._add_page_items(page)

    def _add_page_items(self, page: str):
        if page == "visibility":
            self.add_item(VisibilitySelect())

        elif page == "channels":
            btn = discord.ui.Button(label="✏️ ตั้ง Channels", style=discord.ButtonStyle.primary, row=2)
            async def _cb(ix): await ix.response.send_modal(ChannelIDModal())
            btn.callback = _cb
            self.add_item(btn)

        elif page == "character":
            btn = discord.ui.Button(label="✏️ ตั้ง Character Config", style=discord.ButtonStyle.primary, row=2)
            async def _cb(ix): await ix.response.send_modal(CharacterCfgModal())
            btn.callback = _cb
            self.add_item(btn)

        elif page == "stats":
            btn1 = discord.ui.Button(label="✏️ ตั้งค่าทั่วไป",        style=discord.ButtonStyle.primary, row=2)
            btn2 = discord.ui.Button(label="🏆 Max Rank",               style=discord.ButtonStyle.primary, row=2)
            btn3 = discord.ui.Button(label="⭐ Special Roles",          style=discord.ButtonStyle.success, row=3)
            btn4 = discord.ui.Button(label="🗑️ ล้าง Special Roles",     style=discord.ButtonStyle.danger,  row=3)

            async def _cb1(ix): await ix.response.send_modal(StatsBasicModal())
            async def _cb2(ix): await ix.response.send_modal(StatsMaxRankModal())
            async def _cb3(ix): await ix.response.send_modal(StatsSpecialRoleModal())
            async def _cb4(ix):
                cfg = _load_stats_cfg(); cfg["special_roles"] = []; _save_stats_cfg(cfg)
                await ix.response.edit_message(embed=_build_page_embed("stats"), view=ConfigView("stats"))

            btn1.callback = _cb1; btn2.callback = _cb2; btn3.callback = _cb3; btn4.callback = _cb4
            self.add_item(btn1); self.add_item(btn2); self.add_item(btn3); self.add_item(btn4)

        elif page == "training":
            btn = discord.ui.Button(label="✏️ ตั้งค่า", style=discord.ButtonStyle.primary, row=2)
            async def _cb(ix): await ix.response.send_modal(TrainingScavengeModal())
            btn.callback = _cb
            self.add_item(btn)

        elif page == "creation":
            btn = discord.ui.Button(label="✏️ ตั้งค่า Creation System", style=discord.ButtonStyle.primary, row=2)
            async def _cb(ix): await ix.response.send_modal(CreationCfgModal())
            btn.callback = _cb
            self.add_item(btn)

    async def interaction_check(self, ix: discord.Interaction) -> bool:
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True


@bot.tree.command(name="config", description="[Admin] ตั้งค่าทั้งหมดของบอทในที่เดียว", guild=_ORION_GUILD_OBJ)
async def cmd_config(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    await interaction.response.send_message(
        embed=_build_page_embed("visibility"),
        view=ConfigView("visibility"),
        ephemeral=True,
    )
