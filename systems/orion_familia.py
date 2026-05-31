# ============================================================
# ORION FAMILIA SYSTEM — /familia /familiaแอดมิน
# ============================================================
import discord
import time
import datetime

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    get_wallet, add_money, money_str, load_currency_cfg, _parse_int,
)
from discord.ext import tasks

FAMILIAS_FILE = f"{ORION_DATA_DIR}/familias.json"


def load_familias() -> dict:
    return load_json(FAMILIAS_FILE, {})


def save_familias(d: dict):
    save_json(FAMILIAS_FILE, d)


def get_player_familia(uid: str) -> tuple:
    """Return (familia_id, familia_data) or (None, None)"""
    fams = load_familias()
    for fid, f in fams.items():
        if any(m.get("uid") == uid for m in f.get("members", [])):
            return fid, f
    return None, None


def _familia_embed(fam: dict, fid: str) -> discord.Embed:
    members = fam.get("members", [])
    leader_id = fam.get("leader_id", "")
    embed = discord.Embed(
        title=f"👪  {fam.get('name', 'Familia')}",
        description=fam.get("description", "_ไม่มีคำอธิบาย_"),
        color=0xfd79a8,
    )
    embed.add_field(name="สมาชิก", value=f"`{len(members)}/{fam.get('max_members', 20)}`", inline=True)
    embed.add_field(name="หัวหน้า", value=f"<@{leader_id}>" if leader_id else "—", inline=True)
    embed.add_field(name="Familia ID", value=f"`{fid}`", inline=True)
    if fam.get("icon_url"):
        embed.set_thumbnail(url=fam["icon_url"])
    member_lines = []
    for m in members[:20]:
        mid = m.get("uid", "")
        rank = m.get("rank", "Member")
        member_lines.append(f"<@{mid}> · `{rank}`")
    if member_lines:
        embed.add_field(name="รายชื่อสมาชิก", value="\n".join(member_lines), inline=False)
    embed.set_footer(text=f"Orion · Familia · ก่อตั้ง {fam.get('created_at', '—')}")
    return embed


class FamiliaCreateModal(discord.ui.Modal, title="สร้าง Familia ใหม่"):
    f_name = discord.ui.TextInput(label="ชื่อ Familia", max_length=50)
    f_desc = discord.ui.TextInput(label="คำอธิบาย", style=discord.TextStyle.paragraph, required=False, max_length=300)
    f_icon = discord.ui.TextInput(label="URL รูป icon (ไม่บังคับ)", required=False, max_length=400)

    async def on_submit(self, ix: discord.Interaction):
        uid = str(ix.user.id)
        cfg = load_currency_cfg()
        cost = cfg.get("guild_create_cost", 100)
        fid_existing, _ = get_player_familia(uid)
        if fid_existing:
            await ix.response.send_message("❌ คุณอยู่ใน Familia อยู่แล้ว", ephemeral=True); return
        if get_wallet(uid) < cost:
            await ix.response.send_message(f"❌ เงินไม่พอ — ต้องการ {money_str(cost)}", ephemeral=True); return
        add_money(uid, -cost)
        import uuid
        fid = uuid.uuid4().hex[:8]
        fams = load_familias()
        fams[fid] = {
            "name": self.f_name.value.strip(),
            "description": (self.f_desc.value or "").strip(),
            "icon_url": (self.f_icon.value or "").strip(),
            "leader_id": uid,
            "members": [{"uid": uid, "rank": "Leader"}],
            "invites": [],
            "max_members": 20,
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            "income_rate": 0,
        }
        save_familias(fams)
        await ix.response.send_message(
            embed=_familia_embed(fams[fid], fid),
            ephemeral=True,
        )


class FamiliaInviteUserSelect(discord.ui.UserSelect):
    def __init__(self, fid: str):
        super().__init__(placeholder="เลือกสมาชิกที่จะเชิญ...", min_values=1, max_values=1)
        self.fid = fid

    async def callback(self, ix: discord.Interaction):
        target = self.values[0]
        if target.bot:
            await ix.response.send_message("❌ ไม่ใช่ผู้เล่น", ephemeral=True); return
        uid = str(target.id)
        fams = load_familias()
        fam = fams.get(self.fid)
        if not fam:
            await ix.response.send_message("❌ ไม่พบ Familia", ephemeral=True); return
        if any(m.get("uid") == uid for m in fam.get("members", [])):
            await ix.response.send_message("❌ เป็นสมาชิกอยู่แล้ว", ephemeral=True); return
        if uid in fam.get("invites", []):
            await ix.response.send_message("❌ เชิญไปแล้ว", ephemeral=True); return
        if len(fam.get("members", [])) >= fam.get("max_members", 20):
            await ix.response.send_message("❌ Familia เต็มแล้ว", ephemeral=True); return
        fam.setdefault("invites", []).append(uid)
        save_familias(fams)
        await ix.response.send_message(f"✅ เชิญ {target.mention} แล้ว", ephemeral=True)
        try:
            await target.send(
                f"📨 คุณได้รับเชิญเข้า Familia **{fam['name']}**\n"
                f"ใช้ `/familia` → กด **รับเชิญ** เพื่อเข้าร่วม"
            )
        except Exception:
            pass


