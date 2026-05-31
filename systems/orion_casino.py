# ============================================================
# ORION CASINO — /คาสิโน /คาสิโนห้อง
# ============================================================
import discord
import random
import orion_bot as _bot_module
bot = _bot_module.bot
from orion_bot import (
    load_json, save_json, ORION_DATA_DIR, ALLOWED_COMMAND_GUILD_IDS, _ORION_GUILD_OBJ,
    make_menu_embed, DoneBtn, _eph, get_wallet, add_money, money_str, _parse_int,
)

def _coin_flip(bet: int, uid: str) -> tuple:
    win = random.random() < 0.5
    if win:
        add_money(uid, bet)
        return True, bet
    else:
        add_money(uid, -bet)
        return False, bet

def _slots(bet: int, uid: str) -> tuple:
    symbols = ["🍒", "🍊", "🍋", "⭐", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]
    if reels[0] == reels[1] == reels[2]:
        mult = 5 if reels[0] == "💎" else (10 if reels[0] == "7️⃣" else 3)
        win = bet * mult
        add_money(uid, win)
        return True, reels, win
    else:
        add_money(uid, -bet)
        return False, reels, bet


class CasinoView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=300)
        self.uid = uid
    async def interaction_check(self, ix):
        if str(ix.user.id) != self.uid:
            await ix.response.send_message("❌ ไม่ใช่เมนูของคุณ", ephemeral=True); return False
        return True
    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=0)
    async def done(self, ix, _b):
        await ix.response.edit_message(content="✓", embed=None, view=None)
    @discord.ui.button(label="🪙 Coin Flip", style=discord.ButtonStyle.primary, row=1)
    async def flip(self, ix, _b):
        await ix.response.send_modal(CoinFlipModal(self.uid))
    @discord.ui.button(label="🎰 Slots", style=discord.ButtonStyle.primary, row=2)
    async def slots(self, ix, _b):
        await ix.response.send_modal(SlotsModal(self.uid))


class CoinFlipModal(discord.ui.Modal, title="🪙 Coin Flip"):
    f_bet = discord.ui.TextInput(label="จำนวนเงินที่เดิมพัน", placeholder="100", max_length=10)
    def __init__(self, uid: str):
        super().__init__(); self.uid = uid
    async def on_submit(self, ix: discord.Interaction):
        bet = _parse_int(self.f_bet.value)
        if not bet or bet <= 0:
            await ix.response.send_message("❌ จำนวนต้องบวก", ephemeral=True); return
        if get_wallet(self.uid) < bet:
            await ix.response.send_message(f"❌ เงินไม่พอ — มี {money_str(get_wallet(self.uid))}", ephemeral=True); return
        won, amount = _coin_flip(bet, self.uid)
        result = "🎉 ชนะ!" if won else "💀 แพ้..."
        bal = get_wallet(self.uid)
        await ix.response.send_message(
            f"🪙 **{result}** {'ได้' if won else 'เสีย'} {money_str(amount)} | ยอด: {money_str(bal)}",
            ephemeral=_eph("คาสิโน"),
        )


class SlotsModal(discord.ui.Modal, title="🎰 Slot Machine"):
    f_bet = discord.ui.TextInput(label="จำนวนเดิมพัน", placeholder="50", max_length=10)
    def __init__(self, uid: str):
        super().__init__(); self.uid = uid
    async def on_submit(self, ix: discord.Interaction):
        bet = _parse_int(self.f_bet.value)
        if not bet or bet <= 0:
            await ix.response.send_message("❌ จำนวนต้องบวก", ephemeral=True); return
        if get_wallet(self.uid) < bet:
            await ix.response.send_message(f"❌ เงินไม่พอ", ephemeral=True); return
        won, reels, amount = _slots(bet, self.uid)
        reel_str = " | ".join(reels)
        bal = get_wallet(self.uid)
        if won:
            msg = f"🎰 {reel_str}\n🎉 **JACKPOT!** ได้ {money_str(amount)}"
        else:
            msg = f"🎰 {reel_str}\n💀 แพ้ {money_str(amount)}"
        await ix.response.send_message(f"{msg}\nยอด: {money_str(bal)}", ephemeral=_eph("คาสิโน"))


@bot.tree.command(name="คาสิโน", description="เล่น Coin Flip และ Slots", guild=_ORION_GUILD_OBJ)
async def cmd_casino(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    uid = str(interaction.user.id)
    embed = make_menu_embed("🎲 Casino", [("Coin Flip", "โอกาสชนะ 50%"), ("Slots", "ตี jackpot 3 แถว")], color=0xf1c40f)
    await interaction.response.send_message(embed=embed, view=CasinoView(uid), ephemeral=_eph("คาสิโน"))


@bot.tree.command(name="คาสิโนห้อง", description="คาสิโน private ระหว่างผู้เล่น", guild=_ORION_GUILD_OBJ)
async def cmd_casino_room(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id not in ALLOWED_COMMAND_GUILD_IDS:
        await interaction.response.send_message("❌ ใช้ได้เฉพาะในเซิร์ฟ Orion", ephemeral=True); return
    embed = discord.Embed(title="🎲 Casino Room", description="_ระบบ private casino coming soon_", color=0xf1c40f)
    await interaction.response.send_message(embed=embed, ephemeral=_eph("คาสิโนห้อง"))
