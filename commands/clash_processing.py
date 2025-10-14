import discord
from discord.ext import commands
from discord import Guild, app_commands
import aiohttp
import json
import os
import io
import logging
from typing import Optional, Literal
from config import GUILD_ID, MAIN_CHANNEL_ID

class HydraChimeraCommands(commands.Cog):
    """Hydra and Chimera clash processing commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None
        self.server_url = os.getenv('RAIDEYE_SERVER', '127.0.0.1:8000')
        if not self.server_url.startswith('http'):
            self.server_url = f'http://{self.server_url}'
        self.api_url = f"{self.server_url}/api/discord"
        
        # Clan mapping from environment or clans.json
        self.clan_map = {}
        self._load_clan_map()
        
        # Add context menu commands
        self.ctx_menu_hydra = app_commands.ContextMenu(
            name='Process as Hydra',
            callback=self.context_hydra,
            type=discord.AppCommandType.message
        )
        self.ctx_menu_chimera = app_commands.ContextMenu(
            name='Process as Chimera', 
            callback=self.context_chimera,
            type=discord.AppCommandType.message
        )
        
        self.bot.tree.add_command(self.ctx_menu_hydra)
        self.bot.tree.add_command(self.ctx_menu_chimera)
    
    def _load_clan_map(self):
        """Load clan mapping from clans.json or environment variable"""
        try:
            clan_map_env = os.getenv('DISCORD_CLAN_MAP')
            if clan_map_env:
                self.clan_map = json.loads(clan_map_env)
            elif os.path.exists('clans.json'):
                with open('clans.json', 'r') as f:
                    self.clan_map = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load clan map: {e}")
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        self.aiohttp_session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.aiohttp_session:
            await self.aiohttp_session.close()
        
        # Remove context menu commands
        try:
            self.bot.tree.remove_command(self.ctx_menu_hydra.name, type=discord.AppCommandType.message)
            self.bot.tree.remove_command(self.ctx_menu_chimera.name, type=discord.AppCommandType.message)
        except Exception as e:
            logging.warning(f"Failed to remove context menu commands: {e}")
    
    @app_commands.command(name="hydra", description="Process images for Hydra clash records")
    @app_commands.describe(
        clan_token="Clan identifier (e.g., '1', '2', etc.)",
        image="Image file to process (optional)",
        message_link="Discord message link containing images (optional)",
        dry_run="Preview what would be sent without actually processing"
    )
    async def process_hydra(
        self, 
        interaction: discord.Interaction, 
        clan_token: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
        message_link: Optional[str] = None,
        dry_run: bool = False
    ):
        """Process images as Hydra clash records"""
        await interaction.response.defer(thinking=True)
        
        message = None
        images_to_process = []
        
        # Priority 1: Direct image attachment
        if image:
            if self._is_valid_image_attachment(image):
                try:
                    img_data = await image.read()
                    images_to_process.append((img_data, image.filename))
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to read attached image: {e}")
                    return
            else:
                await interaction.followup.send("❌ Please attach a valid image file (PNG, JPG, JPEG, GIF, WebP)")
                return
        
        # Priority 2: Message link
        elif message_link:
            try:
                parts = message_link.strip().split('/')
                message_id = int(parts[-1])
                channel_id = int(parts[-2])
                channel = await self.bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                images_to_process = await self._extract_images_from_message(message)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to fetch message: {e}")
                return
        
        # No input provided
        else:
            await interaction.followup.send("❌ Please provide either an image attachment, a message link, or use the context menu on a message with images.")
            return
        
        if not images_to_process:
            await interaction.followup.send("❌ No valid images found to process.")
            return
        
        # Process each image separately
        try:
            results = []
            for img_data, filename in images_to_process:
                single_result = await self._process_clash_images([(img_data, filename)], "hydra", clan_token, dry_run)
                results.append(single_result)

            success_count = sum(1 for r in results if r.get('success'))
            response_text = f"✅ **Hydra Clash Processed**\n"
            response_text += f"📊 Processed {len(images_to_process)} image(s)\n"
            response_text += f"🏰 Clan: {clan_token or 'Not specified'}\n"

            for idx, result in enumerate(results, 1):
                if result.get('success'):
                    response_text += f"\nImage {idx}: Success"
                    if result.get('view_url'):
                        response_text += f" | [View Record]({result['view_url']})"
                    if dry_run and result.get('dry_run_payload'):
                        preview = result['dry_run_payload'][:500]
                        response_text += f"\nPreview: ```json\n{preview}\n```"
                else:
                    response_text += f"\nImage {idx}: ❌ Failed - {result.get('error', 'Unknown error')}"

            if dry_run:
                response_text += f"\n\n**DRY RUN - No data was actually sent**"

            await interaction.followup.send(response_text[:2000])
        except Exception as e:
            await interaction.followup.send(f"❌ Error processing Hydra clash: {e}")
    
    @app_commands.command(name="chimera", description="Process images for Chimera clash records")
    @app_commands.describe(
        clan_token="Clan identifier (e.g., '1', '2', etc.)",
        image="Image file to process (optional)",
        message_link="Discord message link containing images (optional)",
        dry_run="Preview what would be sent without actually processing"
    )
    async def process_chimera(
        self, 
        interaction: discord.Interaction, 
        clan_token: str,
        image: Optional[discord.Attachment] = None,
        message_link: Optional[str] = None,
        dry_run: bool = False
    ):
        """Process images as Chimera clash records"""
        await interaction.response.defer(thinking=True)
        
        message = None
        images_to_process = []
        
        # Priority 1: Direct image attachment
        if image:
            if self._is_valid_image_attachment(image):
                try:
                    img_data = await image.read()
                    images_to_process.append((img_data, image.filename))
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to read attached image: {e}")
                    return
            else:
                await interaction.followup.send("❌ Please attach a valid image file (PNG, JPG, JPEG, GIF, WebP)")
                return
        
        # Priority 2: Message link
        elif message_link:
            try:
                parts = message_link.strip().split('/')
                message_id = int(parts[-1])
                channel_id = int(parts[-2])
                channel = await self.bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                images_to_process = await self._extract_images_from_message(message)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to fetch message: {e}")
                return
        
        # No input provided
        else:
            await interaction.followup.send("❌ Please provide either an image attachment, a message link, or use the context menu on a message with images.")
            return
        
        if not images_to_process:
            await interaction.followup.send("❌ No valid images found to process.")
            return
        
        # Process each image separately
        try:
            results = []
            for img_data, filename in images_to_process:
                single_result = await self._process_clash_images([(img_data, filename)], "chimera", clan_token, dry_run)
                results.append(single_result)

            success_count = sum(1 for r in results if r.get('success'))
            response_text = f"✅ **Chimera Clash Processed**\n"
            response_text += f"📊 Processed {len(images_to_process)} image(s)\n"
            response_text += f"🏰 Clan: {clan_token}\n"

            for idx, result in enumerate(results, 1):
                if result.get('success'):
                    response_text += f"\nImage {idx}: Success"
                    if result.get('view_url'):
                        response_text += f" | [View Record]({result['view_url']})"
                    if dry_run and result.get('dry_run_payload'):
                        preview = result['dry_run_payload'][:500]
                        response_text += f"\nPreview: ```json\n{preview}\n```"
                else:
                    response_text += f"\nImage {idx}: ❌ Failed - {result.get('error', 'Unknown error')}"

            if dry_run:
                response_text += f"\n\n**DRY RUN - No data was actually sent**"

            await interaction.followup.send(response_text[:2000])
        except Exception as e:
            await interaction.followup.send(f"❌ Error processing Chimera clash: {e}")
    
    @app_commands.command(name="siege", description="Manage siege plans - notify participants or edit assignments")
    @app_commands.describe(
        action="Action to perform (notify participants or edit plan)",
        plan_id="Siege plan ID number"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Notify Participants", value="notify"),
        app_commands.Choice(name="Edit Plan", value="edit")
    ])
    async def siege_command(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        plan_id: str
    ):
        """Manage siege plans - notify participants or provide edit link"""
        await interaction.response.defer(thinking=True)
        
        try:
            if action.value == "notify":
                # Send request to notify endpoint
                url = f"{self.server_url}/api/discord/siege-plan/{plan_id}/assignments/"
                
                async with self.aiohttp_session.get(url) as resp:
                    if 200 <= resp.status < 300:
                        try:
                            result_data = await resp.json()
                            
                            # Format the response according to the specified structure
                            plan_name = result_data.get('name', 'Unknown Plan')
                            assignments = result_data.get('assignments', [])
                            towers = result_data.get('towers', [])
                            
                            embed = discord.Embed(
                                title=f"🏰 Siege Plan: {plan_name}",
                                description=f"Plan ID: {plan_id}",
                                color=discord.Color.blue()
                            )
                            assignments_text = ""
                            # Format assignments
                            if assignments:
                                
                                for assignment in assignments:
                                    print(assignment)
                                    post_num = assignment.get('post_number', 'Unknown')
                                    team_choice = assignment.get('team_choice', 'No team')
                                    assigned_player = assignment.get('assigned_player') or {}
                                    player_name = assigned_player.get('name', '')
                                    discord_username = assigned_player.get('discord', '')
                                    selected_arena_team = assignment.get('selected_arena_team', 'No arena team')
                                    
                                    # Format the line
                                    line = f"Post {post_num} - {player_name if player_name else 'No Player Assigned'} - {team_choice if team_choice else 'No Condition Assigned'}"
                                    for member in interaction.guild.members:
                                        if member.name == discord_username:
                                           line += f" -> <@{member.id}>" 
                                    # Print just the champ names if selected_arena_team is a dict with 'champions'
                                    if isinstance(selected_arena_team, dict) and 'champions' in selected_arena_team:
                                        champs = ', '.join(selected_arena_team['champions'])
                                        line += f" ({champs})"
                                    elif selected_arena_team and selected_arena_team != 'No arena team':
                                        line += f" ({selected_arena_team})"
                                    assignments_text += line + "\n"
                                
                                
                            else:
                                assignments_text = "No Assignments"
                                pass
                            
                            # towers_text = "\n\n"
                            # # Format towers
                            # if towers:
                               
                            #     for i, tower in enumerate(towers, 1):
                            #         # Format tower info based on structure (adjust as needed)
                            #         if isinstance(tower, dict):
                            #             tower_info = str(tower)
                            #         else:
                            #             tower_info = str(tower)
                            #         towers_text += f"Tower {i}: {tower_info}\n"
                                
                               
                            # else:
                            #     towers_text += "No Tower Assigments"
                            

                            
                            # 3. Send the string in the 'content' argument along with the embed
                            await interaction.followup.send(content=assignments_text+towers_text, allowed_mentions=discord.AllowedMentions(users=True))

                            
                        except Exception as parse_error:
                            # If response isn't JSON or parsing fails
                            text_response = await resp.text()
                            embed = discord.Embed(
                                title="🏰 Siege Plan Notifications Sent",
                                description=f"Successfully notified participants for siege plan #{plan_id}",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="📋 Plan ID", value=plan_id, inline=True)
                            embed.add_field(name="📡 Response", value=text_response[:1000], inline=False)
                            embed.set_footer(text=f"Parse error: {str(parse_error)}")
                            await interaction.followup.send(embed=embed)
                    else:
                        error_text = await resp.text()
                        embed = discord.Embed(
                            title="❌ Notification Failed",
                            description=f"Failed to notify participants for siege plan #{plan_id}",
                            color=discord.Color.red()
                        )
                        embed.add_field(name="📋 Plan ID", value=plan_id, inline=True)
                        embed.add_field(name="🚫 Error", value=f"HTTP {resp.status}: {error_text[:500]}", inline=False)
                        await interaction.followup.send(embed=embed)
            
            elif action.value == "edit":
                # Provide edit link
                edit_url = f"{self.server_url}/siege-plan/{plan_id}/assign/"
                
                embed = discord.Embed(
                    title="✏️ Edit Siege Plan",
                    description=f"Click the link below to edit siege plan #{plan_id}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="📋 Plan ID", value=plan_id, inline=True)
                embed.add_field(name="🔗 Edit Link", value=f"[Click Here to Edit]({edit_url})", inline=False)
                embed.set_footer(text="This link will open in your browser")
                
                await interaction.followup.send(embed=embed)
            
            else:
                await interaction.followup.send("❌ Invalid action. Please use 'notify' or 'edit'.")
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Siege Command Error",
                description=f"An error occurred while processing siege plan #{plan_id}",
                color=discord.Color.red()
            )
            embed.add_field(name="🚫 Error", value=str(e), inline=False)
            embed.add_field(name="🔧 Action", value=action.name, inline=True)
            embed.add_field(name="📋 Plan ID", value=plan_id, inline=True)
            await interaction.followup.send(embed=embed)
    
    async def context_hydra(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu: Process message as Hydra clash"""
        await interaction.response.send_modal(ClanTokenModal(message, "hydra", self))
    
    async def context_chimera(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu: Process message as Chimera clash"""
        await interaction.response.send_modal(ClanTokenModal(message, "chimera", self))
    
    # @app_commands.command(name="extract-images", description="Extract and analyze images from a message")
    # @app_commands.describe(
    #     message_link="Discord message link containing images",
    #     prompt_type="Type of analysis to perform on the images"
    # )
    # @app_commands.choices(prompt_type=[
    #     app_commands.Choice(name="Hydra Clash Record", value="hydra clash record"),
    #     app_commands.Choice(name="Chimera Clash Record", value="chimera clash record"),
    #     app_commands.Choice(name="Personal Scores", value="personal scores"),
    #     app_commands.Choice(name="Custom Analysis", value="custom"),
    # ])
    # async def extract_images(
    #     self, 
    #     interaction: discord.Interaction, 
    #     message_link: str,
    #     prompt_type: app_commands.Choice[str]
    # ):
    #     """Extract and analyze images using the server's extraction endpoint"""
    #     await interaction.response.defer(thinking=True)
        
    #     try:
    #         # Parse message link
    #         parts = message_link.strip().split('/')
    #         message_id = int(parts[-1])
    #         channel_id = int(parts[-2])
    #         channel = await self.bot.fetch_channel(channel_id)
    #         message = await channel.fetch_message(message_id)
    #     except Exception as e:
    #         await interaction.followup.send(f"❌ Failed to fetch message: {e}")
    #         return
        
    #     # Extract images and send to analysis
    #     try:
    #         images = await self._extract_images_from_message(message)
    #         if not images:
    #             await interaction.followup.send("❌ No images found in the specified message.")
    #             return
            
    #         results = []
    #         for img_data, filename in images:
    #             result = await self._post_image_extraction(img_data, filename, prompt_type.value)
    #             results.append(result)
            
    #         # Format response
    #         response_text = f"📊 **Image Analysis Results**\n"
    #         response_text += f"🖼️ Analyzed {len(images)} image(s)\n"
    #         response_text += f"🔍 Analysis Type: {prompt_type.name}\n\n"
            
    #         for i, result in enumerate(results, 1):
    #             if result['success']:
    #                 response_text += f"**Image {i}:** ✅ Success\n"
    #                 if isinstance(result['data'], dict):
    #                     # Format structured data nicely
    #                     for key, value in result['data'].items():
    #                         if key != 'rotation':  # Skip rotation data
    #                             response_text += f"  • {key}: {value}\n"
    #                 else:
    #                     response_text += f"  • Result: {result['data']}\n"
    #             else:
    #                 response_text += f"**Image {i}:** ❌ Failed - {result.get('error', 'Unknown error')}\n"
    #             response_text += "\n"
            
    #         await interaction.followup.send(response_text[:2000])  # Discord message limit
            
    #     except Exception as e:
    #         await interaction.followup.send(f"❌ Error extracting images: {e}")
    
    async def _process_clash_message(self, message: discord.Message, clash_type: str, clan_token: str, dry_run: bool = False):
        """Process a message for clash data"""
        try:
            # Extract images from the message
            images = await self._extract_images_from_message(message)
            if not images:
                return {'success': False, 'error': 'No images found'}
            
            return await self._process_clash_images(images, clash_type, clan_token, dry_run)
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _process_clash_images(self, images: list, clash_type: str, clan_token: Optional[str], dry_run: bool = False):
        """Process images for clash data"""
        try:
            if not images:
                return {'success': False, 'error': 'No images provided'}
            
            # Process first image (assuming one score image per request)
            img_data, filename = images[0]
            
            # Extract data from image
            extraction_result = await self._post_image_extraction(img_data, filename, f"{clash_type} clash record")
            if not extraction_result['success']:
                return {'success': False, 'error': f"Image extraction failed: {extraction_result.get('error')}"}
            
            # Resolve clan token if provided
            resolved_clan = None
            if clan_token:
                resolved_clan = self.clan_map.get(str(clan_token), clan_token)
            
            # Prepare payload for injection
            payload = {
                "opponent_scores": extraction_result['data'],
                "date_recorded": discord.utils.utcnow().isoformat().replace("+00:00", "Z")
            }
            
            # Only add clan if provided
            if resolved_clan:
                payload["clan"] = resolved_clan
            
            if dry_run:
                return {
                    'success': True,
                    'image_count': len(images),
                    'dry_run_payload': json.dumps(payload, indent=2),
                    'message': 'DRY RUN - Would send this payload'
                }
            
            # Send to injection endpoint
            inject_result = await self._inject_clash_data(payload, clash_type)
            if inject_result['success']:
                # Generate view URL
                clash_id_key = f"{clash_type}_clash_id"
                clash_id = inject_result['data'].get(clash_id_key)
                view_url = f"{self.server_url}/{clash_type}/{clash_id}/edit/" if clash_id else None
                
                return {
                    'success': True,
                    'image_count': len(images),
                    'view_url': view_url,
                    'message': inject_result['data'].get('message', 'Successfully processed')
                }
            else:
                return {'success': False, 'error': f"Injection failed: {inject_result.get('error')}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _extract_images_from_message(self, message: discord.Message):
        """Extract all images from a Discord message"""
        images = []
        
        # Process attachments
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                img_data = await attachment.read()
                images.append((img_data, attachment.filename))
        
        # Process embeds
        for embed in message.embeds:
            image_url = None
            if embed.image and embed.image.url:
                image_url = embed.image.url
            elif embed.thumbnail and embed.thumbnail.url:
                image_url = embed.thumbnail.url
            
            if image_url:
                try:
                    async with self.aiohttp_session.get(image_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            filename = os.path.basename(image_url.split('?')[0])
                            images.append((img_data, filename))
                except Exception as e:
                    logging.warning(f"Failed to download embed image {image_url}: {e}")
        
        return images
    
    async def _post_image_extraction(self, img_data: bytes, filename: str, prompt_type: str):
        """Send image to extraction endpoint"""
        try:
            url = f"{self.api_url}/extract/personal_scores/"
            
            data = aiohttp.FormData()
            data.add_field('images', img_data, filename=filename, content_type='image/png')
            data.add_field('prompt_type', prompt_type)
            
            async with self.aiohttp_session.post(url, data=data) as resp:
                text = await resp.text()
                if 200 <= resp.status < 300:
                    try:
                        result_data = await resp.json()
                        return {'success': True, 'data': result_data}
                    except:
                        return {'success': True, 'data': text}
                else:
                    return {'success': False, 'error': f"HTTP {resp.status}: {text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _inject_clash_data(self, payload: dict, clash_type: str):
        """Send clash data to injection endpoint"""
        try:
            url = f"{self.api_url}/injest-{clash_type}/"
            headers = {"Content-Type": "application/json"}
            
            async with self.aiohttp_session.post(url, data=json.dumps(payload), headers=headers) as resp:
                text = await resp.text()
                if 200 <= resp.status < 300:
                    try:
                        result_data = await resp.json()
                        return {'success': True, 'data': result_data}
                    except:
                        return {'success': True, 'data': {'message': text}}
                else:
                    return {'success': False, 'error': f"HTTP {resp.status}: {text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _is_valid_image_attachment(self, attachment: discord.Attachment) -> bool:
        """Check if the attachment is a valid image file"""
        if not attachment.filename:
            return False
        
        # Check file extension
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
        filename_lower = attachment.filename.lower()
        has_valid_ext = any(filename_lower.endswith(ext) for ext in valid_extensions)
        
        # Check content type if available
        has_valid_content_type = attachment.content_type and attachment.content_type.startswith('image/')
        
        return has_valid_ext or has_valid_content_type


class ClanTokenModal(discord.ui.Modal, title='Clan Information'):
    """Modal dialog to collect clan token for processing"""
    
    def __init__(self, message: discord.Message, clash_type: str, cog: HydraChimeraCommands):
        super().__init__()
        self.message = message
        self.clash_type = clash_type
        self.cog = cog
        
        # Create the clan token input with conditional requirements
        self.clan_token = discord.ui.TextInput(
            label='Clan Token/ID',
            placeholder='Enter your clan identifier (e.g., 1, 2, clan_name)',
            required=clash_type != 'hydra',  # Optional for hydra, required for chimera
            max_length=50
        )
        self.add_item(self.clan_token)
    
    dry_run = discord.ui.TextInput(
        label='Dry Run? (y/n)',
        placeholder='Enter "y" for preview only, "n" to actually process',
        required=False,
        default='n',
        max_length=1
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        try:
            is_dry_run = self.dry_run.value.lower().startswith('y')
            clan_token_value = self.clan_token.value.strip() if self.clan_token.value else None
            
            # For chimera, clan token is required
            if self.clash_type == 'chimera' and not clan_token_value:
                await interaction.followup.send("❌ Clan token is required for Chimera processing.")
                return
            
            # Process the message
            result = await self.cog._process_clash_message(
                self.message, 
                self.clash_type, 
                clan_token_value,
                dry_run=is_dry_run
            )
            
            if result['success']:
                embed = discord.Embed(
                    title=f"✅ {self.clash_type.title()} Processing Complete",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="🏰 Clan", value=clan_token_value or "Not specified", inline=True)
                embed.add_field(name="📊 Images", value=str(result.get('image_count', 0)), inline=True)
                embed.add_field(name="🔄 Mode", value="Dry Run" if is_dry_run else "Live", inline=True)
                
                if result.get('view_url') and not is_dry_run:
                    embed.add_field(name="🔗 View Record", value=f"[Click Here]({result['view_url']})", inline=False)
                
                if result.get('dry_run_payload'):
                    # For dry run, show preview
                    preview = result['dry_run_payload'][:1000]
                    if len(result['dry_run_payload']) > 1000:
                        preview += "\n... (truncated)"
                    embed.add_field(name="📋 Preview Payload", value=f"```json\n{preview}\n```", inline=False)
                
                embed.set_footer(text=f"Processed from message {self.message.id}")
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=f"❌ {self.clash_type.title()} Processing Failed",
                    description=result.get('error', 'Unknown error occurred'),
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error processing {self.clash_type}: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logging.exception("Error in ClanTokenModal")
        try:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ An error occurred: {error}")


async def setup(bot):
    """Setup function called by discord.py when loading this cog"""
    await bot.add_cog(HydraChimeraCommands(bot))