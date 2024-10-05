from main import bot, decks, game_active, card_czar, black_card, submitted_cards, timer
from database import fetch_cards_from_db, DEFAULT_HAND_SIZE, players, conn, cursor
from utils import graphql_query

import discord
import sqlite3
import random
import asyncio
import requests
import logging


# Configure logging
logger = logging.getLogger(__name__) # Create a logger specific to this module.
logger.setLevel(logging.ERROR) # Log errors and above.
handler = logging.FileHandler(filename='game_logic.log', encoding='utf-8', mode='w') # Log to a file named 'game_logic.log'.
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')) # Format the log messages.
logger.addHandler(handler) # Add the handler to the logger.


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

    try:
        response = graphql_query(query)
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        return []  # Or return None

    if "data" not in response or "packs" not in response["data"]:
        logger.error("Invalid API response format")
        return []

    if pack is not None and pack not in decks:
        decks[pack] = {"black": [], "white": []}
        for pack_data in response["data"]["packs"]:
            if pack == pack_data["name"]:
                decks[pack]["black"].extend(pack_data["black"])
                decks[pack]["white"].extend(pack_data["white"])

    cards = []
    if pack is not None: #If a pack name is provided, fetch from decks.
        for card_data in decks[pack][type]:
            cards.append(card_data)
    else: #If no pack name provided, fetch all cards of the requested type.
        for pack_data in response["data"]["packs"]:
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
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO Players (player_id, username) VALUES (?, ?)",
                (player_id, user.name),
            )
            conn.commit()
        except sqlite3.Error as e:  # Catch database errors
            conn.rollback()
            logger.error(f"Database error in add_player: {e}")
            await ctx.respond(f"An error occurred adding you to the game: {e}", ephemeral=True)
            return

        await ctx.respond(f"{user.mention} joined the game!", ephemeral=True)
        await deal_cards(ctx, player_id)
    else:
        await ctx.respond(f"{user.mention} is already in the game!", ephemeral=True)


# Function to deal cards to a player
async def deal_cards(ctx, player_id, num_cards=DEFAULT_HAND_SIZE): # num_cards argument with default
    global players

    try:
        cards_to_deal = num_cards - len(players[player_id]["hand"])
        if cards_to_deal <= 0:
            return

        db_cards_raw = fetch_cards_from_db("white")
        db_cards = [card[0] for card in db_cards_raw]
        random_cards = random.sample(db_cards, k=min(cards_to_deal, len(db_cards)))
        players[player_id]["hand"].extend(random_cards)

        cards_to_deal -= len(random_cards)
        if cards_to_deal > 0:
            api_cards = await fetch_cards("white", cards_to_deal)
            players[player_id]["hand"].extend([card["text"] for card in api_cards])

    except Exception as e:
        logger.error(f"Error dealing cards: {e}")
        await ctx.respond("An error occurred dealing cards.", ephemeral=True)


# Function to start a new round
async def start_round(ctx):
    global game_active, card_czar, black_card, submitted_cards, players, decks

    if not game_active:
        await ctx.respond("Game is not active!", ephemeral=True)
        return

    try: # Wrap the Card Czar rotation logic in a try/except block
        player_ids = list(players.keys())
        if card_czar is not None:
            current_czar_index = player_ids.index(card_czar)
            next_czar_index = (current_czar_index + 1) % len(player_ids)
            card_czar = player_ids[next_czar_index]
        else:
            card_czar = player_ids[0]  # First player is the initial Czar
    except ValueError:  # Handle the potential ValueError if card_czar is not in player_ids
        logger.error("card_czar is not in player_ids list") # New
        await ctx.respond("Error rotating Czar. Please start a new game", ephemeral=True)  #
        return # New


    await ctx.respond(
        f"**Round Start!**\n{bot.get_user(card_czar).mention} is the Card Czar.",
        ephemeral=True,
    )

    # Fetch a random black card. Prioritize Decks then database then API
    if decks:  # Prioritize cards from selected packs (if any)
        selected_packs = [pack_name for pack_name, pack_data in decks.items() if pack_data.get("enabled", True)]
        if selected_packs:
            chosen_pack = random.choice(selected_packs)
            black_card = random.choice(decks[chosen_pack]["black"])
        else:
            black_card = await fetch_cards("black")
            black_card = black_card[0] if black_card else None
    elif cursor.execute("SELECT card_text FROM Cards WHERE card_type = 'black' AND enabled = TRUE").fetchone(): # Check if the cursor returns any values
        db_cards = cursor.fetchall()
        black_card = random.choice(db_cards) if db_cards else None
        black_card = black_card[0] if black_card else None  # Extract text and handle None
    else:
        black_card = (await fetch_cards("black"))[0]

    if black_card is None:
        await ctx.send("No black cards available. Game cannot start.")
        game_active = False
        return

    black_card_text = black_card[0] if isinstance(black_card, tuple) else black_card.get('text', None)

    if black_card_text is None:  # Ensure the card text exists
        await ctx.send("Invalid black card format. Game cannot start.")  # Added new error message
        game_active = False
        return

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


