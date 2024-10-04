import sqlite3
import logging

# Configure logging (at the top of main.py)
logger = logging.getLogger(__name__) # Create a logger specific to this module.
logger.setLevel(logging.ERROR) # Log errors and above.
handler = logging.FileHandler(filename='database.log', encoding='utf-8', mode='w') # Log to a file named 'game_logic.log'.
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')) # Format the log messages.
logger.addHandler(handler) # Add the handler to the logger.

DATABASE_NAME = "cards_against_humanity.db"
DEFAULT_HAND_SIZE = 10

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()


def setup_database():
    # Create Cards table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_name TEXT,
            card_type TEXT,
            card_text TEXT,
            enabled BOOLEAN DEFAULT TRUE
        )
        """
    )
    # Create Players table
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
    # Create WinningCards table
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


def fetch_cards_from_db(card_type, pack_name=None, enabled_only=True):
    query = "SELECT card_text FROM Cards WHERE card_type = ?"
    params = [card_type]

    if pack_name:
        query += " AND pack_name = ?"
        params.append(pack_name)

    if enabled_only:
        query += " AND enabled = TRUE"

    cursor.execute(query, params)
    return cursor.fetchall()
