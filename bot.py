import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta
import random

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "giveaways.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def parse_duration(duration: str):
    num = int(duration[:-1])
    unit = duration[-1]

    if unit == "s":
        return timedelta(seconds=num)
    elif unit == "m":
        return timedelta(minutes=num)
    elif unit == "h":
        return timedelta(hours=num)
    elif unit == "d":
        return timedelta(days=num)
    else:
        return None


@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash komendy zsynchronizowane!")
    except Exception as e:
        print(f"Błąd synchronizacji: {e}")


@bot.tree.command(name="giveaway", description="Startuje giveaway")
@app_commands.describe(
    duration="Czas trwania (np. 10s, 5m, 1h, 2d)",
    prize="Nagroda",
    winners="Liczba zwycięzców"
)
async def giveaway(interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
    await interaction.response.defer()

    end_time = parse_duration(duration)
    if end_time is None:
        return await interaction.followup.send("❌ Niepoprawny format czasu!")

    end_timestamp = datetime.utcnow() + end_time

    embed = discord.Embed(
        title="🎉 GIVEAWAY!",
        description=f"Nagroda: **{prize}**\n"
                    f"Czas: **{duration}**\n"
                    f"Liczba zwycięzców: **{winners}**\n\n"
                    f"Kliknij 🎉 aby wziąć udział!",
        color=0x2ecc71
    )
    embed.set_footer(text=f"Zakończy się: {end_timestamp} UTC")

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")

    data = load_data()
    data[str(msg.id)] = {
        "prize": prize,
        "winners": winners,
        "end": end_timestamp.timestamp(),
        "channel": interaction.channel.id
    }
    save_data(data)

    await interaction.followup.send("🎉 Giveaway wystartował!")


@bot.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name != "🎉":
        return

    data = load_data()
    if str(payload.message_id) not in data:
        return


@bot.event
async def on_ready():
    print("Giveaway bot wystartował!")
    asyncio.create_task(giveaway_watcher())


async def giveaway_watcher():
    await bot.wait_until_ready()

    while True:
        now = datetime.utcnow().timestamp()
        data = load_data()
        changed = False

        for msg_id, info in list(data.items()):
            if now >= info["end"]:
                channel = bot.get_channel(info["channel"])
                try:
                    msg = await channel.fetch_message(int(msg_id))
                except:
                    continue

                users = []
                for reaction in msg.reactions:
                    if reaction.emoji == "🎉":
                        users = [u async for u in reaction.users() if not u.bot]

                if not users:
                    await channel.send(f"❌ Giveaway na **{info['prize']}** zakończony — brak uczestników.")
                else:
                    winners = random.sample(users, min(info["winners"], len(users)))
                    winner_mentions = ", ".join([w.mention for w in winners])
                    await channel.send(f"🎉 Giveaway wygrali: {winner_mentions}\nNagroda: **{info['prize']}**")

                del data[msg_id]
                changed = True

        if changed:
            save_data(data)

        await asyncio.sleep(5)


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
