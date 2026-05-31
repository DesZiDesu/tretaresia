# ============================================================
# ORION ITEMS SYSTEM — /ไอเทม /คลังไอเทม /ไอเทมแอดมิน
# ============================================================
import discord
import json
import os
import re

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    _parse_int,
)

ITEMS_FILE = f"{ORION_DATA_DIR}/items_catalog.json"

DEFAULT_ITEMS = {}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:40] or "item"


def load_items_catalog() -> dict:
    return load_json(ITEMS_FILE, dict(DEFAULT_ITEMS))


def save_items_catalog(cat: dict):
    save_json(ITEMS_FILE, cat)


def get_item(item_id: str) -> dict | None:
    return load_items_catalog().get(item_id)


def add_player_item(uid: str, item_id: str, qty: int = 1) -> bool:
    ensure_orion_player(uid)
    cat = load_items_catalog()
    if item_id not in cat:
        return False
    data = load_orion_players()
    inv = data[uid].setdefault("inv", [])
    slot = next((s for s in inv if s.get("id") == item_id), None)
    if slot:
        slot["qty"] = int(slot.get("qty", 0)) + qty
    else:
        inv.append({"id": item_id, "qty": qty})
    save_orion_players(data)
    return True


def remove_player_item(uid: str, item_id: str, qty: int = 1) -> bool:
    data = load_orion_players()
    inv = data.get(uid, {}).get("inv", [])
    slot = next((s for s in inv if s.get("id") == item_id), None)
    if not slot or int(slot.get("qty", 0)) < qty:
        return False
    slot["qty"] = int(slot["qty"]) - qty
    if slot["qty"] <= 0:
        inv.remove(slot)
    save_orion_players(data)
    return True


def player_has_items(uid: str, requirements: list) -> bool:
    data = load_orion_players()
    inv = data.get(uid, {}).get("inv", [])
    for req in requirements:
        item_id = req.get("id")
        qty_needed = int(req.get("qty", 1))
        slot = next((s for s in inv if s.get("id") == item_id), None)
        if not slot or int(slot.get("qty", 0)) < qty_needed:
            return False
    return True


def _build_item_embed(item_id: str, item: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"{item.get('emoji', '📦')}  {item.get('name', item_id)}",
        description=item.get("description", "_ไม่มีคำอธิบาย_"),
        color=0x55efc4,
    )
    if item.get("image_url"):
        embed.set_thumbnail(url=item["image_url"])
    embed.add_field(name="ID", value=f"`{item_id}`", inline=True)
    embed.add_field(name="ราคาขาย", value=f"`{int(item.get('sell_price', 0)):,}`", inline=True)
    itype = item.get("type", "resource")
    embed.add_field(name="ประเภท", value=f"`{itype}`", inline=True)
    stock = item.get("stock", -1)
    embed.add_field(name="Stock", value="`ไม่จำกัด`" if stock < 0 else f"`{stock}`", inline=True)
    embed.set_footer(text=f"Orion · Item Catalog · {item_id}")
    return embed


