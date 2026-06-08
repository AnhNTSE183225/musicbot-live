import discord
from discord.ext import commands
import logging
import sys

# Setup basic logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

class MusicBot(commands.Bot):
    def __init__(self):
        # Event-driven architecture: Intents define which events we receive
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Asynchronous programming: Load extensions non-blockingly
        await self.load_extension("cogs.voice")
        print("Bot setup complete. Voice cog loaded.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
