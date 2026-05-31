# ============================================================
# ORION ROLES SYSTEM — /บทบาท /บทบาทแอดมิน
# ============================================================
import discord
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _eph, get_wallet, add_money, money_str, _parse_int,
)

ROLES_FILE = f"{ORION_DATA_DIR}/roles_config.json"

def load_roles_cfg() -> dict:
    return load_json(ROLES_FILE, {"shop_roles": {}})

def save_roles_cfg(d: dict):
    save_json(ROLES_FILE, d)


class RoleShopSelect(discord.ui.Select):
    def __init__(self, uid: str):
        self.uid = uid
        cfg = load_roles_cfg()
        roles = list(cfg.get("shop_roles", {}).items())[:25]
        options = []
        for rid, info in roles:
            options.append(discord.SelectOption(
                label=info.get("name", rid)[:100],
                value=rid,
                description=f"ราคา: {int(info.get('price', 0)):,}"[:80],
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มี role ที่ขาย", value="none")]
        super().__init__(placeholder="🎭 เลือก role ที่ต้องการซื้อ...", options=options)

    async def callback(self, ix: discord.Interaction):
        if self.values[0] == "none":
            await ix.response.defer(); return
        rid = self.values[0]
        cfg = load_roles_cfg()
        info = cfg.get("shop_roles", {}).get(rid)
        if not info:
            await ix.response.send_message("❌ ไม่พบ role", ephemeral=True); return
        price = int(info.get("price", 0))
        if get_wallet(self.uid) < price:
            await ix.response.send_message(f"❌ เงินไม่พอ — ต้องการ {money_str(price)}", ephemeral=True); return
        role = ix.guild.get_role(int(rid))
        if not role:
            await ix.response.send_message("❌ ไม่พบ role บน server", ephemeral=True); return
        if role in ix.user.roles:
            await ix.response.send_message("❌ คุณมี role นี้อยู่แล้ว", ephemeral=True); return
        add_money(self.uid, -price)
        await ix.user.add_roles(role)
        await ix.response.send_message(f"✅ ซื้อ role **{role.name}** สำเร็จ!", ephemeral=True)


class RolesView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=300)
        self.add_item(RoleShopSelect(uid))
        self.add_item(DoneBtn(row=1))


class AddRoleShopModal(discord.ui.Modal, title="➕ เพิ่ม Role ขาย"):
    f_rid   = discord.ui.TextInput(label="Role ID", max_length=25)
    f_name  = discord.ui.TextInput(label="ชื่อที่แสดง", max_length=50)
    f_price = discord.ui.TextInput(label="ราคา", placeholder="500", max_length=10)

    async def on_submit(self, ix: discord.Interaction):
        cfg = load_roles_cfg()
        cfg.setdefault("shop_roles", {})[self.f_rid.value.strip()] = {
            "name": self.f_name.value.strip(),
            "price": max(0, _parse_int(self.f_price.value, 500) or 500),
        }
        save_roles_cfg(cfg)
        await ix.response.send_message(f"✅ เพิ่ม **{self.f_name.value}** ราคา {money_str(_parse_int(self.f_price.value, 500))}", ephemeral=True)


class RolesAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
    async def interaction_check(self, ix):
        if not ix.user.guild_permissions.administrator:
            await ix.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return False
        return True
    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)
    @discord.ui.button(label="เพิ่ม Role", style=discord.ButtonStyle.success, row=1)
    async def add(self, ix, _b):
        await ix.response.send_modal(AddRoleShopModal())


@bot.tree.command(name="บทบาท", description="ดูและซื้อ role ด้วยเงิน", guild=_ORION_GUILD_OBJ)
async def cmd_roles(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    cfg = load_roles_cfg()
    roles = cfg.get("shop_roles", {})
    embed = discord.Embed(title="🎭 Role Shop", color=0x9b59b6)
    if roles:
        lines = [f"• **{v.get('name', k)}** — {money_str(int(v.get('price', 0)))}" for k, v in list(roles.items())[:15]]
        embed.description = "\n".join(lines)
    else:
        embed.description = "_ไม่มี role ที่ขายตอนนี้_"
    await interaction.response.send_message(embed=embed, view=RolesView(uid), ephemeral=_eph("บทบาท"))


@bot.tree.command(name="บทบาทแอดมิน", description="[Admin] จัดการ Role Shop", guild=_ORION_GUILD_OBJ)
async def cmd_roles_admin(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    cfg = load_roles_cfg()
    embed = make_menu_embed("Role Admin", [(f"Roles ที่ขาย: `{len(cfg.get('shop_roles', {}))}`", "")], color=0x9b59b6)
    await interaction.response.send_message(embed=embed, view=RolesAdminView(), ephemeral=True)
