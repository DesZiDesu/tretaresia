# ============================================================
# ORION SHOP SYSTEM — /ร้าน /ร้านแอดมิน /ร้านอัปโหลด /คูปอง
# ============================================================
import discord
import json
import io
import time

import orion_bot as _bot_module
bot = _bot_module.bot

from orion_bot import (
    load_json, save_json,
    ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    get_wallet, add_money, money_str, load_currency_cfg, _parse_int,
)

SHOP_FILE    = f"{ORION_DATA_DIR}/shop.json"
COUPONS_FILE = f"{ORION_DATA_DIR}/coupons.json"

DEFAULT_SHOP = {"name": "Orion Shop", "description": "", "items": {}}


def load_shop() -> dict:
    s = load_json(SHOP_FILE, dict(DEFAULT_SHOP))
    if "items" not in s:
        s["items"] = {}
    return s


def save_shop(s: dict):
    save_json(SHOP_FILE, s)


def load_coupons() -> dict:
    return load_json(COUPONS_FILE, {})


def save_coupons(d: dict):
    save_json(COUPONS_FILE, d)


def _shop_embed(shop: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏪  {shop.get('name', 'Shop')}",
        description=shop.get("description", "_ยินดีต้อนรับ_"),
        color=0x00b894,
    )
    items = shop.get("items", {})
    if not items:
        embed.add_field(name="สินค้า", value="_ยังไม่มีสินค้า_", inline=False)
    else:
        for iid, it in list(items.items())[:20]:
            stock = it.get("stock", -1)
            stock_str = "∞" if stock < 0 else str(stock)
            role_req = it.get("role_required", "")
            role_text = f" · ต้องมี role <@&{role_req}>" if role_req else ""
            embed.add_field(
                name=f"{_safe_emoji(it.get('emoji'), '🛍️')} {it.get('name', iid)}",
                value=f"{money_str(int(it.get('price', 0)))}  ·  Stock: `{stock_str}`{role_text}",
                inline=True,
            )
    embed.set_footer(text="เลือกสินค้าจาก dropdown ด้านล่างเพื่อซื้อ  ·  Orion Shop")
    return embed