def _items_overview_embed(page: int = 0, per_page: int = 10) -> discord.Embed:
    cat = load_items_catalog()
    items = sorted(cat.items(), key=lambda x: x[1].get("name", x[0]).lower())
    total = len(items)
    start = page * per_page
    end = min(start + per_page, total)
    page_items = items[start:end]
    max_page = max(0, (total - 1) // per_page) if total else 0

    embed = discord.Embed(
        title=f"📦  คลังไอเทมทั้งหมด — {total} ชนิด",
        color=0x55efc4,
    )
    if not page_items:
        embed.description = "_ยังไม่มีไอเทมในคลัง — แอดมินสร้างได้ผ่าน `/ไอเทมแอดมิน`_"
    else:
        lines = []
        for iid, it in page_items:
            lines.append(
                f"{_safe_emoji(it.get('emoji'), '📦')} **{it.get('name', iid)}**"
                f" · `{iid}` · ราคา `{int(it.get('sell_price', 0)):,}`"
            )
        embed.description = "\n".join(lines)
    embed.set_footer(text=f"หน้า {page+1}/{max_page+1}  ·  Orion Item Catalog")
    return embed


def _player_bag_embed(uid: str, member) -> discord.Embed:
    data = load_orion_players()
    inv = data.get(uid, {}).get("inv", [])
    cat = load_items_catalog()
    embed = discord.Embed(
        title=f"🎒  กระเป๋าของ {member.display_name} — {len(inv)} ชนิด",
        color=0x00cec9,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if not inv:
        embed.description = "_กระเป๋าว่าง_"
    else:
        lines = []
        for slot in inv[:25]:
            iid = slot.get("id", "?")
            qty = int(slot.get("qty", 1))
            it = cat.get(iid, {})
            name = it.get("name", iid)
            emoji = _safe_emoji(it.get("emoji"), "📦")
            lines.append(f"{emoji} **{name}** ×{qty}")
        embed.description = "\n".join(lines)
    embed.set_footer(text="Orion · Item Bag")
    return embed


# ── Catalog Item Select ───────────────────────────────────────
class ItemCatalogSelect(discord.ui.Select):
    def __init__(self, page: int = 0):
        self.page = page
        per_page = 25
        cat = load_items_catalog()
        items = sorted(cat.items(), key=lambda x: x[1].get("name", x[0]).lower())
        start = page * per_page
        page_items = items[start:start + per_page]
        options = []
        for iid, it in page_items:
            options.append(discord.SelectOption(
                label=it.get("name", iid)[:100],
                value=iid,
                description=f"{iid} · ราคา {int(it.get('sell_price', 0)):,}"[:80],
                emoji=_safe_emoji(it.get("emoji")),
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มีไอเทม", value="none")]
        super().__init__(placeholder="เลือกไอเทมเพื่อดูรายละเอียด...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        iid = self.values[0]
        cat = load_items_catalog()
        it = cat.get(iid)
        if not it:
            await ix.response.send_message("❌ ไม่พบไอเทม", ephemeral=True); return
        await ix.response.edit_message(
            embed=_build_item_embed(iid, it),
            view=ItemCatalogView(page=self.page),
        )


class ItemCatalogView(discord.ui.View):
    def __init__(self, page: int = 0):
        super().__init__(timeout=300)
        self.page = page
        cat = load_items_catalog()
        per_page = 25
        max_page = max(0, (len(cat) - 1) // per_page) if cat else 0
        self.add_item(ItemCatalogSelect(page=page))
        if page > 0:
            self.add_item(_NavBtn(self, -1, "← ก่อนหน้า", row=1))
        if page < max_page:
            self.add_item(_NavBtn(self, 1, "ถัดไป →", row=1))
        self.add_item(DoneBtn(row=1))


class _NavBtn(discord.ui.Button):
    def __init__(self, parent, delta, label, row=1):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.parent = parent
        self.delta = delta

    async def callback(self, ix):
        new_view = ItemCatalogView(page=self.parent.page + self.delta)
        await ix.response.edit_message(
            embed=_items_overview_embed(page=self.parent.page + self.delta),
            view=new_view,
        )


class PlayerBagSelect(discord.ui.Select):
    def __init__(self, uid: str, member):
        self.uid = uid
        self.member = member
        data = load_orion_players()
        inv = data.get(uid, {}).get("inv", [])[:25]
        cat = load_items_catalog()
        options = []
        for slot in inv:
            iid = slot.get("id", "?")
            qty = int(slot.get("qty", 1))
            it = cat.get(iid, {})
            name = it.get("name", iid)
            options.append(discord.SelectOption(
                label=f"{name} ×{qty}"[:100],
                value=iid,
                description=(it.get("description", "")[:80] or "—"),
                emoji=_safe_emoji(it.get("emoji")),
            ))
        if not options:
            options = [discord.SelectOption(label="กระเป๋าว่าง", value="none")]
        super().__init__(placeholder="🎒 เลือกไอเทมเพื่อดูรายละเอียด...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        iid = self.values[0]
        cat = load_items_catalog()
        it = cat.get(iid, {})
        await ix.response.edit_message(
            embed=_build_item_embed(iid, it) if it else discord.Embed(title=f"📦 {iid}", description="_ไม่พบข้อมูลในคลัง_", color=0x55efc4),
            view=PlayerBagView(self.uid, self.member),
        )


class PlayerBagView(discord.ui.View):
    def __init__(self, uid: str, member):
        super().__init__(timeout=300)
        self.uid = uid
        self.member = member
        self.add_item(PlayerBagSelect(uid, member))
        self.add_item(DoneBtn(row=1))

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่กระเป๋าของคุณ", ephemeral=True)
            return False
        return True


# ── Admin Modals ──────────────────────────────────────────────
class ItemAddModal(discord.ui.Modal, title="➕ เพิ่มไอเทมในคลัง"):
    f_id    = discord.ui.TextInput(label="ID (a-z, _, 0-9)", max_length=40)
    f_name  = discord.ui.TextInput(label="ชื่อไอเทม", max_length=60)
    f_emoji = discord.ui.TextInput(label="Emoji", placeholder="⚔️ 🛡️ 💎", required=False, max_length=10)
    f_price = discord.ui.TextInput(label="ราคาขาย (0 = ไม่มีราคา)", placeholder="0", max_length=10)
    f_desc  = discord.ui.TextInput(label="คำอธิบาย", style=discord.TextStyle.paragraph, max_length=600)

    async def on_submit(self, ix: discord.Interaction):
        iid = _slugify(self.f_id.value)
        if not iid:
            await ix.response.send_message("❌ ID ว่าง", ephemeral=True); return
        cat = load_items_catalog()
        if iid in cat:
            await ix.response.send_message(f"❌ มี ID `{iid}` อยู่แล้ว", ephemeral=True); return
        price = max(0, _parse_int(self.f_price.value, 0) or 0)
        cat[iid] = {
            "name": self.f_name.value.strip(),
            "emoji": (self.f_emoji.value or "📦").strip() or "📦",
            "description": self.f_desc.value.strip(),
            "sell_price": price,
            "type": "item",
            "stock": -1,
            "image_url": "",
        }
        save_items_catalog(cat)
        await ix.response.send_message(f"✅ เพิ่ม `{iid}` — **{cat[iid]['name']}** เรียบร้อย", ephemeral=True)


class ItemEditSelect(discord.ui.Select):
    def __init__(self):
        cat = load_items_catalog()
        items = sorted(cat.items(), key=lambda x: x[1].get("name", x[0]).lower())[:25]
        options = [
            discord.SelectOption(
                label=it.get("name", iid)[:100],
                value=iid,
                description=f"{iid}"[:80],
                emoji=_safe_emoji(it.get("emoji")),
            )
            for iid, it in items
        ]
        if not options:
            options = [discord.SelectOption(label="ไม่มีไอเทม", value="none")]
        super().__init__(placeholder="เลือกไอเทมที่จะแก้...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        iid = self.values[0]
        cat = load_items_catalog()
        it = cat.get(iid, {})
        modal = ItemEditModal(iid)
        modal.f_name.default = it.get("name", "")
        modal.f_emoji.default = it.get("emoji", "")
        modal.f_price.default = str(it.get("sell_price", 0))
        modal.f_desc.default = it.get("description", "")[:1500]
        await ix.response.send_modal(modal)


class ItemEditModal(discord.ui.Modal, title="✏️ แก้ไขไอเทม"):
    f_name  = discord.ui.TextInput(label="ชื่อ (ว่าง=ไม่เปลี่ยน)", required=False, max_length=60)
    f_emoji = discord.ui.TextInput(label="Emoji (ว่าง=ไม่เปลี่ยน)", required=False, max_length=10)
    f_price = discord.ui.TextInput(label="ราคาขาย", placeholder="0", max_length=10)
    f_desc  = discord.ui.TextInput(label="คำอธิบาย (ว่าง=ไม่เปลี่ยน)", style=discord.TextStyle.paragraph, required=False, max_length=600)

    def __init__(self, iid: str):
        super().__init__()
        self.iid = iid

    async def on_submit(self, ix: discord.Interaction):
        cat = load_items_catalog()
        it = cat.get(self.iid)
        if not it:
            await ix.response.send_message("❌ ไม่พบไอเทม", ephemeral=True); return
        if self.f_name.value.strip():    it["name"] = self.f_name.value.strip()
        if self.f_emoji.value.strip():   it["emoji"] = self.f_emoji.value.strip()
        if self.f_price.value.strip():   it["sell_price"] = max(0, _parse_int(self.f_price.value, 0) or 0)
        if self.f_desc.value.strip():    it["description"] = self.f_desc.value.strip()
        save_items_catalog(cat)
        await ix.response.send_message(f"✅ อัปเดต `{self.iid}` แล้ว", ephemeral=True)


class ItemDeleteSelect(discord.ui.Select):
    def __init__(self):
        cat = load_items_catalog()
        items = sorted(cat.items(), key=lambda x: x[1].get("name", x[0]).lower())[:25]
        options = [
            discord.SelectOption(label=it.get("name", iid)[:100], value=iid)
            for iid, it in items
        ] or [discord.SelectOption(label="ไม่มีไอเทม", value="none")]
        super().__init__(placeholder="เลือกไอเทมที่จะลบ...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        iid = self.values[0]
        cat = load_items_catalog()
        name = cat.pop(iid, {}).get("name", iid)
        save_items_catalog(cat)
        await ix.response.edit_message(content=f"🗑️ ลบ `{iid}` — **{name}** แล้ว", view=None)


class ItemAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="เพิ่มไอเทม", style=discord.ButtonStyle.success, row=1)
    async def add(self, ix, _b):
        await ix.response.send_modal(ItemAddModal())

    @discord.ui.button(label="แก้ไขไอเทม", style=discord.ButtonStyle.primary, row=2)
    async def edit(self, ix, _b):
        v = discord.ui.View(timeout=180); v.add_item(ItemEditSelect())
        await ix.response.send_message("เลือกไอเทมที่จะแก้", view=v, ephemeral=True)

    @discord.ui.button(label="ลบไอเทม", style=discord.ButtonStyle.danger, row=3)
    async def delete(self, ix, _b):
        v = discord.ui.View(timeout=180); v.add_item(ItemDeleteSelect())
        await ix.response.send_message("เลือกไอเทมที่จะลบ", view=v, ephemeral=True)

    @discord.ui.button(label="ดาวน์โหลด JSON", style=discord.ButtonStyle.secondary, row=4)
    async def download(self, ix, _b):
        cat = load_items_catalog()
        data = json.dumps(cat, ensure_ascii=False, indent=2)
        f = discord.File(
            fp=__import__("io").BytesIO(data.encode()),
            filename="items_catalog.json",
        )
        await ix.response.send_message("📥 Items catalog JSON", file=f, ephemeral=True)


# ── Slash Commands ────────────────────────────────────────────
@bot.tree.command(name="ไอเทม", description="ดูกระเป๋าไอเทมของตัวเอง", guild=_ORION_GUILD_OBJ)
async def cmd_my_bag(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    await interaction.response.send_message(
        embed=_player_bag_embed(uid, interaction.user),
        view=PlayerBagView(uid, interaction.user),
        ephemeral=_eph("ไอเทม"),
    )


@bot.tree.command(name="คลังไอเทม", description="ดูไอเทมทั้งหมดในเซิร์ฟ", guild=_ORION_GUILD_OBJ)
async def cmd_catalog(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    await interaction.response.send_message(
        embed=_items_overview_embed(),
        view=ItemCatalogView(),
        ephemeral=_eph("คลังไอเทม"),
    )


@bot.tree.command(name="เช็คของ", description="ดูกระเป๋าของผู้เล่นคนอื่น", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(target="ผู้เล่นที่จะดู")
async def cmd_check_bag(interaction: discord.Interaction, target: discord.Member = None):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    target = target or interaction.user
    if target.bot:
        await interaction.response.send_message("❌ บอทไม่มีกระเป๋า", ephemeral=True); return
    uid = str(target.id)
    ensure_orion_player(uid)
    await interaction.response.send_message(
        embed=_player_bag_embed(uid, target),
        view=PlayerBagView(uid, target),
        ephemeral=_eph("เช็คของ"),
    )


@bot.tree.command(name="โอนของ", description="โอนไอเทมให้ผู้เล่นคนอื่น", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(target="ผู้รับไอเทม")
async def cmd_transfer_item(interaction: discord.Interaction, target: discord.Member):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if target.bot or target.id == interaction.user.id:
        await interaction.response.send_message("❌ ไม่สามารถโอนให้ตัวเองหรือบอทได้", ephemeral=True); return
    uid = str(interaction.user.id)
    data = load_orion_players()
    inv = data.get(uid, {}).get("inv", [])
    cat = load_items_catalog()

    from orion_bot import load_skill_cats

    # Build transferable check from skill categories config
    skill_cats = load_skill_cats()
    transferable_cats = {c["id"] for c in skill_cats if c.get("transferable", False)}

    if not inv:
        await interaction.response.send_message("❌ กระเป๋าของคุณว่าง", ephemeral=True); return

    options = []
    for slot in inv[:25]:
        iid = slot.get("id", "?")
        qty = int(slot.get("qty", 1))
        it = cat.get(iid, {})
        # Check if item type is transferable
        item_type = it.get("type", "item")
        if item_type == "artifact_skill" and "artifact" not in transferable_cats:
            continue
        options.append(discord.SelectOption(
            label=f"{it.get('name', iid)} ×{qty}"[:100],
            value=iid,
            emoji=_safe_emoji(it.get("emoji")),
        ))

    if not options:
        await interaction.response.send_message("❌ ไม่มีไอเทมที่โอนได้", ephemeral=True); return

    class TransferSelect(discord.ui.Select):
        def __init__(self):
            super().__init__(placeholder="เลือกไอเทมที่จะโอน...", options=options)

        async def callback(self_, ix2):
            iid = self_.values[0]
            class QtyModal(discord.ui.Modal, title="จำนวนที่จะโอน"):
                f_qty = discord.ui.TextInput(label="จำนวน", placeholder="1", max_length=5)
                async def on_submit(m_self, ix3):
                    qty = max(1, _parse_int(m_self.f_qty.value, 1) or 1)
                    if not remove_player_item(uid, iid, qty):
                        await ix3.response.send_message("❌ ไม่มีไอเทมพอ", ephemeral=True); return
                    add_player_item(str(target.id), iid, qty)
                    it = cat.get(iid, {})
                    await ix3.response.send_message(
                        f"✅ โอน **{it.get('name', iid)}** ×{qty} ให้ {target.mention} แล้ว",
                        ephemeral=False,
                    )
            await ix2.response.send_modal(QtyModal())

    v = discord.ui.View(timeout=120)
    v.add_item(TransferSelect())
    await interaction.response.send_message(
        f"เลือกไอเทมที่จะโอนให้ **{target.display_name}**",
        view=v, ephemeral=True,
    )


@bot.tree.command(name="ไอเทมแอดมิน", description="[Admin] จัดการไอเทมในคลัง", guild=_ORION_GUILD_OBJ)
async def cmd_items_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cat = load_items_catalog()
    embed = make_menu_embed(
        f"Item Admin — {len(cat)} ไอเทมในคลัง",
        [
            ("เพิ่มไอเทม", "สร้างไอเทมใหม่ในคลัง"),
            ("แก้ไขไอเทม", "แก้ไขข้อมูลไอเทมที่มีอยู่"),
            ("ลบไอเทม", "ลบไอเทมออกจากคลัง"),
            ("ดาวน์โหลด JSON", "ดาวน์โหลดไฟล์ catalog ทั้งหมด"),
        ],
        color=0x55efc4,
    )
    await interaction.response.send_message(embed=embed, view=ItemAdminView(), ephemeral=True)
