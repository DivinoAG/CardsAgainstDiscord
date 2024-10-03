import sqlite3
from discord.ext import commands
from main import bot, game_active, players, timer, decks
from game_logic import add_player, start_round, deal_cards, end_round, between_rounds, fetch_cards
from database import conn, cursor


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
    if card_type.lower() not in ("black", "white"):
        await ctx.respond("Invalid card type. Must be 'black' or 'white'.", ephemeral=True)
        return

    try:
        # The try-except block is simplified, IntegrityError is already handled by the database.
        cursor.execute(
            "INSERT INTO Cards (pack_name, card_type, card_text) VALUES (?, ?, ?)",
            (pack_name, card_type, card_text),
        )
        conn.commit()
        await ctx.respond("Card added successfully!", ephemeral=True)
    except sqlite3.Error as e:  # Catches any database related error.
        conn.rollback()
        await ctx.respond(f"Database error: {e}", ephemeral=True)
    try:
        cursor.execute(
            "INSERT INTO Cards (pack_name, card_type, card_text) VALUES (?, ?, ?)",
            (pack_name, card_type, card_text),
        )
        conn.commit()
        await ctx.respond("Card added successfully!", ephemeral=True)
    except sqlite3.IntegrityError as e:  # Catch IntegrityError (duplicate card_id, etc.) (New)
        conn.rollback() # Rollback changes on error
        await ctx.respond(f"Error adding card: {e}", ephemeral=True) # Send a specific error message
    except sqlite3.Error as e:  # Catch other SQLite errors
        conn.rollback() # Rollback changes on error
        await ctx.respond(f"Database error: {e}", ephemeral=True)


@bot.slash_command(name="removecards", description="Remove cards (admin only)")
@commands.has_permissions(administrator=True)
async def remove_cards(ctx, card_id: int):
    try:
        cursor.execute("DELETE FROM Cards WHERE card_id = ?", (card_id,))
        conn.commit()
        await ctx.respond("Card removed successfully!", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"Error removing card: {e}", ephemeral=True)


@bot.slash_command(name="filterpacks", description="Filter packs (admin only)")
@commands.has_permissions(administrator=True)
async def filter_packs(ctx, pack_name: str, enable: bool):
    global decks

    if not decks: # Check for empty deck (New)
        await ctx.respond("No card packs available to filter.", ephemeral=True) # New
        return # New

    try:
        if pack_name.lower() == 'all': # new: filter ALL packs
            for pack_name in decks:
                decks[pack_name]['enabled'] = enable
            cursor.execute("UPDATE Cards SET enabled = ? ", (enable,))
            conn.commit()
            await ctx.respond(f"All packs {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)

        elif pack_name in decks: # Check if the pack exists before trying to filter
            decks[pack_name]['enabled'] = enable
            cursor.execute("UPDATE Cards SET enabled = ? WHERE pack_name = ?", (enable, pack_name))
            conn.commit()
            await ctx.respond(f"Pack '{pack_name}' {'enabled' if enable else 'disabled'} successfully!", ephemeral=True)

        else: # new
            await ctx.respond(f"Pack '{pack_name}' not found.", ephemeral=True)

    except Exception as e:
        await ctx.respond(f"Error filtering pack: {e}", ephemeral=True)


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
