# ============================================================
# ORION AUCTION SYSTEM — /ลงประมูล /ประมูล /ปิดประมูล /ดูประมูล /ประมูลแอดมิน
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

AUCTIONS_FILE = f"{ORION_DATA_DIR}/auctions.json"


def load_auctions() -> list:
    return load_json(AUCTIONS_FILE, [])


def save_auctions(d: list):
    save_json(AUCTIONS_FILE, d)


def _auction_embed(a: dict) -> discord.Embed:
    status = a.get("status", "active")
    color = 0xf39c12 if status == "active" else 0x95a5a6
    embed = discord.Embed(
        title=f"🔨 {a.get('item_name', '?')}",
        description=a.get("description", "_ไม่มีคำอธิบาย_"),
        color=color,
    )
    embed.add_field(name="ราคาตั้งต้น", value=f"`{int(a.get('start_price', 0)):,}`", inline=True)
    embed.add_field(name="ราคาสูงสุดปัจจุบัน", value=f"`{int(a.get('current_bid', 0)):,}`", inline=True)
    top_bidder = a.get("top_bidder")
    embed.add_field(name="ผู้ประมูลสูงสุด", value=f"<@{top_bidder}>" if top_bidder else "_ยังไม่มี_", inline=True)
    seller = a.get("seller_id")
    embed.add_field(name="ผู้ขาย", value=f"<@{seller}>" if seller else "—", inline=True)
    end_ts = a.get("end_ts")
    if end_ts:
        end_str = f"<t:{int(end_ts)}:R>"
    else:
        end_str = "_ไม่มีกำหนด_"
    embed.add_field(name="สิ้นสุด", value=end_str, inline=True)
    embed.set_footer(text=f"ID: {a.get('id', '?')}  ·  สถานะ: {status}")
    return embed


class BidModal(discord.ui.Modal, title="💰 ใส่ราคาประมูล"):
    f_bid = discord.ui.TextInput(label="ราคาที่ต้องการประมูล", placeholder="เช่น 500", max_length=12)

    def __init__(self, aid: str, uid: str):
        super().__init__()
        self.aid = aid
        self.uid = uid

    async def on_submit(self, ix: discord.Interaction):
        bid = _parse_int(self.f_bid.value)
        if bid is None or bid <= 0:
            await ix.response.send_message("❌ ราคาต้องเป็นตัวเลขบวก", ephemeral=True); return
        auctions = load_auctions()
        a = next((x for x in auctions if x.get("id") == self.aid), None)
        if not a or a.get("status") != "active":
            await ix.response.send_message("❌ ไม่พบประมูลหรือปิดแล้ว", ephemeral=True); return
        if bid <= int(a.get("current_bid", 0)):
            await ix.response.send_message(
                f"❌ ต้องประมูลมากกว่า `{int(a['current_bid']):,}`",
                ephemeral=True,
            ); return
        if get_wallet(self.uid) < bid:
            await ix.response.send_message(
                f"❌ เงินไม่พอ — มี {money_str(get_wallet(self.uid))}",
                ephemeral=True,
            ); return
        # Refund previous top bidder
        prev = a.get("top_bidder")
        if prev and prev != self.uid:
            prev_bid = int(a.get("current_bid", 0))
            add_money(prev, prev_bid)
        add_money(self.uid, -bid)
        a["current_bid"] = bid
        a["top_bidder"] = self.uid
        save_auctions(auctions)
        await ix.response.send_message(
            f"✅ ประมูล `{bid:,}` สำเร็จ! คุณเป็นผู้ประมูลสูงสุดตอนนี้",
            ephemeral=True,
        )


class AuctionItemView(discord.ui.View):
    def __init__(self, aid: str, uid: str):
        super().__init__(timeout=300)
        self.aid = aid
        self.uid = uid

    @discord.ui.button(label="💰 ประมูล", style=discord.ButtonStyle.success)
    async def bid(self, ix, _b):
        await ix.response.send_modal(BidModal(self.aid, str(ix.user.id)))

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)