class FamiliaPanelView(discord.ui.View):
    def __init__(self, uid: str, fid: str):
        super().__init__(timeout=300)
        self.uid = uid
        self.fid = fid
        fams = load_familias()
        fam = fams.get(fid, {})
        is_leader = fam.get("leader_id") == uid

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="เชิญสมาชิก", style=discord.ButtonStyle.primary, row=1)
    async def invite(self, ix, _b):
        fams = load_familias()
        fam = fams.get(self.fid, {})
        if fam.get("leader_id") != self.uid:
            await ix.response.send_message("❌ ต้องเป็น Leader", ephemeral=True); return
        v = discord.ui.View(timeout=120)
        v.add_item(FamiliaInviteUserSelect(self.fid))
        await ix.response.send_message("เลือกสมาชิกที่จะเชิญ", view=v, ephemeral=True)

    @discord.ui.button(label="ออกจาก Familia", style=discord.ButtonStyle.danger, row=2)
    async def leave(self, ix, _b):
        fams = load_familias()
        fam = fams.get(self.fid, {})
        if not fam:
            await ix.response.send_message("❌ ไม่พบ Familia", ephemeral=True); return
        if fam.get("leader_id") == self.uid:
            await ix.response.send_message("❌ Leader ออกไม่ได้ — ต้องยุบ Familia ก่อน", ephemeral=True); return
        fam["members"] = [m for m in fam.get("members", []) if m.get("uid") != self.uid]
        save_familias(fams)
        await ix.response.edit_message(content="✅ ออกจาก Familia แล้ว", embed=None, view=None)


# ── Passive income loop ────────────────────────────────────────
@tasks.loop(hours=1)
async def familia_passive_loop():
    try:
        fams = load_familias()
        for fid, fam in fams.items():
            rate = int(fam.get("income_rate", 0))
            if rate <= 0:
                continue
            for m in fam.get("members", []):
                uid = m.get("uid", "")
                if uid:
                    add_money(uid, rate)
    except Exception as e:
        print(f"[Familia] passive loop error: {e}")


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="familia", description="ดูข้อมูล Familia ของคุณ", guild=_ORION_GUILD_OBJ)
async def cmd_familia(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    fid, fam = get_player_familia(uid)

    if not fid:
        # ดูคำเชิญ
        fams = load_familias()
        invites = [(fid2, f) for fid2, f in fams.items() if uid in f.get("invites", [])]
        if invites:
            lines = [f"• **{f['name']}** (`{fid2}`)" for fid2, f in invites[:5]]
            embed = discord.Embed(
                title="📨 คำเชิญ Familia",
                description="คุณได้รับเชิญเข้า:\n" + "\n".join(lines),
                color=0xfd79a8,
            )
            class InviteView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=120)
                @discord.ui.button(label="รับเชิญ (อันแรก)", style=discord.ButtonStyle.success)
                async def accept(self2, ix2, _b):
                    fam2 = invites[0][1]; fid3 = invites[0][0]
                    fam2["members"].append({"uid": uid, "rank": "Member"})
                    fam2["invites"] = [u for u in fam2.get("invites", []) if u != uid]
                    fams2 = load_familias(); fams2[fid3] = fam2; save_familias(fams2)
                    await ix2.response.edit_message(content=f"✅ เข้าร่วม **{fam2['name']}** แล้ว", embed=None, view=None)
                @discord.ui.button(label="ปฏิเสธ", style=discord.ButtonStyle.secondary)
                async def decline(self2, ix2, _b):
                    fam2 = invites[0][1]; fid3 = invites[0][0]
                    fam2["invites"] = [u for u in fam2.get("invites", []) if u != uid]
                    fams2 = load_familias(); fams2[fid3] = fam2; save_familias(fams2)
                    await ix2.response.edit_message(content="❌ ปฏิเสธคำเชิญแล้ว", embed=None, view=None)
            await interaction.response.send_message(embed=embed, view=InviteView(), ephemeral=_eph("familia"))
            return

        # ไม่มี familia และไม่มีคำเชิญ
        cfg = load_currency_cfg()
        cost = cfg.get("guild_create_cost", 100)
        embed = make_menu_embed(
            "Familia",
            [("สร้าง Familia", f"ค่าใช้จ่าย {money_str(cost)}  |  สมาชิกสูงสุด 20 คน")],
            color=0xfd79a8,
        )
        class CreateView(discord.ui.View):
            @discord.ui.button(label="สร้าง Familia", style=discord.ButtonStyle.success)
            async def create(self, ix2, _b):
                await ix2.response.send_modal(FamiliaCreateModal())
        await interaction.response.send_message(embed=embed, view=CreateView(), ephemeral=_eph("familia"))
        return

    await interaction.response.send_message(
        embed=_familia_embed(fam, fid),
        view=FamiliaPanelView(uid, fid),
        ephemeral=_eph("familia"),
    )


@bot.tree.command(name="familiaแอดมิน", description="[Admin] จัดการ Familia ทั้งหมด", guild=_ORION_GUILD_OBJ)
async def cmd_familia_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    fams = load_familias()
    lines = [f"• **{f.get('name','?')}** (`{fid}`) · {len(f.get('members',[]))} คน"
             for fid, f in list(fams.items())[:15]]
    embed = discord.Embed(
        title=f"Familia Admin — {len(fams)} กลุ่ม",
        description="\n".join(lines) or "_ไม่มี Familia_",
        color=0xfd79a8,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
