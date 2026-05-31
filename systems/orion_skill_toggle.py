# ============================================================
# ORION SKILL TOGGLE — /สกิลใช้ /สกิลตั้งCD /สกิลตั้งCDผู้เล่น
# ============================================================
import discord
import time
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _safe_emoji, _eph,
    load_orion_players, save_orion_players, ensure_orion_player,
    cooldown_remaining, set_cooldown, format_cooldown, _parse_int,
)

SKILL_TOGGLE_FILE = f"{ORION_DATA_DIR}/skill_toggle.json"


def load_skill_toggle() -> dict:
    return load_json(SKILL_TOGGLE_FILE, {"global_cd": 0, "player_cds": {}})


def save_skill_toggle(d: dict):
    save_json(SKILL_TOGGLE_FILE, d)


class UseSkillSelect(discord.ui.Select):
    def __init__(self, uid: str):
        self.uid = uid
        skills = load_orion_players().get(uid, {}).get("skills", [])[:25]
        options = []
        for i, sk in enumerate(skills):
            st = load_skill_toggle()
            global_cd = int(st.get("global_cd", 0))
            player_cds = st.get("player_cds", {})
            cd_key = f"skill_use_{uid}_{i}"
            remaining = cooldown_remaining(uid, cd_key)
            cd_info = f" — CD: {format_cooldown(remaining)}" if remaining > 0 else " — พร้อม"
            options.append(discord.SelectOption(
                label=f"{sk.get('name', '?')}{cd_info}"[:100],
                value=str(i),
                description=sk.get("origin_type", "—")[:80],
                emoji=_safe_emoji(sk.get("emoji"), "✨"),
            ))
        if not options:
            options = [discord.SelectOption(label="ไม่มีสกิล", value="none")]
        super().__init__(placeholder="✨ เลือกสกิลที่จะใช้...", options=options)

    async def callback(self, ix: discord.Interaction):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return
        if self.values[0] == "none":
            await ix.response.defer(); return
        idx = int(self.values[0])
        cd_key = f"skill_use_{self.uid}_{idx}"
        remaining = cooldown_remaining(self.uid, cd_key)
        if remaining > 0:
            await ix.response.send_message(f"⏳ cooldown: **{format_cooldown(remaining)}**", ephemeral=True); return

        skills = load_orion_players().get(self.uid, {}).get("skills", [])
        if idx >= len(skills):
            await ix.response.send_message("❌ ไม่พบสกิล", ephemeral=True); return
        sk = skills[idx]

        st = load_skill_toggle()
        global_cd = int(st.get("global_cd", 0))
        player_cd = int(st.get("player_cds", {}).get(self.uid, {}).get(str(idx), global_cd))
        use_cd = player_cd if player_cd > 0 else global_cd

        if use_cd > 0:
            set_cooldown(self.uid, cd_key, use_cd)

        embed = discord.Embed(
            title=f"{_safe_emoji(sk.get('emoji'), '✨')} ใช้สกิล: {sk.get('name', '?')}",
            description=sk.get("context", "_ไม่มีคำอธิบาย_"),
            color=0xfdcb6e,
        )
        if use_cd > 0:
            embed.set_footer(text=f"Cooldown: {format_cooldown(use_cd)}")
        await ix.response.send_message(embed=embed, ephemeral=_eph("สกิลใช้"))


@bot.tree.command(name="สกิลใช้", description="เลือกและใช้สกิล (พร้อม cooldown)", guild=_ORION_GUILD_OBJ)
async def cmd_skill_use(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    ensure_orion_player(uid)
    v = discord.ui.View(timeout=120)
    v.add_item(UseSkillSelect(uid))
    v.add_item(DoneBtn(row=1))
    await interaction.response.send_message("เลือกสกิลที่จะใช้", view=v, ephemeral=_eph("สกิลใช้"))


@bot.tree.command(name="สกิลตั้งCD", description="[Admin] ตั้ง cooldown global สำหรับสกิล", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(seconds="cooldown เป็นวินาที (0 = ไม่มี CD)")
async def cmd_skill_set_cd(interaction: discord.Interaction, seconds: int):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    st = load_skill_toggle()
    st["global_cd"] = max(0, seconds)
    save_skill_toggle(st)
    await interaction.response.send_message(f"✅ Global skill CD: **{format_cooldown(seconds)}**", ephemeral=True)


@bot.tree.command(name="สกิลตั้งCDผู้เล่น", description="[Admin] ตั้ง cooldown สกิลเฉพาะผู้เล่น", guild=_ORION_GUILD_OBJ)
@discord.app_commands.describe(target="ผู้เล่น", skill_index="เลขลำดับสกิล (เริ่มที่ 1)", seconds="cooldown วินาที")
async def cmd_skill_set_cd_player(
    interaction: discord.Interaction,
    target: discord.Member, skill_index: int, seconds: int,
):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ต้องเป็นแอดมิน", ephemeral=True); return
    uid = str(target.id)
    idx = skill_index - 1
    st = load_skill_toggle()
    st.setdefault("player_cds", {}).setdefault(uid, {})[str(idx)] = max(0, seconds)
    save_skill_toggle(st)
    await interaction.response.send_message(
        f"✅ สกิล #{skill_index} ของ {target.display_name} · CD: **{format_cooldown(seconds)}**",
        ephemeral=True,
    )
