import discord
from discord.ext import commands
import os
import json

# ── Config ───────────────────────────────────────────────
with open(os.path.join(os.path.dirname(__file__), "config.json")) as f:
    config = json.load(f)

TOKEN    = config["token"]
PREFIX   = "--"
COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
# ────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


async def load_cogs():
    for filename in os.listdir(COGS_DIR):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog)
                print(f"  ✅ Loaded: {cog}")
            except Exception as e:
                print(f"  ❌ Failed to load {cog}: {e}")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"\n🤖 ShitPostBot is online!")
    print(f"   Logged in as: {bot.user} (ID: {bot.user.id})")
    print(f"   Prefix: {PREFIX}")
    print(f"   Slash commands synced ✅")
    print(f"   Servers: {len(bot.guilds)}\n")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
