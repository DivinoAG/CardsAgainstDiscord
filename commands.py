import sqlite3
from discord.ext import commands
from main import bot, game_active, players, timer, decks, API_URL
from game_logic import add_player, start_round, deal_cards, end_round, between_rounds, fetch_cards
from database import conn, cursor
import requests
import logging


# Configure logging
logger = logging.getLogger(__name__) # Create a logger specific to this module.
logger.setLevel(logging.ERROR) # Log errors and above.
handler = logging.FileHandler(filename='commands.log', encoding='utf-8', mode='w') # Log to a file named 'game_logic.log'.
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')) # Format the log messages.
logger.addHandler(handler) # Add the handler to the logger.


@bot.slash_command(name="join", description="Join the Cards Against Humanity game")
async def join(ctx):
    try:
        await add_player(ctx, ctx.author)
    except Exception as e:
        await ctx.respond(f"An error occurred joining the game: {e}", ephemeral=True)


@bot.slash_command(name="settimer", description="Set the between-rounds timer (in seconds)")
@commands.has_permissions(administrator=True)  # Restrict to admins
async def settimer(ctx, seconds: int):
    global timer
    try:
        seconds = int(seconds)  # Convert to integer
        if 10 <= seconds <= 60:  # Enforce reasonable limits
            timer = seconds
            await ctx.respond(f"Timer set to {seconds} seconds.", ephemeral=True)
        else:
            await ctx.respond("Timer must be between 10 and 60 seconds.", ephemeral=True)
    except ValueError: # Handle error if input isn't a number
        await ctx.respond("Invalid input. Please enter a number.", ephemeral=True)

@bot.slash_command(name="start", description="Start the game (admin only)")
@commands.has_permissions(administrator=True)
async def start_game(ctx):
    global game_active
    game_active = True
    await start_round(ctx)


@bot.slash_command(name="addcards", description="Add cards (admin only)")
@commands.has_permissions(administrator=True)
async def add_cards(ctx, pack_name: str, card_type: str, card_text: str):
    if card_type.lower() not in ("black", "white"):  # Validate card_type
        await ctx.respond("Invalid card type. Must be 'black' or 'white'.", ephemeral=True)
        return

    try:
        cursor.execute(
            "INSERT INTO Cards (pack_name, card_type, card_text) VALUES (?, ?, ?)",
            (pack_name, card_type.lower(), card_text),  # Ensure card_type is lowercase
        )
        conn.commit()
        await ctx.respond(f"Card '{card_text}' added to pack '{pack_name}' successfully!", ephemeral=True)  # More informative message
    except sqlite3.IntegrityError as e:  # Specific error for integrity violations (duplicates, etc.)
        conn.rollback()
        await ctx.respond(f"Error adding card: {e}", ephemeral=True)  # More specific error message if possible
    except sqlite3.Error as e:  # Catch other SQLite errors
        conn.rollback()
        await ctx.respond(f"Database error: {e}", ephemeral=True)


@bot.slash_command(name="removecards", description="Remove cards (admin only)")
@commands.has_permissions(administrator=True)
async def remove_cards(ctx, card_id: int):
    try:
        cursor.execute("SELECT card_text FROM Cards WHERE card_id = ?", (card_id,)) # Fetch the card text before deleting (New)
        deleted_card = cursor.fetchone() # Fetch the card that was deleted (New)

        cursor.execute("DELETE FROM Cards WHERE card_id = ?", (card_id,))
        if cursor.rowcount == 0:  # Check if any rows were affected, i.e. a card was deleted. (New)
            await ctx.respond("Card not found.", ephemeral=True) # (New)
            return  # Exit early if no card was found

        conn.commit()
        await ctx.respond(f"Card '{deleted_card[0]}' removed successfully!", ephemeral=True)  # Include the removed card in the message  (NEW) # More informative message

    except sqlite3.Error as e:  # Catch SQLite errors
        conn.rollback()
        await ctx.respond(f"Database error: {e}", ephemeral=True)


@bot.slash_command(name="listpacks", description="List available card packs from the API")
async def list_packs(ctx):
    try:
        query = """
            query {
              packs {
                name
              }
            }
        """
        response = requests.post(API_URL, json={"query": query})
        response.raise_for_status()
        api_packs = [pack['name'] for pack in response.json()['data']['packs']]
        await ctx.respond("Available packs from API: " + ", ".join(api_packs))
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing packs: {e}")
        await ctx.respond("Could not retrieve card packs from API.", ephemeral=True)


@bot.slash_command(name="filterpacks", description="Filter packs (admin only)")
@commands.has_permissions(administrator=True)
async def filter_packs(ctx, pack_name: str, enable: bool):
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
            response = requests.post(API_URL, json={"query": query})  # Fetch API packs
            response.raise_for_status()
            api_packs = [pack['name'] for pack in response.json()['data']['packs']]

            for pack in api_packs:
                decks[pack] = {'enabled': enable}
            cursor.execute("UPDATE Cards SET enabled = ?", (enable,)) # Update local database
            conn.commit()
            await ctx.respond(f"All packs {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)
            return  # Exit early

        # Filter specific pack. Check if it exists in decks or database.
        if pack_name in decks:
            decks[pack_name]['enabled'] = enable
        cursor.execute("UPDATE Cards SET enabled = ? WHERE pack_name = ?", (enable, pack_name)) # Update local database
        conn.commit()

        await ctx.respond(f"Pack '{pack_name}' {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)

    except requests.exceptions.RequestException as e:  # Handle API request errors
        logger.error(f"Error during API request in filterpacks: {e}")
        await ctx.respond("Could not retrieve card packs from API.", ephemeral=True)

    except sqlite3.Error as e:  # Handle database errors
        conn.rollback()  # Rollback changes if error occurs
        logger.error(f"Database error in filterpacks: {e}")
        await ctx.respond("A database error occurred.", ephemeral=True)


@bot.slash_command(name="resetgame", description="Reset the game (admin only)")
@commands.has_permissions(administrator=True)
async def reset_game(ctx):
    global game_active, card_czar, black_card, submitted_cards, players, timer
    try:
        game_active = False
        card_czar = None
        black_card = None
        submitted_cards = {}
        players = {}
        timer = 10
        await ctx.respond("Game reset successfully!", ephemeral=True)

    except Exception as e:
        await ctx.respond(f"Error resetting game: {e}", ephemeral=True)


@bot.slash_command(name="end", description="End the game (admin only)")
@commands.has_permissions(administrator=True)
async def end_game(ctx):
    global game_active
    game_active = False
    await ctx.respond("Game ended.", ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.respond("Command not found. Use `/help` for a list of commands.", ephemeral=True)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.respond("You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.respond(str(error), ephemeral=True) # More informative message for missing arguments
    else:
        print(f"An error occurred: {error}")
        await ctx.respond("An unexpected error occurred.", ephemeral=True)
