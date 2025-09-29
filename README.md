# RaidEye Discord Bot

A modular Discord bot built with discord.py that focuses on raid management and clan activities. The bot is designed with extensibility in mind, making it easy to add new slash commands.

## Features

- **Slash Commands**: Modern Discord slash command support
- **Modular Design**: Easy to add new commands by creating new files
- **Clan Management**: Built-in clan information and management commands
- **Raid Scheduling**: Track and display raid schedules
- **Auto-sync**: Automatically syncs commands with Discord on startup

## Setup

### Prerequisites

- Python 3.8 or higher
- A Discord application and bot token

### Installation

1. **Clone or download this project**

2. **Create a virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Set up your Discord bot**:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to the "Bot" section and create a bot
   - Copy the bot token

5. **Configure environment variables**:
   ```powershell
   # Set your bot token as an environment variable
   $env:DISCORD_BOT_TOKEN="your_bot_token_here"
   ```

6. **Invite your bot to a server**:
   - In the Discord Developer Portal, go to OAuth2 > URL Generator
   - Select "bot" and "applications.commands" scopes
   - Select necessary permissions (Send Messages, Use Slash Commands, etc.)
   - Use the generated URL to invite your bot

7. **Run the bot**:
   ```powershell
   python bot.py
   ```

## Available Commands

- `/info` - Get information about the bot
- `/ping` - Check the bot's response time
- `/help` - Get help with bot commands
- `/clan-info <clan_name>` - Get information about a specific clan
- `/clan-list` - List all clans in the database
- `/raid-schedule` - Check the current raid schedule

## Adding New Commands

The bot is designed for easy extensibility. To add new commands:

1. **Create a new file** in the `commands/` directory (e.g., `commands/new_feature.py`)

2. **Use this template**:
   ```python
   import discord
   from discord.ext import commands
   from discord import app_commands

   class NewFeatureCommands(commands.Cog):
       """Description of your command group"""
       
       def __init__(self, bot):
           self.bot = bot
       
       @app_commands.command(name="your-command", description="What your command does")
       async def your_command(self, interaction: discord.Interaction):
           """Your command function"""
           await interaction.response.send_message("Hello from your new command!")

   async def setup(bot):
       """Setup function - required for all command files"""
       await bot.add_cog(NewFeatureCommands(bot))
   ```

3. **Restart the bot** - The bot will automatically load your new commands on startup

## Project Structure

```
RaidEye_Discord_bot/
├── bot.py                 # Main bot file
├── commands/              # Command modules directory
│   ├── info.py           # Information commands (/info, /ping, /help)
│   └── clan.py           # Clan management commands
├── clans.json            # Clan data storage
├── discord_db.py         # Database utilities (if needed)
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Command Categories

### Information Commands (`commands/info.py`)
- General bot information
- Help system
- Ping/latency checking

### Clan Commands (`commands/clan.py`)
- Clan information display
- Clan listing
- Raid schedule display

## Configuration

The bot uses environment variables for configuration:

- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)
- `BOT_PREFIX` - Prefix for text commands (default: `!`)
- `DEBUG_MODE` - Enable debug logging (default: `False`)

## Data Storage

- `clans.json` - Stores clan information and member data
- Additional data files can be added as needed

## Contributing

To add new features:

1. Create new command files in the `commands/` directory
2. Follow the existing code structure and patterns
3. Use Discord embeds for rich message formatting
4. Include proper error handling
5. Add command descriptions for the help system

## Troubleshooting

### Bot not responding to slash commands
- Make sure the bot has been invited with the `applications.commands` scope
- Check that commands are syncing properly (look for sync messages in console)
- Ensure the bot has necessary permissions in your server

### Environment variable issues
- Make sure `DISCORD_BOT_TOKEN` is set before running the bot
- On Windows PowerShell, use: `$env:DISCORD_BOT_TOKEN="your_token"`

### Command not loading
- Check the console for error messages during startup
- Ensure your command file has the proper `setup()` function
- Verify the command file doesn't start with an underscore

## License

This project is open source and available under the MIT License.