class ShopItemSelect(discord.ui.Select):
    def __init__(self):
        shop = load_shop()
        items = list(shop.get("items", {}).items())[:25]
        options = []
        for iid, it in items:
            stock = it.get("stock", -1)
            stock_str = "∞" if stock < 0 else str(stock)
            options.append(discord.SelectOption(
                label=f"{it.get('name', iid)}"[:100],
                value=iid,
                description=f"{int(it.get('price', 0)):,} · Stock: {stock_str}"[:80],
                emoji=_safe_emoji(it.get("emoji")),
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มีสินค้า", value="none")]
        super().__init__(placeholder="🛍️ เลือกสินค้าที่ต้องการซื้อ...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        iid = self.values[0]
        shop = load_shop()
        it = shop.get("items", {}).get(iid)
        if not it:
            await ix.response.send_message("❌ ไม่พบสินค้า", ephemeral=True); return

        uid = str(ix.user.id)
        price = int(it.get("price", 0))

        # Role check
        role_req = it.get("role_required", "")
        if role_req and not any(str(r.id) == str(role_req) for r in ix.user.roles):
            await ix.response.send_message(
                f"❌ ต้องมี role <@&{role_req}> เพื่อซื้อสินค้านี้",
                ephemeral=True,
            ); return

        # Stock check
        stock = it.get("stock", -1)
        if stock == 0:
            await ix.response.send_message("❌ สินค้าหมดแล้ว", ephemeral=True); return

        if get_wallet(uid) < price:
            await ix.response.send_message(
                f"❌ เงินไม่พอ — มี {money_str(get_wallet(uid))} ต้องการ {money_str(price)}",
                ephemeral=True,
            ); return

        # Confirm embed
        embed = discord.Embed(
            title=f"🛍️ ยืนยันการซื้อ — {it.get('name', iid)}",
            description=(
                f"ราคา: {money_str(price)}\n"
                f"{it.get('description', '_ไม่มีคำอธิบาย_')}"
            ),
            color=0x00b894,
        )
        if it.get("image_url"):
            embed.set_thumbnail(url=it["image_url"])

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
            @discord.ui.button(label="✅ ซื้อ", style=discord.ButtonStyle.success)
            async def yes(self2, ix2, _b):
                shop2 = load_shop()
                it2 = shop2.get("items", {}).get(iid)
                if not it2:
                    await ix2.response.send_message("❌ สินค้าหาย", ephemeral=True); return
                if get_wallet(uid) < price:
                    await ix2.response.send_message("❌ เงินไม่พอ", ephemeral=True); return
                stock2 = it2.get("stock", -1)
                if stock2 == 0:
                    await ix2.response.send_message("❌ หมดแล้ว", ephemeral=True); return
                add_money(uid, -price)
                if stock2 > 0:
                    it2["stock"] = stock2 - 1
                    save_shop(shop2)
                # Add to player bag
                from orion_items import add_player_item, load_items_catalog, save_items_catalog
                cat = load_items_catalog()
                if iid not in cat:
                    cat[iid] = {
                        "name": it2.get("name", iid),
                        "emoji": it2.get("emoji", "🛍️"),
                        "description": it2.get("description", ""),
                        "sell_price": 0,
                        "type": "shop_item",
                        "stock": -1,
                    }
                    save_items_catalog(cat)
                add_player_item(uid, iid, 1)
                await ix2.response.edit_message(
                    content=f"✅ ซื้อ **{it2.get('name', iid)}** สำเร็จ!",
                    embed=None, view=None,
                )
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def no(self2, ix2, _b):
                await ix2.response.edit_message(content="❌ ยกเลิก", embed=None, view=None)

        await ix.response.send_message(embed=embed, view=ConfirmView(), ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ShopItemSelect())
        self.add_item(DoneBtn(row=1))


# ── Admin: Shop Item CRUD ─────────────────────────────────────
class ShopAddItemModal(discord.ui.Modal, title="➕ เพิ่มสินค้าในร้าน"):
    f_id    = discord.ui.TextInput(label="ID สินค้า (a-z, _, 0-9)", max_length=40)
    f_name  = discord.ui.TextInput(label="ชื่อสินค้า", max_length=60)
    f_price = discord.ui.TextInput(label="ราคา", placeholder="100", max_length=10)
    f_stock = discord.ui.TextInput(label="Stock (-1 = ไม่จำกัด)", placeholder="-1", max_length=10)
    f_desc  = discord.ui.TextInput(label="คำอธิบาย", style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, ix: discord.Interaction):
        iid = self.f_id.value.strip().lower().replace(" ", "_")
        if not iid:
            await ix.response.send_message("❌ ID ว่าง", ephemeral=True); return
        shop = load_shop()
        if iid in shop.get("items", {}):
            await ix.response.send_message(f"❌ มี `{iid}` อยู่แล้ว", ephemeral=True); return
        shop.setdefault("items", {})[iid] = {
            "name": self.f_name.value.strip(),
            "price": max(0, _parse_int(self.f_price.value, 100) or 100),
            "stock": _parse_int(self.f_stock.value, -1) if self.f_stock.value.strip() else -1,
            "description": self.f_desc.value.strip(),
            "emoji": "🛍️",
            "role_required": "",
            "image_url": "",
        }
        save_shop(shop)
        await ix.response.send_message(f"✅ เพิ่ม `{iid}` — {self.f_name.value} แล้ว", ephemeral=True)


class ShopNameModal(discord.ui.Modal, title="ตั้งชื่อร้านค้า"):
    f_name = discord.ui.TextInput(label="ชื่อร้าน", max_length=60)
    f_desc = discord.ui.TextInput(label="คำอธิบาย (ไม่บังคับ)", required=False, max_length=200)

    async def on_submit(self, ix: discord.Interaction):
        shop = load_shop()
        shop["name"] = self.f_name.value.strip()
        shop["description"] = (self.f_desc.value or "").strip()
        save_shop(shop)
        await ix.response.send_message(f"✅ ชื่อร้าน: **{shop['name']}**", ephemeral=True)


class ShopAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)

    @discord.ui.button(label="ตั้งชื่อร้าน", style=discord.ButtonStyle.primary, row=1)
    async def shop_name(self, ix, _b):
        await ix.response.send_modal(ShopNameModal())

    @discord.ui.button(label="เพิ่มสินค้า", style=discord.ButtonStyle.success, row=2)
    async def add_item(self, ix, _b):
        await ix.response.send_modal(ShopAddItemModal())

    @discord.ui.button(label="ดาวน์โหลด JSON Template", style=discord.ButtonStyle.secondary, row=3)
    async def download_template(self, ix, _b):
        shop = load_shop()
        data = json.dumps(shop, ensure_ascii=False, indent=2)
        f = discord.File(fp=io.BytesIO(data.encode()), filename="shop_export.json")
        await ix.response.send_message(
            "📥 Shop JSON — แก้ไขแล้วอัปโหลดผ่าน `/ร้านอัปโหลด`",
            file=f, ephemeral=True,
        )

    @discord.ui.button(label="รีเซ็ตร้าน", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, ix, _b):
        class Confirm(discord.ui.View):
            @discord.ui.button(label="ยืนยันรีเซ็ต", style=discord.ButtonStyle.danger)
            async def yes(self2, ix2, _b2):
                save_shop(dict(DEFAULT_SHOP))
                await ix2.response.edit_message(content="🗑️ รีเซ็ตร้านแล้ว", embed=None, view=None)
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def no(self2, ix2, _b2):
                await ix2.response.edit_message(content="❌ ยกเลิก", embed=None, view=None)
        await ix.response.send_message("⚠️ ยืนยันรีเซ็ตร้านทั้งหมด?", view=Confirm(), ephemeral=True)


# ── Coupon System ─────────────────────────────────────────────
class CouponView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=120)
        self.uid = uid

    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return False
        return True

    @discord.ui.button(label="ใช้คูปอง", style=discord.ButtonStyle.primary)
    async def use_coupon(self, ix, _b):
        await ix.response.send_modal(CouponRedeemModal(self.uid))

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)


