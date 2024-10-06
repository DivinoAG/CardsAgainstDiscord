import sqlite3
import discord
from discord.ext import commands
from main import bot, game_active, players, timer, decks, logger
from game_logic import add_player, start_round
from database import conn, cursor
from utils import graphql_query
from thefuzz import fuzz
import requests


@bot.tree.command(name="join", description="Join the Cards Against Humanity game")
async def join(interaction: discord.Interaction):
    try:
        await add_player(interaction, interaction.user)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred joining the game: {e}", ephemeral=True)


@bot.tree.command(name="settimer", description="Set the between-rounds timer (in seconds)")
@commands.has_permissions(administrator=True)  # Restrict to admins
async def settimer(interaction: discord.Interaction, seconds: int):
    global timer
    try:
        seconds = int(seconds)  # Convert to integer
        if 10 <= seconds <= 60:  # Enforce reasonable limits
            timer = seconds
            await interaction.response.send_message(f"Timer set to {seconds} seconds.", ephemeral=True)
        else:
            await interaction.response.send_message("Timer must be between 10 and 60 seconds.", ephemeral=True)
    except ValueError: # Handle error if input isn't a number
        await interaction.response.send_message("Invalid input. Please enter a number.", ephemeral=True)

@bot.tree.command(name="start", description="Start the game (admin only)")
@commands.has_permissions(administrator=True)
async def start_game(interaction: discord.Interaction):
    global game_active
    game_active = True
    await start_round(interaction)


@bot.tree.command(name="addcards", description="Add cards (admin only)")
@commands.has_permissions(administrator=True)
async def add_cards(interaction: discord.Interaction, pack_name: str, card_type: str, card_text: str):
    if card_type.lower() not in ("black", "white"):  # Validate card_type
        await interaction.response.send_message("Invalid card type. Must be 'black' or 'white'.", ephemeral=True)
        return

    try:
        cursor.execute(
            "INSERT INTO Cards (pack_name, card_type, card_text) VALUES (?, ?, ?)",
            (pack_name, card_type.lower(), card_text),  # Ensure card_type is lowercase
        )
        conn.commit()
        await interaction.response.send_message(f"Card '{card_text}' added to pack '{pack_name}' successfully!", ephemeral=True)  # More informative message
    except sqlite3.IntegrityError as e:  # Specific error for integrity violations (duplicates, etc.)
        conn.rollback()
        await interaction.response.send_message(f"Error adding card: {e}", ephemeral=True)  # More specific error message if possible
    except sqlite3.Error as e:  # Catch other SQLite errors
        conn.rollback()
        await interaction.response.send_message(f"Database error: {e}", ephemeral=True)


@bot.tree.command(name="removecards", description="Remove cards (admin only)")
@commands.has_permissions(administrator=True)
async def remove_cards(interaction: discord.Interaction, card_id: int):
    try:
        cursor.execute("SELECT card_text FROM Cards WHERE card_id = ?", (card_id,))
        deleted_card = cursor.fetchone()

        cursor.execute("DELETE FROM Cards WHERE card_id = ?", (card_id,))
        if cursor.rowcount == 0:  # Check if any rows were affected, i.e. a card was deleted.
            await interaction.response.send_message("Card not found.", ephemeral=True)
            return  # Exit early if no card was found

        conn.commit()
        await interaction.response.send_message(f"Card '{deleted_card[0]}' removed successfully!", ephemeral=True)

    except sqlite3.Error as e:  # Catch SQLite errors
        conn.rollback()
        await interaction.response.send_message(f"Database error: {e}", ephemeral=True)