# Function to handle card submissions and Czar selection
@bot.event
async def on_interaction(interaction):
    global submitted_cards, black_card, players, card_czar

    if interaction.component.style == discord.ButtonStyle.blurple:
        player_id = interaction.user.id

        if player_id != card_czar:  # Player card submission
            card_index = int(interaction.component.label) - 1
            card = players[player_id]["hand"][card_index]
            submitted_cards[player_id] = card["text"]
            players[player_id]["hand"].pop(card_index)

            await interaction.response.defer()
            await interaction.followup.send(
                f"Card submitted successfully!", ephemeral=True
            )

            if len(submitted_cards) == len(players) - 1:
                await end_round(interaction)


        elif player_id == card_czar:  # Card Czar selection
            winning_card_index = int(interaction.component.label.split()[1]) - 1
            winning_player_id = list(submitted_cards.keys())[winning_card_index]
            winning_card = submitted_cards[winning_player_id]

            # Update player stats in database
            cursor.execute(
                "UPDATE Players SET wins = wins + 1, games_played = games_played + 1 WHERE player_id = ?",
                (winning_player_id,),
            )
            conn.commit()

            # Store winning combination
            cursor.execute(
                "INSERT INTO WinningCards (player_id, black_card_text, white_card_text) VALUES (?, ?, ?)",
                (winning_player_id, black_card["text"], winning_card),
            )
            conn.commit()

            players[winning_player_id]["wins"] += 1
            players[winning_player_id]["games_played"] += 1

            await interaction.response.send_message(
                f"**Winning Card:** {winning_card} submitted by {bot.get_user(winning_player_id).mention}", ephemeral=False
            )

            await between_rounds(interaction)


# Function to end a round
async def end_round(interaction):
    global card_czar, black_card, submitted_cards, players
    ctx = interaction.channel # Get ctx from interaction

    cards_message = (
        f"**Black Card:**\n{black_card['text']}\n\n**Submitted Cards:**\n"
    )
    for card_text in submitted_cards.values():
        cards_message += f"- {card_text}\n"
    await ctx.send(cards_message)


    card_options = []
    for i, card_text in enumerate(submitted_cards.values()):
        card_options.append(
            discord.ui.Button(
                label=f"Card {i + 1}", style=discord.ButtonStyle.blurple
            )
        )

    await bot.get_user(card_czar).send(
        f"**Select the winning card:**\n{cards_message}",
        components=card_options,
    )


async def between_rounds(ctx):
    global game_active, players, timer
    if not game_active:  # Don't start next round if game isn't active
        return

    await ctx.send(f"Next round in {timer} seconds. Type /join to join.", delete_after=timer)
    await asyncio.sleep(timer)

    # Check for players who left the server
    players = {player_id: player_data for player_id, player_data in players.items() if bot.get_user(player_id) is not None}

    # Deal new cards
    for player_id in players:
        await deal_cards(ctx, player_id)

    # Check if there are enough players for next round
    if len(players) < 2:  # Need at least 2 players (1 Czar, 1 player)
        await ctx.send("Not enough players to continue. Game ended.")
        game_active = False  # End the game
        return

    await start_round(ctx)


# Function to handle player disconnects
@bot.event
async def on_member_remove(member):
    global players
    player_id = member.id
    if player_id in players:
        del players[player_id]
        # Get the default channel of the guild the member left.
        guild = member.guild
        if guild:
            default_channel = guild.system_channel
            if default_channel:
                await default_channel.send(f"{member.mention} left the game.")


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
