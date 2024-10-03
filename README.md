# Cards Against Discord

A Discord bot that brings the fun and irreverent card game Cards Against Humanity to your server.  Get ready for some hilarious and potentially offensive combinations!

## Features

* **Core Gameplay:** Play a full game of Cards Against Humanity directly within Discord.
* **Card Database:**  Fetches cards from the public Rest Against Humanity API ([https://restagainsthumanity.com/api/graphql](https://restagainsthumanity.com/api/graphql)).
* **Player Management:**  Players can join, leave, and be automatically assigned as the Card Czar.
* **Game Flow:**  Automated round management, card dealing, submissions, and winner selection.
* **Admin Commands:** Control game settings, add custom cards, and manage the game.
* **Error Handling:** Robust error handling to gracefully handle disconnects and other issues.
* **Player Stats:** Track player wins and win rates.
* **Emoji Voting:** Vote on winning card combinations using emojis.
* **"Best of" Posts:** Weekly and monthly highlights of the funniest combinations.

## Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/cards-against-discord.git  # Replace with your repository URL
   ```

2. **Install Dependencies:** Create and activate a virtual environment (recommended):
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
    ```
    Then install the required libraries:
    ```bash
    pip install -r requirements.txt
    ```

3. **Create a Discord Bot:**
    * Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
    * In your application settings, navigate to the "Bot" tab and create a new bot.
    * Add the bot to your Discord server using the OAuth2 URL generator, ensuring the `applications.commands` scope is selected.

4. **Bot Token:**
    * Create a `.env` file in the root directory of the project.
    * Inside `.env`, add your bot token:
      ```
      DISCORD_BOT_TOKEN="your_actual_bot_token"
      ```

5. **Database Setup:**
   The bot will automatically create the necessary database file (`cah_bot.db`) upon first run.

6. **Run the Bot:**
   ```bash
   python cah_bot.py
   ```

## Usage

* `/join`: Join the game.
* `/start`: Start a new game (admin only).
* `/end`: End the current game (admin only).
* `/stats [username]`: View player statistics.  Omit username to see your own stats.
* `/set-timer <seconds>`: Set the timer for between-round waiting (admin only).
* `/add-cards`: Add new cards (admin only).  (Implementation details for this will be added later).
* `/remove-cards`: Remove cards (admin only). (Implementation details for this will be added later).
* `/filter-packs`: Filter card packs (admin only).  (Implementation details for this will be added later).

## Contributing

Contributions are welcome! Feel free to open issues and pull requests.

## License

This project is licensed under the [MIT License](LICENSE).
