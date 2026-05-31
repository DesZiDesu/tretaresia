# ============================================================
# ORION STATS PROGRESSION SYSTEM
# /ฝึกสถิติ — ระบบ Attribute Training (Endurance/Strength/Perception/Speed)
# ============================================================
import discord
import asyncio
import random
import time
import json

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    get_wallet, add_money, money_str, load_currency_cfg, _parse_int,
    cooldown_remaining, set_cooldown, format_cooldown,
)

STATS_FILE       = f"{ORION_DATA_DIR}/player_stats.json"
STATS_CONFIG_FILE = f"{ORION_DATA_DIR}/stats_config.json"

# Rank ladder — fixed order
STAT_RANKS = [
    "E-", "E", "E+",
    "D-", "D", "D+",
    "C-", "C", "C+",
    "B-", "B", "B+",
    "A-", "A", "A+",
    "S-", "S", "S+",
    "EX",
]

RANK_COLORS = {
    "E-": 0x95a5a6, "E": 0x95a5a6, "E+": 0x95a5a6,
    "D-": 0x27ae60, "D": 0x27ae60, "D+": 0x27ae60,
    "C-": 0x2980b9, "C": 0x2980b9, "C+": 0x2980b9,
    "B-": 0x8e44ad, "B": 0x8e44ad, "B+": 0x8e44ad,
    "A-": 0xe67e22, "A": 0xe67e22, "A+": 0xe67e22,
    "S-": 0xe74c3c, "S": 0xe74c3c, "S+": 0xe74c3c,
    "EX": 0xf1c40f,
}

STAT_NAMES = {
    "endurance":  ("Endurance", "🟢", "ความทนทาน — ทน/รับความเจ็บปวดได้ดีแค่ไหน"),
    "strength":   ("Strength",  "🔴", "พลัง — ความแข็งแกร่งและแรง"),
    "perception": ("Perception","🔵", "การรับรู้ — ความไวต่อสิ่งแวดล้อม"),
    "speed":      ("Speed",     "🟡", "ความเร็ว — ความคล่องแคล่วและปฏิกิริยา"),
}

DEFAULT_STATS_CONFIG = {
    "max_rank": "B+",
    "special_roles": [],
    "training_cost": 100,
    "training_cooldown_seconds": 3600,
    "xp_per_success": 20,
    "xp_per_fail": 5,
    "xp_to_rank_up": 100,
}


def load_stats_config() -> dict:
    cfg = load_json(STATS_CONFIG_FILE, {})
    changed = False
    for k, v in DEFAULT_STATS_CONFIG.items():
        if k not in cfg:
            cfg[k] = v; changed = True
    if changed:
        save_json(STATS_CONFIG_FILE, cfg)
    return cfg


def save_stats_config(cfg: dict):
    save_json(STATS_CONFIG_FILE, cfg)


def load_player_stats() -> dict:
    return load_json(STATS_FILE, {})


def save_player_stats(d: dict):
    save_json(STATS_FILE, d)


def ensure_player_stats(uid: str):
    data = load_player_stats()
    if uid not in data:
        data[uid] = {
            attr: {"rank_idx": 0, "xp": 0}
            for attr in STAT_NAMES
        }
        save_player_stats(data)


def get_player_stat(uid: str, attr: str) -> dict:
    ensure_player_stats(uid)
    return load_player_stats().get(uid, {}).get(attr, {"rank_idx": 0, "xp": 0})


def get_overall_rank_idx(uid: str) -> int:
    ensure_player_stats(uid)
    data = load_player_stats().get(uid, {})
    idxs = [data.get(attr, {}).get("rank_idx", 0) for attr in STAT_NAMES]
    return min(idxs) if idxs else 0


def get_max_rank_idx(member: discord.Member) -> int:
    cfg = load_stats_config()
    default_max = cfg.get("max_rank", "B+")
    default_idx = STAT_RANKS.index(default_max) if default_max in STAT_RANKS else 11

    special_roles = cfg.get("special_roles", [])
    user_role_ids = {str(r.id) for r in member.roles}
    if any(str(rid) in user_role_ids for rid in special_roles):
        return len(STAT_RANKS) - 1  # EX

    return default_idx