class CouponRedeemModal(discord.ui.Modal, title="ใช้คูปอง"):
    f_code = discord.ui.TextInput(label="รหัสคูปอง", max_length=40)

    def __init__(self, uid: str):
        super().__init__()
        self.uid = uid

    async def on_submit(self, ix: discord.Interaction):
        code = self.f_code.value.strip().upper()
        coupons = load_coupons()
        if code not in coupons:
            await ix.response.send_message("❌ ไม่พบรหัสคูปอง", ephemeral=True); return
        coup = coupons[code]
        if coup.get("used"):
            await ix.response.send_message("❌ คูปองนี้ถูกใช้ไปแล้ว", ephemeral=True); return
        if coup.get("uid") and coup["uid"] != self.uid:
            await ix.response.send_message("❌ คูปองนี้ไม่ใช่ของคุณ", ephemeral=True); return
        reward = int(coup.get("reward", 0))
        if reward > 0:
            add_money(self.uid, reward)
        coup["used"] = True
        coup["used_by"] = self.uid
        coup["used_at"] = int(time.time())
        save_coupons(coupons)
        await ix.response.send_message(
            f"✅ ใช้คูปอง `{code}` สำเร็จ! ได้รับ {money_str(reward)} 🎉",
            ephemeral=True,
        )


# ── Slash Commands ─────────────────────────────────────────────
@bot.tree.command(name="ร้าน", description="เปิดร้านค้า Orion", guild=_ORION_GUILD_OBJ)
async def cmd_shop(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    ensure_orion_player(str(interaction.user.id))
    shop = load_shop()
    await interaction.response.send_message(
        embed=_shop_embed(shop),
        view=ShopView(),
        ephemeral=_eph("ร้าน"),
    )


@bot.tree.command(name="ร้านแอดมิน", description="[Admin] จัดการร้านค้า", guild=_ORION_GUILD_OBJ)
async def cmd_shop_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    shop = load_shop()
    embed = make_menu_embed(
        f"Shop Admin — {shop.get('name', 'Shop')}",
        [
            (f"สินค้า: `{len(shop.get('items', {}))}`", "จำนวนสินค้าในร้าน"),
            ("ตั้งชื่อร้าน", "เปลี่ยนชื่อและคำอธิบายร้าน"),
            ("เพิ่มสินค้า", "เพิ่มสินค้าใหม่"),
            ("ดาวน์โหลด / อัปโหลด JSON", "Export/Import ข้อมูลร้านทั้งหมด"),
        ],
        color=0x00b894,
    )
    await interaction.response.send_message(embed=embed, view=ShopAdminView(), ephemeral=True)


@bot.tree.command(name="ร้านอัปโหลด", description="[Admin] อัปโหลด JSON เพื่ออัปเดตร้านค้า", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(file="ไฟล์ JSON ร้านค้า (ดาวน์โหลดจาก /ร้านแอดมิน ก่อน)")
async def cmd_shop_upload(interaction: discord.Interaction, file: discord.Attachment):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    if not file.filename.endswith(".json"):
        await interaction.response.send_message("❌ ต้องเป็นไฟล์ .json", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            await interaction.followup.send("❌ รูปแบบ JSON ไม่ถูกต้อง — ต้องเป็น object {}", ephemeral=True); return
        # Validate structure
        if "_comment" in data:
            data.pop("_comment")
        if "items" not in data:
            data["items"] = {}
        save_shop(data)
        n = len(data.get("items", {}))
        await interaction.followup.send(
            f"✅ อัปโหลดสำเร็จ — ร้าน **{data.get('name', 'Shop')}** · `{n}` สินค้า",
            ephemeral=True,
        )
    except json.JSONDecodeError as e:
        await interaction.followup.send(f"❌ JSON parse error: `{e}`", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)


@bot.tree.command(name="คูปอง", description="ดูและใช้คูปองส่วนลด", guild=_ORION_GUILD_OBJ)
async def cmd_coupon(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    embed = make_menu_embed(
        "🎫 Coupon",
        [("ใช้คูปอง", "กรอกรหัสคูปองเพื่อรับรางวัล")],
        color=0xfdcb6e,
    )
    await interaction.response.send_message(
        embed=embed,
        view=CouponView(uid),
        ephemeral=_eph("คูปอง"),
    )
