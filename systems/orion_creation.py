# ============================================================
# ORION CREATION SYSTEM — /สร้าง (Blacksmith/Creator role)
# สร้าง Artifact Skill หรือไอเทม → Admin review → Approve/Decline
# ============================================================
import discord
import json
import time
import datetime

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    load_skill_cats, get_skill_cat, _parse_int,
)

CREATION_FILE   = f"{ORION_DATA_DIR}/creation_requests.json"
CREATION_CFG    = f"{ORION_DATA_DIR}/creation_config.json"

DEFAULT_CREATION_CFG = {
    "creator_role_ids": [],
    "review_channel_id": None,
}


def load_creation_cfg() -> dict:
    cfg = load_json(CREATION_CFG, {})
    for k, v in DEFAULT_CREATION_CFG.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def save_creation_cfg(cfg: dict):
    save_json(CREATION_CFG, cfg)


def load_creation_requests() -> list:
    return load_json(CREATION_FILE, [])


def save_creation_requests(d: list):
    save_json(CREATION_FILE, d)


def _has_creator_role(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    cfg = load_creation_cfg()
    role_ids = {str(r) for r in cfg.get("creator_role_ids", [])}
    if not role_ids:
        return False
    return any(str(r.id) in role_ids for r in member.roles)


def _req_embed(req: dict, title_prefix: str = "") -> discord.Embed:
    req_type = req.get("type", "item")
    uid = req.get("uid", "?")
    color = 0xe67e22 if req_type == "item" else 0x6c5ce7

    embed = discord.Embed(
        title=f"{title_prefix}{'🗡️ Item' if req_type == 'item' else '✨ Artifact Skill'} Request — {req.get('name', '?')}",
        color=color,
    )
    embed.add_field(name="ผู้สร้าง", value=f"<@{uid}>", inline=True)
    embed.add_field(name="ประเภท", value=f"`{req_type}`", inline=True)
    embed.add_field(name="ชื่อ", value=f"`{req.get('name', '?')}`", inline=True)
    if req.get("emoji"):
        embed.add_field(name="Emoji", value=req["emoji"], inline=True)
    if req.get("description"):
        embed.add_field(name="คำอธิบาย", value=req["description"][:1000], inline=False)
    if req_type == "skill":
        if req.get("context"):
            embed.add_field(name="Context/Effect", value=req["context"][:1000], inline=False)
    if req.get("image_url"):
        embed.set_thumbnail(url=req["image_url"])
    embed.set_footer(text=f"ID: {req.get('id', '?')} · {req.get('created_at', '—')}")
    return embed


class CreationTypeView(discord.ui.View):
    """Choose: create artifact skill OR item"""
    def __init__(self, uid: str):
        super().__init__(timeout=120)
        self.uid = uid

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return False
        return True

    @discord.ui.button(label="✨ Artifact Skill", style=discord.ButtonStyle.primary, row=0)
    async def create_skill(self, ix, _b):
        await ix.response.send_modal(CreateSkillRequestModal(self.uid))

    @discord.ui.button(label="🗡️ ไอเทม", style=discord.ButtonStyle.success, row=0)
    async def create_item(self, ix, _b):
        await ix.response.send_modal(CreateItemRequestModal(self.uid))

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)


