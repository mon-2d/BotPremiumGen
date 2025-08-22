import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import json
import os
from datetime import datetime

from myserver import server_on

# ===== การตั้งค่า =====
DATA_FILE = "stock.json"
HISTORY_FILE = "history.json"
BLACKLIST_FILE = "blacklist.json"
PREMIUM_FILE = "premium.json"
PREMIUM_STOCK_FILE = "stock_prm.json"
PREMIUM_BLACKLIST_FILE = "blacklist_prm.json"

# เก็บเวลาล่าสุดที่ user ใช้ /gen
cooldowns = {}
status_channel_id = None  # ช่องแจ้งเตือนทุก 15 นาที

# ===== สร้างไฟล์ถ้ายังไม่มี =====
for file, default in [(DATA_FILE, {"stock": []}), 
                      (HISTORY_FILE, {}), 
                      (BLACKLIST_FILE, []), 
                      (PREMIUM_FILE, []),
                      (PREMIUM_STOCK_FILE, {"stock": []}), 
                      (PREMIUM_BLACKLIST_FILE, [])]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

# ===== ฟังก์ชันโหลด/บันทึก =====
def load_stock():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["stock"]

def save_stock(stock):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"stock": stock}, f, ensure_ascii=False, indent=2)

def load_history():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_blacklist():
    with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_blacklist(blist):
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(blist, f, ensure_ascii=False, indent=2)

