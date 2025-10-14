import discord
from discord.ext import commands
import asyncio


import os
import sys
from pathlib import Path
import configparser

# Read config from .properties file passed as first argument
def load_properties_config(path):
    config = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config

if len(sys.argv) > 1:
    config_path = sys.argv[1]
    config = load_properties_config(config_path)
    # Set all config values as environment variables for downstream code
    for k, v in config.items():
        os.environ[k] = v
else:
    print("No .properties config file provided! Exiting.")
    sys.exit(1)

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_TOKEN')
BOT_PREFIX = os.environ.get('BOT_PREFIX', '!')
GUILD_ID = int(os.environ.get('GUILD_ID', 0))
MAIN_CHANNEL_ID = int(os.environ.get('MAIN_CHANNEL_ID', 0))
RAIDEYE_SERVER = os.environ.get('RAIDEYE_SERVER', 'http://127.0.0.1:8000')

# Bot configuration
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.members = True

class RaidEyeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=BOT_PREFIX,  # Use prefix from config
            intents=INTENTS,
            help_command=None  # Disable default help command
        )
        self.guild_id = GUILD_ID
        self.main_channel_id = MAIN_CHANNEL_ID
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        print("Setting up bot...")
        
        # Load all command cogs from the commands directory
        await self.load_commands()
        
        # Sync slash commands with Discord
        try:
            # Try guild-specific sync first (faster for testing)
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
            else:
                # Fallback to global sync
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} command(s) globally")
        except discord.Forbidden:
            print("❌ Bot doesn't have permission to sync commands!")
            print("Make sure the bot was invited with 'applications.commands' scope")
        except discord.HTTPException as e:
            print(f"❌ HTTP error during sync: {e}")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
            print("Commands will still work, but may take up to 1 hour to appear")
    
    async def load_commands(self):
        """Load all command cogs from the commands directory"""
        commands_dir = Path("commands")
        if not commands_dir.exists():
            commands_dir.mkdir()
            print(f"Created {commands_dir} directory")
            return
        
        # Load all Python files in the commands directory as cogs
        for file in commands_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue  # Skip private files
                
            cog_name = f"commands.{file.stem}"
            try:
                await self.load_extension(cog_name)
                print(f"Loaded command: {file.stem}")
            except Exception as e:
                print(f"Failed to load {file.stem}: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        print(f"{self.user} has connected to Discord!")
        print(f"Bot is in {len(self.guilds)} guilds")
        
        # Check if bot is in the configured guild
        target_guild = self.get_guild(GUILD_ID)
        if target_guild:
            print(f"✅ Connected to configured server: {target_guild.name}")
            main_channel = self.get_channel(MAIN_CHANNEL_ID)
            if main_channel:
                print(f"✅ Found main channel: #{main_channel.name}")
            else:
                print(f"⚠️ Main channel not found (ID: {MAIN_CHANNEL_ID})")
        else:
            print(f"⚠️ Bot is not in the configured server (ID: {GUILD_ID})")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for raids | /info"
            )
        )
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        print(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")
    
    @commands.command(name='sync')
    @commands.is_owner()
    async def sync_commands(self, ctx):
        """Manually sync slash commands (bot owner only)"""
        try:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                await ctx.send(f"✅ Synced {len(synced)} commands to this guild!")
            else:
                synced = await self.tree.sync()
                await ctx.send(f"✅ Synced {len(synced)} commands globally!")
        except Exception as e:
            await ctx.send(f"❌ Failed to sync: {e}")
    
    @commands.command(name='clear')
    @commands.is_owner()
    async def clear_commands(self, ctx):
        """Clear all slash commands (bot owner only)"""
        try:
            # Clear guild commands
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.clear_commands(guild=guild)
                synced = await self.tree.sync(guild=guild)
                await ctx.send(f"✅ Cleared guild commands! Remaining: {len(synced)}")
            
            # Clear global commands
            self.tree.clear_commands(guild=None)
            global_synced = await self.tree.sync()
            await ctx.send(f"✅ Cleared global commands! Remaining: {len(global_synced)}")
            
        except Exception as e:
            await ctx.send(f"❌ Failed to clear commands: {e}")
    
    @commands.command(name='list')
    @commands.is_owner()
    async def list_commands(self, ctx):
        """List all current slash commands (bot owner only)"""
        try:
            embed = discord.Embed(
                title="📋 Current Slash Commands",
                color=discord.Color.blue()
            )
            
            # Guild commands
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                guild_commands = await self.tree.fetch_commands(guild=guild)
                if guild_commands:
                    guild_list = "\n".join([f"• /{cmd.name}" for cmd in guild_commands])
                    embed.add_field(
                        name=f"🏰 Guild Commands ({len(guild_commands)})",
                        value=guild_list,
                        inline=False
                    )
            
            # Global commands
            global_commands = await self.tree.fetch_commands()
            if global_commands:
                global_list = "\n".join([f"• /{cmd.name}" for cmd in global_commands])
                embed.add_field(
                    name=f"🌍 Global Commands ({len(global_commands)})",
                    value=global_list,
                    inline=False
                )
            
            if not guild_commands and not global_commands:
                embed.description = "No slash commands found"
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to list commands: {e}")

async def main():
    """Main function to run the bot"""
    bot = RaidEyeBot()
    
    # Get bot token from config (which loads from environment/env file)
    token = DISCORD_BOT_TOKEN
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        print("Please set your Discord bot token in the .env file or as an environment variable.")
        print("Example: DISCORD_BOT_TOKEN=your_token_here")
        return
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        print("Invalid bot token provided!")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())