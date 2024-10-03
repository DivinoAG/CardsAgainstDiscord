import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from commands import *
from database import setup_database, conn, fetch_cards_from_db, DATABASE_NAME, DEFAULT_HAND_SIZE
from game_logic import *
import logging

# Configure logging (at the top of main.py)
logging.basicConfig(filename="bot.log", level=logging.ERROR)

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