def load_premium():
    with open(PREMIUM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_premium(premium):
    with open(PREMIUM_FILE, "w", encoding="utf-8") as f:
        json.dump(premium, f, ensure_ascii=False, indent=2)

def load_premium_stock():
    with open(PREMIUM_STOCK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["stock"]

def save_premium_stock(stock):
    with open(PREMIUM_STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump({"stock": stock}, f, ensure_ascii=False, indent=2)

def load_blacklist_prm():
    with open(PREMIUM_BLACKLIST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_blacklist_prm(blist):
    with open(PREMIUM_BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(blist, f, ensure_ascii=False, indent=2)

# ===== ตั้งค่า bot =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Event on_ready =====
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ===== /genprm =====
@bot.tree.command(name="genprm", description="สุ่ม Premium Stock ส่ง DM (สูงสุด 2)")
@app_commands.describe(amount="จำนวนที่ต้องการ (สูงสุด 2)")
async def genprm(interaction: discord.Interaction, amount: int = 1):
    user_id = str(interaction.user.id)

    if user_id in load_blacklist_prm():
        await interaction.response.send_message("⛔ คุณถูกแบนจาก Premium", ephemeral=True)
        return

    premium = load_premium()
    if user_id not in premium:
        await interaction.response.send_message("❌ เฉพาะ Premium Users เท่านั้น", ephemeral=True)
        return

    if amount > 2:
        await interaction.response.send_message("⚠️ เจน Premium ได้สูงสุดครั้งละ 2", ephemeral=True)
        return

    stock = load_premium_stock()
    if len(stock) == 0:
        await interaction.response.send_message("❌ Premium Stock หมดแล้ว", ephemeral=True)
        return

    # ตรวจ cooldown
    cd = cooldowns.get("premium", 0)
    last_time = interaction.user.id in cooldowns and cooldowns.get(str(interaction.user.id), None)
    now = datetime.now().timestamp()
    if last_time and now - last_time < cd:
        await interaction.response.send_message(f"⏳ คุณต้องรออีก {int(cd - (now - last_time))} วินาที", ephemeral=True)
        return
    cooldowns[str(interaction.user.id)] = now

    take = min(amount, len(stock))
    chosen = random.sample(stock, take)
    new_stock = [c for c in stock if c not in chosen]
    save_premium_stock(new_stock)

    history = load_history()
    if user_id not in history:
        history[user_id] = []
    history[user_id].append({"Acc": chosen, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "premium": True})
    history[user_id] = history[user_id][-20:]
    save_history(history)

    msg = f"🌟 Premium Acc\n```{chr(10).join(chosen)}```"
    try:
        await interaction.user.send(msg)
        await interaction.response.send_message(f"📩 Premium Acc ถูกส่งไป DM (เหลือ {len(new_stock)} ชิ้น)", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ ส่ง DM ไม่ได้\n🌟 โค้ด:\n```{chr(10).join(chosen)}```", ephemeral=True)

# ===== /addstockprm =====
@bot.tree.command(name="addstockprm", description="เพิ่ม Premium Stock (admin only)")
async def addstockprm(interaction: discord.Interaction, file: discord.Attachment):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    if not file.filename.endswith(".txt"):
        await interaction.response.send_message("❌ ต้องเป็นไฟล์ .txt", ephemeral=True)
        return
    content = await file.read()
    lines = [line.strip() for line in content.decode("utf-8").splitlines() if line.strip()]
    stock = load_premium_stock()
    stock.extend(lines)
    save_premium_stock(stock)
    await interaction.response.send_message(f"✅ เพิ่ม Premium Stock {len(lines)} รายการ", ephemeral=True)

# ===== /removestockprm =====
@bot.tree.command(name="removestockprm", description="ลบ Premium Stock ทั้งหมด (admin only)")
async def removestockprm(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    save_premium_stock([])
    await interaction.response.send_message("✅ ลบ Premium Stock ทั้งหมดแล้ว", ephemeral=True)


# ===== /checkstockprm =====
@bot.tree.command(
    name="checkstockprm",
    description="ตรวจสอบจำนวน Premium Stock ที่เหลือ (เฉพาะ Premium Users)"
)
async def checkstockprm(interaction: discord.Interaction):
    premium = load_premium()
    if str(interaction.user.id) not in premium:
        await interaction.response.send_message(
            "❌ เฉพาะ Premium Users เท่านั้น", ephemeral=True
        )
        return

    stock = load_premium_stock()
    await interaction.response.send_message(
        f"📦 Premium Stock คงเหลือ: {len(stock)}", ephemeral=True
    )

# ===== /addpremium =====
@bot.tree.command(name="addpremium", description="เพิ่มสิทธิ Premium ให้ user (admin only)")
async def addpremium(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    premium = load_premium()
    if str(user.id) not in premium:
        premium.append(str(user.id))
        save_premium(premium)
        await interaction.response.send_message(f"✅ {user.mention} ได้รับ Premium", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {user.mention} มี Premium อยู่แล้ว", ephemeral=True)

# ===== /removepremium =====
@bot.tree.command(name="removepremium", description="ลบสิทธิ Premium ของ user (admin only)")
async def removepremium(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    premium = load_premium()
    if str(user.id) in premium:
        premium.remove(str(user.id))
        save_premium(premium)
        await interaction.response.send_message(f"✅ {user.mention} ถูกลบ Premium", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {user.mention} ไม่มี Premium", ephemeral=True)

# ===== /checkpremium =====
@bot.tree.command(name="checkpremium", description="ตรวจสอบสิทธิ Premium ของคุณ")
async def checkpremium(interaction: discord.Interaction):
    if str(interaction.user.id) in load_premium():
        await interaction.response.send_message("🌟 คุณมี Premium", ephemeral=True)
    else:
        await interaction.response.send_message("❌ คุณยังไม่มี Premium", ephemeral=True)

# ===== /blacklistprm =====
@bot.tree.command(name="blacklistprm", description="แบนผู้ใช้จาก Premium (admin only)")
async def blacklistprm(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    bl = load_blacklist_prm()
    if str(user.id) not in bl:
        bl.append(str(user.id))
        save_blacklist_prm(bl)
        await interaction.response.send_message(f"✅ {user.mention} ถูกแบนจาก Premium", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {user.mention} ถูกแบนอยู่แล้ว", ephemeral=True)

# ===== /unblacklistprm =====
@bot.tree.command(name="unblacklistprm", description="ปลดแบนผู้ใช้จาก Premium (admin only)")
async def unblacklistprm(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    bl = load_blacklist_prm()
    if str(user.id) in bl:
        bl.remove(str(user.id))
        save_blacklist_prm(bl)
        await interaction.response.send_message(f"✅ {user.mention} ถูกปลดแบนจาก Premium", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {user.mention} ไม่ได้ถูกแบน", ephemeral=True)

# ===== /historyprm =====
@bot.tree.command(
    name="historyprm",
    description="ดูประวัติการ Gen Premium ของคุณ (เฉพาะ Premium Users)"
)
async def historyprm(interaction: discord.Interaction):
    premium = load_premium()
    user_id = str(interaction.user.id)

    if user_id not in premium:
        await interaction.response.send_message(
            "❌ เฉพาะ Premium Users เท่านั้น", ephemeral=True
        )
        return

    history = load_history()
    embed = discord.Embed(
        title="📜 ประวัติการ Gen Premium",
        color=discord.Color.gold()
    )

    if user_id not in history or len(history[user_id]) == 0:
        embed.add_field(
            name=f"ของคุณ ({interaction.user})",
            value="❌ ยังไม่มีประวัติ",
            inline=False
        )
    else:
        last_5 = history[user_id][-5:]
        text = "\n".join(
            [f"{h['time']} → เจน {len(h['Acc'])} ID" for h in last_5]
        )
        embed.add_field(
            name=f"ของคุณ ({interaction.user})",
            value=text,
            inline=False
        )

    # คนล่าสุดที่ Gen Premium
    all_entries = [(uid, e) for uid, entries in history.items()
                   for e in entries if e.get("premium", False)]
    if all_entries:
        last_uid, last_entry = all_entries[-1]
        try:
            user = await bot.fetch_user(int(last_uid))
            embed.add_field(
                name="👤 คนล่าสุดที่ Gen Premium",
                value=f"{user} เวลา {last_entry['time']}",
                inline=False
            )
            embed.set_thumbnail(url=user.display_avatar.url)
        except:
            embed.add_field(
                name="👤 คนล่าสุดที่ Gen Premium",
                value=f"User ID {last_uid} เวลา {last_entry['time']}",
                inline=False
            )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===== /lastgenprm =====
@bot.tree.command(
    name="lastgenprm",
    description="ดู Premium ล่าสุดของผู้ใช้ทั้งหมด (เฉพาะ Premium Users)"
)
async def lastgenprm(interaction: discord.Interaction):
    premium = load_premium()
    if str(interaction.user.id) not in premium:
        await interaction.response.send_message(
            "❌ เฉพาะ Premium Users เท่านั้น", ephemeral=True
        )
        return

    history = load_history()
    embed = discord.Embed(
        title="🌟 Premium ล่าสุดของผู้ใช้",
        color=discord.Color.gold()
    )

    for user_id, entries in history.items():
        if not entries:
            continue
        last_entry = entries[-1]
        if not last_entry.get("premium", False):
            continue
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except:
            name = f"User ID {user_id}"
        embed.add_field(
            name=name,
            value=f"เจนไปแล้ว {len(last_entry['Acc'])} ID เวลา {last_entry['time']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== /stocktopprm =====
@bot.tree.command(
    name="stocktopprm",
    description="ดูจำนวน Premium Stock ที่เจนมากที่สุดของผู้ใช้ (เฉพาะ Premium Users)"
)
async def stocktopprm(interaction: discord.Interaction):
    premium = load_premium()
    if str(interaction.user.id) not in premium:
        await interaction.response.send_message(
            "❌ เฉพาะ Premium Users เท่านั้น", ephemeral=True
        )
        return

    history_data = load_history()
    top_list = []

    for user_id, entries in history_data.items():
        if str(user_id) not in premium:
            continue
        total_id = sum(len(e["Acc"]) for e in entries if e.get("premium", False))
        total_acc = sum(1 for e in entries if e.get("premium", False))
        if total_id > 0:
            top_list.append((user_id, total_id, total_acc))

    if not top_list:
        await interaction.response.send_message(
            "❌ ยังไม่มีผู้ใช้ Premium เจน Stock", ephemeral=True
        )
        return

    top_list.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="🏆 Top Premium Users",
        description="จำนวน Premium ID ที่เจนไปแล้ว พร้อมจำนวน Account",
        color=discord.Color.gold()
    )

    for i, (user_id, total_id, total_acc) in enumerate(top_list[:10], 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
            avatar = user.display_avatar.url
        except:
            name = f"User ID {user_id}"
            avatar = None

        embed.add_field(
            name=f"{i}. {name}",
            value=f"ID เจนไปแล้ว: {total_id}\nจำนวน Account: {total_acc}",
            inline=False
        )
        if avatar:
            embed.set_thumbnail(url=avatar)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===== /setcooldown =====
@bot.tree.command(name="setcooldown", description="ตั้งค่า cooldown การใช้ /genprm ของ Premium (admin only)")
@app_commands.describe(seconds="จำนวนวินาที cooldown")
async def setcooldown(interaction: discord.Interaction, seconds: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ แอดมินเท่านั้น", ephemeral=True)
        return
    global cooldowns
    cooldowns["premium"] = seconds
    await interaction.response.send_message(f"✅ ตั้งค่า cooldown Premium /genprm เป็น {seconds} วินาทีเรียบร้อย", ephemeral=True)

server_on

# ===== รัน bot =====
bot.run(os.getenv('TOKEN'))