@bot.tree.command(name="searchcards", description="Search for cards by text (admin only)")
@commands.has_permissions(administrator=True)
async def search_cards(interaction: discord.Interaction, search_term: str):
    try:
        search_term = search_term.lower() # Ensure case-insensitive search.

        cursor.execute(
            "SELECT card_id, pack_name, card_type, card_text FROM Cards",
        )
        all_cards = cursor.fetchall()

        # Perform fuzzy search and order results by score.
        matching_cards = []
        for card in all_cards:
            score = fuzz.partial_ratio(search_term, card[3].lower()) # Calculate score using Levenshtein distance
            if score > 50:
                matching_cards.append((score, card))

        matching_cards.sort(reverse=True, key=lambda x: x[0]) # Sort list by score.

        if not matching_cards:
            await interaction.response.send_message("No cards found matching your search term.", ephemeral=True)
            return

        # Limit results to 20
        matching_cards = matching_cards[:20]

        # Format and send the results.
        results = "```\n"
        for score, card in matching_cards:
            results += f"ID: {card[0]}, Pack: {card[1]}, Type: {card[2]}, Text: {card[3]} (Score: {score})\n"
        results += "```"

        if len(results) > 2000:  # Check for Discord's message length limit
            await interaction.response.send_message(
                "Too many results. Please refine your search term.", ephemeral=True
            )
            return

        await interaction.response.send_message(results, ephemeral=True)

    except sqlite3.Error as e:
        conn.rollback()
        await interaction.response.send_message(f"Database error: {e}", ephemeral=True)


@bot.tree.command(name="listpacks", description="List available card packs from the API")
async def list_packs(interaction: discord.Interaction):
    try:
        query = """
            query {
              packs {
                name
              }
            }
        """
        response = graphql_query(query)
        api_packs = [pack['name'] for pack in response.json()['data']['packs']]
        await interaction.response.send_message("Available packs from API: " + ", ".join(api_packs))
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing packs: {e}")
        await interaction.response.send_message("Could not retrieve card packs from API.", ephemeral=True)


@bot.tree.command(name="filterpacks", description="Filter packs (admin only)")
@commands.has_permissions(administrator=True)
async def filter_packs(interaction: discord.Interaction, pack_name: str, enable: bool):
    global decks
    try:
        # If filtering ALL, manage both API packs and database packs.
        if pack_name.lower() == 'all':
            query = """
                query {
                  packs {
                    name
                  }
                }
            """
            response = graphql_query(query)
            api_packs = [pack['name'] for pack in response.json()['data']['packs']]

            for pack in api_packs:
                decks[pack] = {'enabled': enable}
            cursor.execute("UPDATE Cards SET enabled = ?", (enable,)) # Update local database
            conn.commit()
            await interaction.response.send_message(f"All packs {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)
            return  # Exit early

        # Filter specific pack. Check if it exists in decks or database.
        if pack_name in decks:
            decks[pack_name]['enabled'] = enable
        cursor.execute("UPDATE Cards SET enabled = ? WHERE pack_name = ?", (enable, pack_name)) # Update local database
        conn.commit()

        await interaction.response.send_message(f"Pack '{pack_name}' {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)

    except requests.exceptions.RequestException as e:  # Handle API request errors
        logger.error(f"Error during API request in filterpacks: {e}")
        await interaction.response.send_message("Could not retrieve card packs from API.", ephemeral=True)

    except sqlite3.Error as e:  # Handle database errors
        conn.rollback()  # Rollback changes if error occurs
        logger.error(f"Database error in filterpacks: {e}")
        await interaction.response.send_message("A database error occurred.", ephemeral=True)


@bot.tree.command(name="resetgame", description="Reset the game (admin only)")
@commands.has_permissions(administrator=True)
async def reset_game(interaction: discord.Interaction):
    global game_active, card_czar, black_card, submitted_cards, players, timer
    try:
        game_active = False
        card_czar = None
        black_card = None
        submitted_cards = {}
        players = {}
        timer = 10
        await interaction.response.send_message("Game reset successfully!", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"Error resetting game: {e}", ephemeral=True)


@bot.tree.command(name="end", description="End the game (admin only)")
@commands.has_permissions(administrator=True)
async def end_game(interaction: discord.Interaction):
    global game_active
    game_active = False
    await interaction.response.send_message("Game ended.", ephemeral=True)


@bot.event
async def on_command_error(interaction: discord.Interaction, error):
    if isinstance(error, commands.CommandNotFound):
        await interaction.response.send_message("Command not found. Use `/help` for a list of commands.", ephemeral=True)
    elif isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, commands.MissingRequiredArgument):
        await interaction.response.send_message(str(error), ephemeral=True) # More informative message for missing arguments
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
