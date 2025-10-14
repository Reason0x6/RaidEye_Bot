import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import io
import logging
from typing import Optional, Literal
from config import GUILD_ID, MAIN_CHANNEL_ID

class ClanStatsCommands(commands.Cog):
    """Clan statistics and information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None
        self.server_url = os.getenv('RAIDEYE_SERVER', '127.0.0.1:8000')
        if not self.server_url.startswith('http'):
            self.server_url = f'http://{self.server_url}'
        self.api_url = f"{self.server_url}/api/discord"
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        self.aiohttp_session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.aiohttp_session:
            await self.aiohttp_session.close()
    
    # @app_commands.command(name="clan-stats", description="Get detailed clan statistics")
    # async def clan_stats(
    #     self, 
    #     interaction: discord.Interaction, 
    #     include_image: bool = False,
    #     message_link: Optional[str] = None
    # ):
    #     """Fetch and display clan statistics"""
    #     await interaction.response.defer(thinking=True)
        
    #     try:
    #         # Fetch clan stats from server
    #         stats_url = f"{self.api_url}/clans/stats/msg"
            
    #         async with self.aiohttp_session.get(stats_url) as resp:
    #             text = await resp.text()
                
    #             if 200 <= resp.status < 300:
    #                 # Parse response
    #                 try:
    #                     data = json.loads(text)
    #                     message_text = data.get("message", str(data)) if isinstance(data, dict) else str(data)
    #                 except:
    #                     message_text = text
                    
                    
    #                 # Create embed for better formatting
    #                 embed = discord.Embed(
    #                     title="📊 Clan Statistics",
    #                     description=message_text,
    #                     color=discord.Color.blue()
    #                 )
                    
    #                 embed.set_footer(text="Data retrieved from RaidEye server")
    #                 embed.timestamp = discord.utils.utcnow()
                    
                    
    #                 await interaction.followup.send(embed=embed)
                
    #             else:
    #                 # Error response
    #                 error_embed = discord.Embed(
    #                     title="❌ Failed to Fetch Clan Stats",
    #                     description=f"Server returned status {resp.status}",
    #                     color=discord.Color.red()
    #                 )
                    
    #                 if len(text) <= 1000:
    #                     error_embed.add_field(name="Error Details", value=f"```{text}```", inline=False)
    #                     await interaction.followup.send(embed=error_embed)
    #                 else:
    #                     error_file = discord.File(io.BytesIO(text.encode('utf-8')), filename="error_details.txt")
    #                     await interaction.followup.send(embed=error_embed, file=error_file)
        
    #     except Exception as e:
    #         await interaction.followup.send(f"❌ Error fetching clan stats: {e}")
    
    @app_commands.command(name="clan-info-query", description="Query specific clan information")
    @app_commands.describe(
        query_type="Type of clan information to retrieve",
        clan_filter="Optional clan identifier to filter results"
    )
    @app_commands.choices(query_type=[
        app_commands.Choice(name="All Clans Overview", value="overview"),
        app_commands.Choice(name="Active Members", value="members"),
        app_commands.Choice(name="Recent Activity", value="activity"),
        app_commands.Choice(name="Performance Stats", value="performance"),
        app_commands.Choice(name="Raid History", value="raids"),
    ])
    async def clan_info_query(
        self,
        interaction: discord.Interaction,
        query_type: app_commands.Choice[str],
        clan_filter: Optional[str] = None
    ):
        """Query specific types of clan information"""
        await interaction.response.defer(thinking=True)
        
        try:
            # Build query parameters
            params = {"type": query_type.value}
            if clan_filter:
                params["clan"] = clan_filter
            
            # Make request to server
            query_url = f"{self.api_url}/clans/query"
            
            async with self.aiohttp_session.get(query_url, params=params) as resp:
                if 200 <= resp.status < 300:
                    try:
                        data = await resp.json()
                    except:
                        data = {"message": await resp.text()}
                    
                    embed = discord.Embed(
                        title=f"📋 {query_type.name}",
                        color=discord.Color.green()
                    )
                    
                    if clan_filter:
                        embed.description = f"Results filtered for clan: **{clan_filter}**"
                    
                    # Format the response based on query type
                    if isinstance(data, dict):
                        if "clans" in data:
                            clan_list = []
                            for clan_name, clan_data in data["clans"].items():
                                if isinstance(clan_data, dict):
                                    members = clan_data.get("members", "Unknown")
                                    level = clan_data.get("level", "Unknown")
                                    clan_list.append(f"**{clan_name}** - Level {level} ({members} members)")
                                else:
                                    clan_list.append(f"**{clan_name}** - {clan_data}")
                            
                            embed.add_field(
                                name="Clans",
                                value="\n".join(clan_list[:10]) + ("\n..." if len(clan_list) > 10 else ""),
                                inline=False
                            )
                        elif "message" in data:
                            embed.description = data["message"]
                        else:
                            # Generic data formatting
                            for key, value in list(data.items())[:5]:  # Limit fields
                                embed.add_field(
                                    name=key.replace("_", " ").title(),
                                    value=str(value)[:1000],  # Limit field length
                                    inline=True
                                )
                    else:
                        embed.description = str(data)[:2000]
                    
                    embed.set_footer(text=f"Query: {query_type.name}")
                    embed.timestamp = discord.utils.utcnow()
                    
                    await interaction.followup.send(embed=embed)
                
                else:
                    await interaction.followup.send(f"❌ Query failed with status {resp.status}")
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error executing clan query: {e}")
    
    @app_commands.command(name="server-status", description="Check RaidEye server status and connectivity")
    async def server_status(self, interaction: discord.Interaction):
        """Check the status of the RaidEye server"""
        await interaction.response.defer(thinking=True)
        
        embed = discord.Embed(
            title="🖥️ RaidEye Server Status",
            color=discord.Color.blue()
        )
        
        # Test basic connectivity
        try:
            async with self.aiohttp_session.get(f"{self.server_url}/", timeout=10) as resp:
                if resp.status == 200:
                    embed.add_field(name="🟢 Server", value="Online", inline=True)
                    embed.color = discord.Color.green()
                else:
                    embed.add_field(name="🟡 Server", value=f"Responding (HTTP {resp.status})", inline=True)
                    embed.color = discord.Color.orange()
        except Exception as e:
            embed.add_field(name="🔴 Server", value="Offline or unreachable", inline=True)
            embed.color = discord.Color.red()
            embed.add_field(name="Error", value=str(e)[:500], inline=False)
        
        # Test API endpoints
        api_endpoints = [
            ("Clan Stats", f"{self.api_url}/clans/stats/msg"),
            ("Image Extraction", f"{self.api_url}/extract/personal_scores/"),
            ("Hydra Injection", f"{self.api_url}/injest-hydra/"),
            ("Chimera Injection", f"{self.api_url}/injest-chimera/"),
        ]
        
        api_status = []
        for name, url in api_endpoints:
            try:
                async with self.aiohttp_session.get(url, timeout=5) as resp:
                    if 200 <= resp.status < 500:  # Accept any non-server-error status
                        api_status.append(f"✅ {name}")
                    else:
                        api_status.append(f"❌ {name} ({resp.status})")
            except Exception:
                api_status.append(f"❌ {name} (unreachable)")
        
        embed.add_field(
            name="🔧 API Endpoints",
            value="\n".join(api_status),
            inline=False
        )
        
        embed.add_field(name="🌐 Server URL", value=self.server_url, inline=False)
        embed.set_footer(text="Status checked")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    """Setup function called by discord.py when loading this cog"""
    await bot.add_cog(ClanStatsCommands(bot))