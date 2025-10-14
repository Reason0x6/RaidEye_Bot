"""
Bot configuration settings
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
BOT_PREFIX = os.environ.get("BOT_PREFIX", "!")
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

# Server and Channel Configuration
GUILD_ID = int(os.getenv('GUILD_ID', 710875600637788170))  # Your Discord server ID
MAIN_CHANNEL_ID = int(os.environ.get("MAIN_CHANNEL_ID", 0))
RAIDEYE_SERVER = os.environ.get("RAIDEYE_SERVER", "http://127.0.0.1:8000")

# Additional configuration options
BOT_NAME = "RaidEye Bot"
BOT_VERSION = "1.0.0"
BOT_DESCRIPTION = "A Discord bot focused on raid management and clan activities"

# You can add more channel IDs as needed
CHANNELS = {
    'main': MAIN_CHANNEL_ID,
    # 'announcements': 123456789012345678,  # Add more channels as needed
    # 'raids': 123456789012345679,
    # 'general': 123456789012345680,
}

# Bot permissions required
REQUIRED_PERMISSIONS = [
    'send_messages',
    'use_slash_commands',
    'embed_links',
    'read_message_history',
    'add_reactions'
]