class CreateSkillRequestModal(discord.ui.Modal, title="✨ สร้าง Artifact Skill"):
    f_name    = discord.ui.TextInput(label="ชื่อสกิล", max_length=80)
    f_emoji   = discord.ui.TextInput(label="Icon (emoji หรือ URL รูป)", required=False, max_length=400)
    f_context = discord.ui.TextInput(
        label="คำอธิบาย / Effect ของสกิล",
        style=discord.TextStyle.paragraph, max_length=1500,
    )
    f_origin  = discord.ui.TextInput(
        label="ประเภท (ว่าง = Artifact)",
        placeholder="Artifact", required=False, max_length=40,
    )

    def __init__(self, uid: str):
        super().__init__()
        self.uid = uid

    async def on_submit(self, ix: discord.Interaction):
        import uuid
        rid = uuid.uuid4().hex[:8]
        icon = (self.f_emoji.value or "").strip()
        emoji = icon if not icon.lower().startswith("http") else "✨"
        icon_url = icon if icon.lower().startswith("http") else ""

        req = {
            "id": rid,
            "uid": self.uid,
            "type": "skill",
            "name": self.f_name.value.strip(),
            "emoji": emoji,
            "icon_url": icon_url,
            "context": self.f_context.value.strip(),
            "origin_type": (self.f_origin.value or "Artifact").strip() or "Artifact",
            "status": "pending",
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        reqs = load_creation_requests()
        reqs.append(req)
        save_creation_requests(reqs)

        await ix.response.send_message(
            f"✅ ส่งคำขอสร้าง **{req['name']}** (ID: `{rid}`) แล้ว — รอแอดมิน review",
            ephemeral=True,
        )
        await _send_review(ix.guild, req)


class CreateItemRequestModal(discord.ui.Modal, title="🗡️ สร้างไอเทม"):
    f_name  = discord.ui.TextInput(label="ชื่อไอเทม", max_length=80)
    f_emoji = discord.ui.TextInput(label="Emoji", placeholder="⚔️", required=False, max_length=10)
    f_desc  = discord.ui.TextInput(
        label="คำอธิบาย",
        style=discord.TextStyle.paragraph, max_length=1000,
    )
    f_image = discord.ui.TextInput(
        label="URL รูปภาพ (ไม่บังคับ)",
        required=False, max_length=400,
    )
    f_price = discord.ui.TextInput(label="ราคาขาย (0 = ไม่มีราคา)", placeholder="0", max_length=10)

    def __init__(self, uid: str):
        super().__init__()
        self.uid = uid

    async def on_submit(self, ix: discord.Interaction):
        import uuid
        rid = uuid.uuid4().hex[:8]
        req = {
            "id": rid,
            "uid": self.uid,
            "type": "item",
            "name": self.f_name.value.strip(),
            "emoji": (self.f_emoji.value or "📦").strip() or "📦",
            "description": self.f_desc.value.strip(),
            "image_url": (self.f_image.value or "").strip(),
            "sell_price": max(0, _parse_int(self.f_price.value, 0) or 0),
            "status": "pending",
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        reqs = load_creation_requests()
        reqs.append(req)
        save_creation_requests(reqs)

        await ix.response.send_message(
            f"✅ ส่งคำขอสร้างไอเทม **{req['name']}** (ID: `{rid}`) แล้ว — รอแอดมิน review",
            ephemeral=True,
        )
        await _send_review(ix.guild, req)


async def _send_review(guild: discord.Guild, req: dict):
    cfg = load_creation_cfg()
    ch_id = cfg.get("review_channel_id")
    if not ch_id or not guild:
        return
    ch = guild.get_channel(int(ch_id))
    if not ch:
        return
    embed = _req_embed(req, "📋 คำขอใหม่: ")
    view = CreationReviewView(req["id"])
    try:
        msg = await ch.send(embed=embed, view=view)
        # Store message id for reference
        reqs = load_creation_requests()
        r = next((x for x in reqs if x["id"] == req["id"]), None)
        if r:
            r["review_message_id"] = str(msg.id)
            r["review_channel_id"] = str(ch_id)
            save_creation_requests(reqs)
    except Exception as e:
        print(f"[Creation] send review failed: {e}")


class CreationReviewView(discord.ui.View):
    """Persistent view for admin review buttons"""
    def __init__(self, req_id: str):
        super().__init__(timeout=None)
        self.req_id = req_id

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="✅ อนุมัติ", style=discord.ButtonStyle.success, custom_id="creation_approve")
    async def approve(self, ix, _b):
        await self._resolve(ix, True, "")

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger, custom_id="creation_decline")
    async def decline(self, ix, _b):
        await ix.response.send_modal(CreationDeclineModal(self.req_id))

    async def _resolve(self, ix: discord.Interaction, approved: bool, reason: str):
        reqs = load_creation_requests()
        req = next((r for r in reqs if r["id"] == self.req_id), None)
        if not req or req.get("status") != "pending":
            await ix.response.send_message("❌ คำขอนี้ถูกจัดการไปแล้ว", ephemeral=True); return

        req["status"] = "approved" if approved else "declined"
        req["resolved_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        req["reason"] = reason
        save_creation_requests(reqs)

        if approved:
            await _execute_creation(ix.guild, req)

        # Edit review message
        try:
            embed = _req_embed(req, "✅ อนุมัติ: " if approved else "❌ ปฏิเสธ: ")
            await ix.response.edit_message(embed=embed, view=None)
        except Exception:
            await ix.response.defer()

        # DM creator
        try:
            uid = req.get("uid", "")
            user = await bot.fetch_user(int(uid))
            if approved:
                msg = (
                    f"✅ **คำขอสร้างของคุณได้รับการอนุมัติแล้ว!**\n"
                    f"**{req['name']}** ถูกเพิ่มให้คุณแล้ว 🎉"
                )
            else:
                msg = (
                    f"❌ **คำขอสร้างของคุณถูกปฏิเสธ**\n"
                    f"**{req['name']}**\n"
                    + (f"เหตุผล: {reason}" if reason else "")
                )
            await user.send(msg)
        except Exception:
            pass


async def _execute_creation(guild: discord.Guild, req: dict):
    """Actually create the item/skill when approved"""
    uid = req.get("uid", "")
    if not uid:
        return
    ensure_orion_player(uid)

    req_type = req.get("type")
    if req_type == "skill":
        data = load_orion_players()
        data[uid].setdefault("skills", []).append({
            "name": req.get("name", "?"),
            "context": req.get("context", ""),
            "emoji": req.get("emoji", "✨"),
            "icon_url": req.get("icon_url", ""),
            "origin_type": req.get("origin_type", "Artifact"),
        })
        save_orion_players(data)
    elif req_type == "item":
        from orion_items import load_items_catalog, save_items_catalog, add_player_item
        import re
        iid = re.sub(r"[^\w_]", "_", req.get("name", "item").lower().strip())[:30] + "_" + req["id"][:6]
        cat = load_items_catalog()
        cat[iid] = {
            "name": req.get("name", "?"),
            "emoji": req.get("emoji", "📦"),
            "description": req.get("description", ""),
            "sell_price": req.get("sell_price", 0),
            "image_url": req.get("image_url", ""),
            "type": "item",
            "stock": -1,
        }
        save_items_catalog(cat)
        add_player_item(uid, iid, 1)


class CreationDeclineModal(discord.ui.Modal, title="❌ เหตุผลที่ปฏิเสธ"):
    f_reason = discord.ui.TextInput(
        label="เหตุผล (ส่งให้ผู้สร้างดู)",
        style=discord.TextStyle.paragraph,
        required=False, max_length=500,
    )

    def __init__(self, req_id: str):
        super().__init__()
        self.req_id = req_id

    async def on_submit(self, ix: discord.Interaction):
        reqs = load_creation_requests()
        req = next((r for r in reqs if r["id"] == self.req_id), None)
        if not req:
            await ix.response.send_message("❌ ไม่พบคำขอ", ephemeral=True); return
        view = CreationReviewView(self.req_id)
        await view._resolve(ix, False, self.f_reason.value.strip())


# ── Creation Config Admin ─────────────────────────────────────
class CreationConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(CreatorRoleSelect())

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="ตั้ง Review Channel", style=discord.ButtonStyle.primary, row=2)
    async def set_channel(self, ix, _b):
        await ix.response.send_modal(ReviewChannelModal())


class CreatorRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="เลือก Role ที่ใช้ระบบสร้างได้ (Blacksmith, Creator...)...",
            min_values=0, max_values=10,
            row=0,
        )

    async def callback(self, ix: discord.Interaction):
        cfg = load_creation_cfg()
        cfg["creator_role_ids"] = [str(r.id) for r in self.values]
        save_creation_cfg(cfg)
        names = ", ".join(r.name for r in self.values) or "_(ล้างแล้ว)_"
        await ix.response.send_message(f"✅ Creator roles: {names}", ephemeral=True)


class ReviewChannelModal(discord.ui.Modal, title="ตั้ง Review Channel"):
    f_ch = discord.ui.TextInput(label="Channel ID", placeholder="1234567890", max_length=25)

    async def on_submit(self, ix: discord.Interaction):
        ch_id = self.f_ch.value.strip()
        if not ch_id.isdigit():
            await ix.response.send_message("❌ ต้องเป็น Channel ID (ตัวเลข)", ephemeral=True); return
        cfg = load_creation_cfg()
        cfg["review_channel_id"] = ch_id
        save_creation_cfg(cfg)
        await ix.response.send_message(f"✅ ตั้ง review channel เป็น <#{ch_id}>", ephemeral=True)


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="สร้าง", description="สร้าง Artifact Skill หรือไอเทม (เฉพาะ Creator role)", guild=_ORION_GUILD_OBJ)
async def cmd_create(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not _has_creator_role(interaction.user):
        await interaction.response.send_message(
            "❌ ต้องมี Creator/Blacksmith role — ติดต่อแอดมิน",
            ephemeral=True,
        ); return
    embed = make_menu_embed(
        "🔨 Creation System",
        [
            ("✨ Artifact Skill", "สร้างสกิลประเภท Artifact — ต้องรอแอดมิน approve"),
            ("🗡️ ไอเทม", "สร้างไอเทมใหม่ — ต้องรอแอดมิน approve"),
        ],
        color=0xe67e22,
    )
    await interaction.response.send_message(
        embed=embed,
        view=CreationTypeView(str(interaction.user.id)),
        ephemeral=True,
    )


@bot.tree.command(name="สร้างแอดมิน", description="[Admin] ตั้งค่าระบบ Creation", guild=_ORION_GUILD_OBJ)
async def cmd_creation_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cfg = load_creation_cfg()
    reqs = load_creation_requests()
    pending = sum(1 for r in reqs if r.get("status") == "pending")
    embed = make_menu_embed(
        "Creation Admin",
        [
            (f"คำขอค้าง: `{pending}`", "คำขอที่รอ review"),
            ("Creator Roles", "กำหนด role ที่ใช้ระบบสร้างได้"),
            ("Review Channel", f"<#{cfg['review_channel_id']}>" if cfg.get("review_channel_id") else "_ยังไม่ตั้ง_"),
        ],
        color=0xe67e22,
    )
    await interaction.response.send_message(embed=embed, view=CreationConfigView(), ephemeral=True)