def _progress_bar(xp: int, xp_max: int, width: int = 20) -> str:
    filled = int((xp / max(1, xp_max)) * width)
    filled = min(filled, width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int((xp / max(1, xp_max)) * 100)
    return f"`[{bar}]` **{pct}%**"


def _stats_embed(uid: str, member: discord.Member) -> discord.Embed:
    ensure_player_stats(uid)
    data = load_player_stats().get(uid, {})
    cfg = load_stats_config()
    xp_max = cfg.get("xp_to_rank_up", 100)

    overall_idx = get_overall_rank_idx(uid)
    overall_rank = STAT_RANKS[overall_idx]
    color = RANK_COLORS.get(overall_rank, 0x6c5ce7)

    embed = discord.Embed(
        title=f"⚔️  Stats — {member.display_name}",
        description=f"🏆 **Overall Rank: `{overall_rank}`**",
        color=color,
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    for attr, (label, emoji, desc) in STAT_NAMES.items():
        stat = data.get(attr, {"rank_idx": 0, "xp": 0})
        rank_idx = int(stat.get("rank_idx", 0))
        xp = int(stat.get("xp", 0))
        rank = STAT_RANKS[rank_idx]
        bar = _progress_bar(xp, xp_max)
        at_max = rank_idx >= get_max_rank_idx(member)
        rank_display = f"`{rank}`" + (" ✦MAX" if at_max else "")
        embed.add_field(
            name=f"{emoji} {label}",
            value=f"{bar}\nRank: {rank_display}",
            inline=False,
        )

    max_rank = STAT_RANKS[get_max_rank_idx(member)]
    cost = cfg.get("training_cost", 100)
    cd = cfg.get("training_cooldown_seconds", 3600)
    embed.set_footer(
        text=f"Max Rank: {max_rank}  ·  Training Cost: {cost}  ·  Cooldown: {cd//60}นาที"
    )
    return embed


# ── Training Minigame: "Pattern Sequence" (Unique) ────────────
# Show a 3×2 grid with 3 highlighted cells. Player must click them in order.

GRID_LABELS = ["①", "②", "③", "④", "⑤", "⑥"]
GRID_ROWS   = [0, 0, 0, 1, 1, 1]  # ①②③ = row 0, ④⑤⑥ = row 1


class PatternSequenceView(discord.ui.View):
    """Player must tap 3 highlighted positions in the shown order"""
    def __init__(self, uid: str, attr: str, sequence: list, on_complete):
        super().__init__(timeout=30)
        self.uid = uid
        self.attr = attr
        self.sequence = sequence  # list of position indices (0-5) in order
        self.on_complete = on_complete
        self.progress = []  # positions clicked so far
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        for i, label in enumerate(GRID_LABELS):
            is_next = (len(self.progress) < len(self.sequence) and
                       self.sequence[len(self.progress)] == i)
            is_done = i in self.progress
            btn = _SeqBtn(i, label, is_done, self)
            btn.row = GRID_ROWS[i]
            self.add_item(btn)

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เกมของคุณ", ephemeral=True); return False
        return True

    async def _advance(self, ix, position: int):
        if not self.sequence:
            return
        expected = self.sequence[len(self.progress)]
        if position != expected:
            # Wrong tap — fail
            await ix.response.edit_message(
                content="❌ **ผิดลำดับ!** การฝึกล้มเหลว...",
                embed=None, view=None,
            )
            await self.on_complete(False)
            self.stop()
            return
        self.progress.append(position)
        if len(self.progress) >= len(self.sequence):
            await ix.response.edit_message(
                content="✅ **ถูกต้อง!** การฝึกสำเร็จ!",
                embed=None, view=None,
            )
            await self.on_complete(True)
            self.stop()
            return
        self._build_buttons()
        await ix.response.edit_message(
            content=f"Progress: {len(self.progress)}/{len(self.sequence)} ✓",
            view=self,
        )


class _SeqBtn(discord.ui.Button):
    def __init__(self, position: int, label: str, is_done: bool, parent):
        style = discord.ButtonStyle.success if is_done else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style)
        self.position = position
        self.parent = parent

    async def callback(self, ix: discord.Interaction):
        await self.parent._advance(ix, self.position)


async def run_training_minigame(interaction: discord.Interaction, attr: str) -> bool:
    """Run the Pattern Sequence minigame. Returns True if player succeeds."""
    # Generate a random sequence of 4 positions
    sequence = random.sample(range(6), 4)

    label_map = " → ".join(GRID_LABELS[i] for i in sequence)
    embed = discord.Embed(
        title=f"🧠 Training — Pattern Sequence",
        description=(
            f"**Attribute:** {STAT_NAMES[attr][0]}\n\n"
            f"จดจำลำดับนี้แล้วกดปุ่มให้ถูก:\n"
            f"## {label_map}\n\n"
            f"_คุณมีเวลา 5 วินาทีในการจำก่อนปุ่มจะปรากฏ..._"
        ),
        color=0x6c5ce7,
    )

    result_holder = {"success": None}
    event = asyncio.Event()

    async def on_complete(success: bool):
        result_holder["success"] = success
        event.set()

    # Show sequence first (no buttons yet)
    await interaction.followup.send(embed=embed, ephemeral=True)
    await asyncio.sleep(5)

    # Now show buttons
    game_view = PatternSequenceView(str(interaction.user.id), attr, sequence, on_complete)
    await interaction.followup.send(
        f"🎯 กดปุ่มตามลำดับ: **{label_map}**",
        view=game_view,
        ephemeral=True,
    )

    try:
        await asyncio.wait_for(event.wait(), timeout=35)
    except asyncio.TimeoutError:
        result_holder["success"] = False

    return result_holder.get("success", False)


# ── Attribute Training ────────────────────────────────────────
class TrainAttrSelect(discord.ui.Select):
    def __init__(self, uid: str, member: discord.Member):
        self.uid = uid
        self.member = member
        options = []
        for attr, (label, emoji, desc) in STAT_NAMES.items():
            stat = get_player_stat(uid, attr)
            rank = STAT_RANKS[stat["rank_idx"]]
            options.append(discord.SelectOption(
                label=f"{label} — Rank {rank}",
                value=attr,
                description=desc[:80],
                emoji=emoji,
            ))
        super().__init__(placeholder="🏋️ เลือก Attribute ที่จะฝึก...", options=options)

    async def callback(self, ix: discord.Interaction):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return
        attr = self.values[0]

        # Cooldown check
        cd_key = f"stat_train_{attr}"
        remaining = cooldown_remaining(self.uid, cd_key)
        if remaining > 0:
            await ix.response.send_message(
                f"⏳ Cooldown: **{format_cooldown(remaining)}** ก่อนฝึก {STAT_NAMES[attr][0]} ได้อีกครั้ง",
                ephemeral=True,
            ); return

        cfg = load_stats_config()
        cost = cfg.get("training_cost", 100)
        max_idx = get_max_rank_idx(self.member)

        stat = get_player_stat(self.uid, attr)
        if stat["rank_idx"] >= max_idx:
            await ix.response.send_message(
                f"⚠️ {STAT_NAMES[attr][0]} ถึง Max Rank แล้ว (`{STAT_RANKS[max_idx]}`)",
                ephemeral=True,
            ); return

        if get_wallet(self.uid) < cost:
            await ix.response.send_message(
                f"❌ เงินไม่พอ — ต้องการ {money_str(cost)} ในการฝึก",
                ephemeral=True,
            ); return

        # Deduct money + set cooldown first
        add_money(self.uid, -cost)
        cd_secs = cfg.get("training_cooldown_seconds", 3600)
        set_cooldown(self.uid, cd_key, cd_secs)

        # Defer and run minigame
        await ix.response.defer(ephemeral=True)
        success = await run_training_minigame(ix, attr)

        xp_gain = cfg.get("xp_per_success", 20) if success else cfg.get("xp_per_fail", 5)
        xp_max = cfg.get("xp_to_rank_up", 100)

        data = load_player_stats()
        ensure_player_stats(self.uid)
        data = load_player_stats()
        stat_data = data[self.uid][attr]
        stat_data["xp"] = int(stat_data.get("xp", 0)) + xp_gain

        ranked_up = False
        while stat_data["xp"] >= xp_max and stat_data["rank_idx"] < max_idx:
            stat_data["xp"] -= xp_max
            stat_data["rank_idx"] += 1
            ranked_up = True

        stat_data["xp"] = min(stat_data["xp"], xp_max - 1)
        save_player_stats(data)

        attr_label, emoji, _ = STAT_NAMES[attr]
        new_rank = STAT_RANKS[stat_data["rank_idx"]]

        result_msg = (
            f"{'✅ สำเร็จ!' if success else '❌ ล้มเหลว'} ได้รับ **{xp_gain} XP** ใน **{attr_label}**\n"
            f"XP: `{stat_data['xp']}/{xp_max}`  ·  Rank: `{new_rank}`"
        )
        if ranked_up:
            result_msg += f"\n🎉 **RANK UP!** {attr_label} เพิ่มเป็น `{new_rank}`!"

        await ix.followup.send(result_msg, ephemeral=True)


class StatsView(discord.ui.View):
    def __init__(self, uid: str, member: discord.Member):
        super().__init__(timeout=300)
        self.uid = uid
        self.member = member
        self.add_item(TrainAttrSelect(uid, member))
        self.add_item(DoneBtn(row=1))

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return False
        return True


# ── Stats Config Admin ────────────────────────────────────────
class StatsConfigModal(discord.ui.Modal, title="⚙️ ตั้งค่าระบบ Stats"):
    f_max_rank = discord.ui.TextInput(
        label="Max Rank (E-, E, E+, D-, ... B+, A+, S+, EX)",
        placeholder="B+", max_length=3,
    )
    f_cost = discord.ui.TextInput(label="ค่าฝึก/ครั้ง", placeholder="100", max_length=10)
    f_cd   = discord.ui.TextInput(label="Cooldown (วินาที)", placeholder="3600", max_length=10)
    f_xp_s = discord.ui.TextInput(label="XP ต่อ Success", placeholder="20", max_length=5)
    f_xp_f = discord.ui.TextInput(label="XP ต่อ Fail", placeholder="5", max_length=5)

    async def on_submit(self, ix: discord.Interaction):
        rank = self.f_max_rank.value.strip()
        if rank not in STAT_RANKS:
            await ix.response.send_message(f"❌ ไม่พบ rank `{rank}` — ใช้: {', '.join(STAT_RANKS)}", ephemeral=True); return
        cfg = load_stats_config()
        cfg["max_rank"] = rank
        cfg["training_cost"] = max(0, _parse_int(self.f_cost.value, 100) or 100)
        cfg["training_cooldown_seconds"] = max(60, _parse_int(self.f_cd.value, 3600) or 3600)
        cfg["xp_per_success"] = max(1, _parse_int(self.f_xp_s.value, 20) or 20)
        cfg["xp_per_fail"] = max(0, _parse_int(self.f_xp_f.value, 5) or 5)
        save_stats_config(cfg)
        await ix.response.send_message(
            f"✅ Max Rank: `{rank}`  Cost: `{cfg['training_cost']}`  "
            f"CD: `{cfg['training_cooldown_seconds']}s`  XP: `{cfg['xp_per_success']}/{cfg['xp_per_fail']}`",
            ephemeral=True,
        )


class SpecialRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="เลือก role ที่ไม่มี rank cap (เช่น Deity)...", min_values=0, max_values=10)

    async def callback(self, ix: discord.Interaction):
        cfg = load_stats_config()
        cfg["special_roles"] = [str(r.id) for r in self.values]
        save_stats_config(cfg)
        names = ", ".join(r.name for r in self.values) or "_(ล้างแล้ว)_"
        await ix.response.send_message(f"✅ Special roles: {names}", ephemeral=True)


class StatsAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(SpecialRoleSelect())

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="ตั้งค่า Stats", style=discord.ButtonStyle.primary, row=2)
    async def config(self, ix, _b):
        cfg = load_stats_config()
        modal = StatsConfigModal()
        modal.f_max_rank.default = cfg.get("max_rank", "B+")
        modal.f_cost.default = str(cfg.get("training_cost", 100))
        modal.f_cd.default = str(cfg.get("training_cooldown_seconds", 3600))
        modal.f_xp_s.default = str(cfg.get("xp_per_success", 20))
        modal.f_xp_f.default = str(cfg.get("xp_per_fail", 5))
        await ix.response.send_modal(modal)


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="สถิติ", description="ดู Stats และฝึก Attributes", guild=_ORION_GUILD_OBJ)
async def cmd_stats(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    ensure_player_stats(uid)
    await interaction.response.send_message(
        embed=_stats_embed(uid, interaction.user),
        view=StatsView(uid, interaction.user),
        ephemeral=_eph("สถิติ"),
    )


@bot.tree.command(name="สถิติแอดมิน", description="[Admin] ตั้งค่าระบบ Stats", guild=_ORION_GUILD_OBJ)
async def cmd_stats_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cfg = load_stats_config()
    idx = STAT_RANKS.index(cfg.get("max_rank", "B+")) if cfg.get("max_rank") in STAT_RANKS else 11
    embed = make_menu_embed(
        "Stats Admin",
        [
            (f"Max Rank: `{cfg.get('max_rank', 'B+')}`", f"Max index: {idx}/{len(STAT_RANKS)-1}"),
            (f"Training Cost: `{cfg.get('training_cost', 100)}`", "เงินที่ต้องจ่ายต่อการฝึก 1 ครั้ง"),
            (f"Cooldown: `{cfg.get('training_cooldown_seconds', 3600)}s`", f"= {cfg.get('training_cooldown_seconds', 3600)//60} นาที"),
            (f"XP Success/Fail: `{cfg.get('xp_per_success',20)}/{cfg.get('xp_per_fail',5)}`", "XP ที่ได้ต่อ success/fail"),
        ],
        color=0x6c5ce7,
    )
    await interaction.response.send_message(embed=embed, view=StatsAdminView(), ephemeral=True)
