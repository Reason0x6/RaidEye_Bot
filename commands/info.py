import discord
from discord.ext import commands
from discord import app_commands

class InfoCommands(commands.Cog):
    """Information commands for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="info", description="Get information about the bot")
    async def info(self, interaction: discord.Interaction):
        """Display bot information"""
        
        embed = discord.Embed(
            title="🤖 RaidEye Bot Info",
            description="A Discord bot focused on raid management and clan activities",
            color=discord.Color.blue()
        )
        
        # Bot stats
        embed.add_field(
            name="📊 Stats",
            value=f"🏰 Servers: {len(self.bot.guilds)}\n"
                  f"👥 Users: {len(self.bot.users)}\n"
                  f"📡 Latency: {round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        # Bot version and info
        embed.add_field(
            name="ℹ️ Details",
            value=f"🔧 Version: 1.0.0\n"
                  f"🐍 Discord.py: {discord.__version__}\n"
                  f"🏷️ Bot ID: {self.bot.user.id}",
            inline=True
        )
        
        # Commands info
        embed.add_field(
            name="⚡ Commands",
            value="Use `/` to see all available slash commands!\n"
                  "This bot is designed for easy command expansion.",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="RaidEye Bot | Made with ❤️")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ping", description="Check the bot's response time")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="help", description="Get help with bot commands")
    async def help(self, interaction: discord.Interaction):
        """Display help information"""
        
        embed = discord.Embed(
            title="📚 Help - Available Commands",
            description="Here are all the available slash commands:",
            color=discord.Color.purple()
        )
        
        # Get all slash commands
        commands_list = []
        for command in self.bot.tree.get_commands():
            commands_list.append(f"**/{command.name}** - {command.description}")
        
        if commands_list:
            embed.add_field(
                name="⚡ Slash Commands",
                value="\n".join(commands_list),
                inline=False
            )
        
        embed.add_field(
            name="💡 Tips",
            value="• Type `/` in chat to see all commands with auto-complete\n"
                  "• Commands are organized by categories for easy management\n"
                  "• New commands can be easily added to extend functionality",
            inline=False
        )
        
        embed.set_footer(text="Need more help? Contact the bot developer!")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    """Setup function called by discord.py when loading this cog"""
    await bot.add_cog(InfoCommands(bot))