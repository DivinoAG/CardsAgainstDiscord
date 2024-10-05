import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from database import setup_database
import logging

# Configure logging (at the top of main.py)
logger = logging.getLogger(__name__) # Create a logger specific to this module.
logger.setLevel(logging.ERROR) # Log errors and above.
handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w') # Log to a file named 'game_logic.log'.
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')) # Format the log messages.
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
