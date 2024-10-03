import discord
from discord.ext import commands
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta
import requests

# Replace with your actual GraphQL API URL
API_URL = "https://restagainsthumanity.com/api/graphql"

# Database setup
conn = sqlite3.connect("cards_against_humanity.db")
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS Players (
        player_id INTEGER PRIMARY KEY,
        username TEXT,
        wins INTEGER DEFAULT 0,
        games_played INTEGER DEFAULT 0
    )
    """
)
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS WinningCards (
        combination_id INTEGER PRIMARY KEY,
        player_id INTEGER,
        black_card_text TEXT,
        white_card_text TEXT,
        votes INTEGER DEFAULT 0,
        FOREIGN KEY (player_id) REFERENCES Players(player_id)
    )
    """
)
conn.commit()

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

# GraphQL API client
def graphql_query(query):
    response = requests.post(API_URL, json={"query": query})
    response.raise_for_status()
    return response.json()

# Function to fetch cards from the API
async def fetch_cards(type, limit=10, pack=None):
    if type == "black":
        query = """
        query {
          packs {
            name
            black(where: { pick: 2 }) {
              text
              pick
            }
          }
        }
        """
    elif type == "white":
        query = """
        query {
          packs {
            name
            white {
              text
            }
          }
        }
        """
    else:
        raise ValueError("Invalid card type")

    response = graphql_query(query)
    cards = []
    for pack_data in response["data"]["packs"]:
        if pack is None or pack == pack_data["name"]:
            if type == "black":
                cards.extend(pack_data["black"])
            elif type == "white":
                cards.extend(pack_data["white"])

    if len(cards) >= limit:
        return random.sample(cards, limit)
    else:
        return cards

# Function to add a player to the game
async def add_player(ctx, user):
    global players
    player_id = user.id
    if player_id not in players:
        players[player_id] = {
            "username": user.name,
            "hand": [],
            "wins": 0,
            "games_played": 0,
        }
        cursor.execute(
            "INSERT OR IGNORE INTO Players (player_id, username) VALUES (?, ?)",
            (player_id, user.name),
        )
        conn.commit()
        await ctx.respond(f"{user.mention} joined the game!", ephemeral=True)
        await deal_cards(player_id)
    else:
        await ctx.respond(f"{user.mention} is already in the game!", ephemeral=True)

# Function to deal cards to a player
async def deal_cards(player_id):
    global players
    for _ in range(10 - len(players[player_id]["hand"])):
        cards = await fetch_cards("white", 1)
        players[player_id]["hand"].append(cards[0])

# Function to start a new round
async def start_round():
    global game_active, card_czar, black_card, submitted_cards, players

    if not game_active:
        await ctx.respond("Game is not active!", ephemeral=True)
        return

    # Assign card czar
    card_czar = next(iter(players))
    await ctx.respond(
        f"**Round Start!**\n{bot.get_user(card_czar).mention} is the Card Czar.",
        ephemeral=True,
    )

    # Fetch a random black card
    black_card = await fetch_cards("black")[0]

    # Post the black card
    await ctx.send(
        f"**Black Card:**\n{black_card['text']}\n\nSubmit your cards using the buttons below."
    )

    # Send ephemeral messages to players with their white cards
    submitted_cards = {}
    for player_id in players:
        if player_id != card_czar:
            cards = players[player_id]["hand"]
            message = "\n".join(
                f"{i+1}. {card['text']}" for i, card in enumerate(cards)
            )
            await bot.get_user(player_id).send(
                f"**Your White Cards:**\n{message}\n\nPlease select one card:",
                components=[
                    discord.ui.Button(
                        label=str(i + 1), style=discord.ButtonStyle.blurple
                    )
                    for i in range(len(cards))
                ],
            )

# Function to handle card submissions
@bot.event
async def on_interaction(interaction):
    global submitted_cards
    if interaction.component.style == discord.ButtonStyle.blurple:
        # Get the selected card index
        card_index = int(interaction.component.label) - 1

        # Get the player's white card
        player_id = interaction.user.id
        card = players[player_id]["hand"][card_index]

        # Add the card to submitted cards
        submitted_cards[player_id] = card["text"]

        # Remove the card from the player's hand
        players[player_id]["hand"].pop(card_index)

        await interaction.response.defer()
        await interaction.followup.send(
            f"Card submitted successfully!", ephemeral=True
        )

        # Check if all players have submitted
        if len(submitted_cards) == len(players) - 1:
            await end_round()

# Function to end a round
async def end_round():
    global card_czar, black_card, submitted_cards, players

    # Post all submitted cards to the channel
    cards_message = (
        f"**Black Card:**\n{black_card['text']}\n\n**Submitted Cards:**\n"
    )
    for card_text in submitted_cards.values():
        cards_message += f"- {card_text}\n"
    await ctx.send(cards_message)

    # Send the Card Czar an ephemeral message to select the winner
    card_options = []
    for i, card_text in enumerate(submitted_cards.values()):
        card_options.append(
            discord.ui.Button(
                label=f"Card {i + 1}", style=discord.ButtonStyle.blurple
            )
        )

    # Send an ephemeral message to the Card Czar with the submitted cards
    await bot.get_user(card_czar).send(
        f"**Select the winning card:**\n{cards_message}",
        components=card_options,
    )

# Function to handle Card Czar's card selection
@bot.event
async def on_interaction(interaction):
    # ... (Implement logic to handle Card Czar's card selection)

# Function to handle player disconnects
@bot.event
async def on_member_remove(member):
    global players
    player_id = member.id
    if player_id in players:
        del players[player_id]
        await ctx.send(f"{member.mention} left the game.")

# Function to display player statistics
@bot.command()
async def stats(ctx, username=None):
    if username is None:
        await ctx.respond("Please specify a username!", ephemeral=True)
        return

    cursor.execute(
        "SELECT wins, games_played FROM Players WHERE username = ?", (username,)
    )
    result = cursor.fetchone()
    if result is None:
        await ctx.respond(f"{username} not found in the database.", ephemeral=True)
        return

    wins, games_played = result
    win_rate = round((wins / games_played) * 100, 2) if games_played > 0 else 0
    await ctx.respond(
        f"**{username} Stats:**\nWins: {wins}\nGames Played: {games_played}\nWin Rate: {win_rate}%",
        ephemeral=True,
    )

# Slash command handlers
@bot.slash_command(name="join", description="Join the Cards Against Humanity game")
async def join(ctx):
    await add_player(ctx, ctx.author)

# ... (Implement other slash command handlers for admin commands and player stats)

# Main bot loop
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Run the bot with your bot token
bot.run("YOUR_BOT_TOKEN")
