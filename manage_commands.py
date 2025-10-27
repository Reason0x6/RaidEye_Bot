"""
Command Management Utility

This script helps you manage Discord slash commands:
- Clear all commands (global and guild-specific)
- List current commands
- Re-sync commands
"""

import discord
from discord.ext import commands
import asyncio
import os
import sys
from pathlib import Path

# NOTE: This script can load a .properties file (bots/*.properties) passed as the
# first command-line argument. The properties file will be loaded and exported as
# environment variables so the rest of the script (and the main bot) will pick
# up the same configuration keys.


def load_properties_config(path: str) -> dict:
    """Load simple key=value .properties file and return dict of values.

    Lines beginning with # or empty lines are ignored. Values are set into
    os.environ by the caller.
    """
    config = {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Properties file not found: {path}")

    with p.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


def apply_properties_to_env(path: str):
    data = load_properties_config(path)
    for k, v in data.items():
        # Only set if not already present to avoid clobbering env intentionally set
        os.environ[k] = v

class CommandManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    async def setup_hook(self):
        print("Command Manager ready!")

async def clear_commands():
    """Clear all slash commands"""
    bot = CommandManager()
    
    try:
        # Get token from environment (support both DISCORD_BOT_TOKEN and DISCORD_TOKEN keys)
        token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
        if not token:
            print("❌ DISCORD_BOT_TOKEN or DISCORD_TOKEN not set in environment. Provide a properties file or set env vars.")
            return
        await bot.login(token)
        print("🤖 Connected to Discord!")
        
        # Clear guild-specific commands if GUILD_ID is set
        gid = int(os.getenv('GUILD_ID', '0'))
        if gid:
            print(f"\n📋 Clearing commands for guild {gid}...")
            guild = discord.Object(id=gid)
            bot.tree.clear_commands(guild=guild)
            guild_synced = await bot.tree.sync(guild=guild)
            print(f"✅ Cleared guild commands. Remaining: {len(guild_synced)}")
        
        # Clear global commands
        print("\n📋 Clearing global commands...")
        bot.tree.clear_commands(guild=None)
        global_synced = await bot.tree.sync()
        print(f"✅ Cleared global commands. Remaining: {len(global_synced)}")
        
        print("\n🎉 All commands cleared successfully!")
        print("ℹ️  Note: It may take a few minutes for changes to appear in Discord")
        
    except discord.LoginFailure:
        print("❌ Invalid bot token!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.close()

async def list_commands():
    """List all current slash commands"""
    bot = CommandManager()
    
    try:
        token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
        if not token:
            print("❌ DISCORD_BOT_TOKEN or DISCORD_TOKEN not set in environment. Provide a properties file or set env vars.")
            return
        await bot.login(token)
        print("🤖 Connected to Discord!")
        
        # Get global commands
        print("\n🌍 Global Commands:")
        global_commands = await bot.tree.fetch_commands()
        if global_commands:
            for cmd in global_commands:
                print(f"  • /{cmd.name} - {cmd.description}")
        else:
            print("  No global commands found")
        
        # Get guild-specific commands if GUILD_ID is set
        gid = int(os.getenv('GUILD_ID', '0'))
        if gid:
            print(f"\n🏰 Guild Commands ({gid}):")
            guild = discord.Object(id=gid)
            guild_commands = await bot.tree.fetch_commands(guild=guild)
            if guild_commands:
                for cmd in guild_commands:
                    print(f"  • /{cmd.name} - {cmd.description}")
            else:
                print("  No guild commands found")
        
    except discord.LoginFailure:
        print("❌ Invalid bot token!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.close()

async def resync_commands():
    """Re-sync commands from the bot"""
    print("🔄 Re-syncing commands...")
    print("This will load commands from your bot files and sync them to Discord")
    
    # Import and load the main bot
    try:
        from bot import RaidEyeBot
        # Ensure token is present
        token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
        if not token:
            print("❌ DISCORD_BOT_TOKEN or DISCORD_TOKEN not set in environment. Provide a properties file or set env vars.")
            return
        bot = RaidEyeBot()
        await bot.start(token)
    except Exception as e:
        print(f"❌ Error starting bot for resync: {e}")

def main():
    """Main menu for command management"""
    # If a properties file path is passed as the first CLI arg, apply it to env
    if len(sys.argv) > 1:
        props_path = sys.argv[1]
        try:
            apply_properties_to_env(props_path)
            print(f"Loaded properties from: {props_path}")
        except Exception as e:
            print(f"❌ Failed to load properties file '{props_path}': {e}")

    print("🔧 Discord Bot Command Manager")
    print("=" * 40)
    print("1. List current commands")
    print("2. Clear all commands (removes old/unwanted commands)")
    print("3. Re-sync commands (loads from bot files)")
    print("4. Exit")
    
    while True:
        choice = input("\nSelect an option (1-4): ").strip()
        
        if choice == "1":
            print("\n📋 Listing current commands...")
            asyncio.run(list_commands())
            
        elif choice == "2":
            confirm = input("\n⚠️  This will remove ALL slash commands. Continue? (y/N): ").strip().lower()
            if confirm == 'y':
                asyncio.run(clear_commands())
            else:
                print("❌ Operation cancelled")
                
        elif choice == "3":
            print("\n🔄 Re-syncing commands...")
            asyncio.run(resync_commands())
            
        elif choice == "4":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    main()