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
from config import DISCORD_BOT_TOKEN, GUILD_ID

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
        await bot.login(DISCORD_BOT_TOKEN)
        print("🤖 Connected to Discord!")
        
        # Clear guild-specific commands if GUILD_ID is set
        if GUILD_ID:
            print(f"\n📋 Clearing commands for guild {GUILD_ID}...")
            guild = discord.Object(id=GUILD_ID)
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
        await bot.login(DISCORD_BOT_TOKEN)
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
        if GUILD_ID:
            print(f"\n🏰 Guild Commands ({GUILD_ID}):")
            guild = discord.Object(id=GUILD_ID)
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
        bot = RaidEyeBot()
        await bot.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"❌ Error starting bot for resync: {e}")

def main():
    """Main menu for command management"""
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