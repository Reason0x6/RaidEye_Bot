"""
Simple Command Cleaner

This script clears all Discord slash commands for your bot.
"""

import discord
import asyncio
from config import DISCORD_BOT_TOKEN, GUILD_ID

async def clear_all_commands():
    """Clear all slash commands"""
    
    # Create a simple bot instance just for clearing commands
    intents = discord.Intents.default()
    bot = discord.Client(intents=intents)
    
    try:
        print("🤖 Connecting to Discord...")
        await bot.login(DISCORD_BOT_TOKEN)
        
        # Create application command tree
        tree = discord.app_commands.CommandTree(bot)
        
        print("📋 Clearing commands...")
        
        # Clear guild commands if GUILD_ID is set
        if GUILD_ID:
            print(f"Clearing guild commands for {GUILD_ID}...")
            guild = discord.Object(id=GUILD_ID)
            tree.clear_commands(guild=guild)
            guild_synced = await tree.sync(guild=guild)
            print(f"✅ Guild commands cleared. Remaining: {len(guild_synced)}")
        
        # Clear global commands
        print("Clearing global commands...")
        tree.clear_commands(guild=None)
        global_synced = await tree.sync(guild=None)
        print(f"✅ Global commands cleared. Remaining: {len(global_synced)}")
        
        print("\n🎉 All commands have been cleared!")
        print("💡 You can now restart your bot to register fresh commands.")
        
    except discord.LoginFailure:
        print("❌ Invalid bot token!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    print("🧹 Discord Command Cleaner")
    print("=" * 30)
    
    confirm = input("⚠️  This will clear ALL slash commands. Continue? (y/N): ").strip().lower()
    
    if confirm == 'y':
        asyncio.run(clear_all_commands())
    else:
        print("❌ Operation cancelled")