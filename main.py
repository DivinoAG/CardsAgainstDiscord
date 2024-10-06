import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from database import setup_database
import logging
import logging.handlers

# Configure logging (at the top of main.py)
logger = logging.getLogger('discord') # Create a logger specific to this module.
logger.setLevel(logging.DEBUG) # Log errors and above.
logging.getLogger('discord.http').setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    maxBytes=32 * 1024 * 1024,  # 32 MiB
    backupCount=5,  # Rotate through 5 files
)
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler) # Add the handler to the logger.

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Constants
API_URL = "https://restagainsthumanity.com/api/graphql"

# Database setup
setup_database()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global variables
game_active = False
card_czar = None
black_card = None
submitted_cards = {}
players = {}
timer = 10  # Default timer in seconds
decks = {}

# Main bot loop
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Run the bot
bot.run(TOKEN)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Attempting to sync commands...")
    await bot.tree.sync()
    print("Commands synced.")

@bot.tree.command(name="test", description="Test command")
async def test(interaction: discord.Interaction):
    print("Test command invoked!")
    await interaction.response.send_message("Test successful!", ephemeral=True)