class AuctionListSelect(discord.ui.Select):
    def __init__(self, uid: str):
        self.uid = uid
        auctions = [a for a in load_auctions() if a.get("status") == "active"][:25]
        options = []
        for a in auctions:
            options.append(discord.SelectOption(
                label=a.get("item_name", "?")[:100],
                value=a.get("id", "?"),
                description=f"ราคาปัจจุบัน {int(a.get('current_bid', 0)):,}"[:80],
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มีประมูล", value="none")]
        super().__init__(placeholder="เลือกรายการประมูล...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        aid = self.values[0]
        auctions = load_auctions()
        a = next((x for x in auctions if x.get("id") == aid), None)
        if not a:
            await ix.response.send_message("❌ ไม่พบ", ephemeral=True); return
        await ix.response.send_message(
            embed=_auction_embed(a),
            view=AuctionItemView(aid, str(ix.user.id)),
            ephemeral=True,
        )


class AuctionView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=300)
        self.add_item(AuctionListSelect(uid))
        self.add_item(DoneBtn(row=1))


class CreateAuctionModal(discord.ui.Modal, title="🔨 ลงประมูลไอเทม"):
    f_name  = discord.ui.TextInput(label="ชื่อไอเทม", max_length=60)
    f_start = discord.ui.TextInput(label="ราคาตั้งต้น", placeholder="100", max_length=10)
    f_hours = discord.ui.TextInput(label="ระยะเวลา (ชั่วโมง)", placeholder="24", max_length=5)
    f_desc  = discord.ui.TextInput(label="คำอธิบาย", style=discord.TextStyle.paragraph, required=False, max_length=500)

    async def on_submit(self, ix: discord.Interaction):
        import uuid
        uid = str(ix.user.id)
        start = max(1, _parse_int(self.f_start.value, 100) or 100)
        hours = max(1, _parse_int(self.f_hours.value, 24) or 24)
        end_ts = int(time.time()) + hours * 3600
        a = {
            "id": uuid.uuid4().hex[:8],
            "seller_id": uid,
            "item_name": self.f_name.value.strip(),
            "description": (self.f_desc.value or "").strip(),
            "start_price": start,
            "current_bid": start,
            "top_bidder": None,
            "end_ts": end_ts,
            "status": "active",
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        }
        auctions = load_auctions()
        auctions.append(a)
        save_auctions(auctions)
        await ix.response.send_message(
            f"✅ ลงประมูล **{a['item_name']}** แล้ว\n"
            f"ราคาตั้งต้น: `{start:,}` · สิ้นสุด: <t:{end_ts}:R>",
            ephemeral=True,
        )


@bot.tree.command(name="ดูประมูล", description="ดูรายการประมูลทั้งหมด", guild=_ORION_GUILD_OBJ)
async def cmd_view_auctions(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    active = [a for a in load_auctions() if a.get("status") == "active"]
    embed = discord.Embed(
        title=f"🔨  ตลาดประมูล — {len(active)} รายการ",
        color=0xf39c12,
    )
    if not active:
        embed.description = "_ไม่มีรายการประมูล_"
    else:
        lines = [
            f"• **{a['item_name']}** — `{int(a.get('current_bid', 0)):,}` · <t:{int(a.get('end_ts', 0))}:R>"
            for a in active[:10]
        ]
        embed.description = "\n".join(lines)
    await interaction.response.send_message(
        embed=embed,
        view=AuctionView(uid),
        ephemeral=_eph("ดูประมูล"),
    )


@bot.tree.command(name="ลงประมูล", description="นำไอเทมมาประมูลในตลาด", guild=_ORION_GUILD_OBJ)
async def cmd_create_auction(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    await interaction.response.send_modal(CreateAuctionModal())


@bot.tree.command(name="ปิดประมูล", description="ปิดการประมูลของคุณก่อนเวลา", guild=_ORION_GUILD_OBJ)
async def cmd_close_auction(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    auctions = load_auctions()
    my = [a for a in auctions if a.get("seller_id") == uid and a.get("status") == "active"]
    if not my:
        await interaction.response.send_message("❌ คุณไม่มีประมูลที่เปิดอยู่", ephemeral=True); return

    options = [
        discord.SelectOption(label=a["item_name"][:100], value=a["id"])
        for a in my[:25]
    ]

    class CloseSelect(discord.ui.Select):
        def __init__(self):
            super().__init__(placeholder="เลือกประมูลที่จะปิด...", options=options)
        async def callback(self2, ix2):
            aid = self2.values[0]
            a = next((x for x in load_auctions() if x["id"] == aid), None)
            if not a:
                await ix2.response.send_message("❌ ไม่พบ", ephemeral=True); return
            if a.get("status") != "active":
                await ix2.response.send_message("❌ ปิดแล้ว", ephemeral=True); return
            # Settle
            top = a.get("top_bidder")
            if top:
                add_money(uid, int(a.get("current_bid", 0)))
            a["status"] = "closed"
            save_auctions(load_auctions())  # reload+save
            auctions2 = load_auctions()
            for x in auctions2:
                if x["id"] == aid:
                    x["status"] = "closed"
            save_auctions(auctions2)
            winner_text = f"ผู้ชนะ: <@{top}>" if top else "ไม่มีผู้ประมูล"
            await ix2.response.send_message(
                f"✅ ปิดประมูล **{a['item_name']}** แล้ว · {winner_text}",
                ephemeral=True,
            )

    v = discord.ui.View(timeout=120)
    v.add_item(CloseSelect())
    await interaction.response.send_message("เลือกประมูลที่จะปิด", view=v, ephemeral=True)


@bot.tree.command(name="ประมูลแอดมิน", description="[Admin] จัดการระบบประมูล", guild=_ORION_GUILD_OBJ)
async def cmd_auction_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    auctions = load_auctions()
    active = sum(1 for a in auctions if a.get("status") == "active")
    embed = discord.Embed(
        title=f"Auction Admin — {len(auctions)} รายการ ({active} active)",
        color=0xf39c12,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ประมูล", description="ดูรายการประมูลและใส่ราคา", guild=_ORION_GUILD_OBJ)
async def cmd_bid(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    active = [a for a in load_auctions() if a.get("status") == "active"]
    if not active:
        await interaction.response.send_message("❌ ไม่มีรายการประมูลตอนนี้", ephemeral=True); return
    await interaction.response.send_message(
        "เลือกรายการประมูล",
        view=AuctionView(uid),
        ephemeral=_eph("ดูประมูล"),
    )
