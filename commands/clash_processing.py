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
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
        filename_lower = attachment.filename.lower()
        has_valid_ext = any(filename_lower.endswith(ext) for ext in valid_extensions)
        has_valid_content_type = attachment.content_type and attachment.content_type.startswith('image/')
        return has_valid_ext or has_valid_content_type
    async def _extract_images_from_message(self, message: discord.Message):
        """Extract valid image attachments from a Discord message."""
        images = []
        # Check attachments
        for attachment in getattr(message, 'attachments', []):
            if self._is_valid_image_attachment(attachment):
                try:
                    img_data = await attachment.read()
                    images.append((img_data, attachment.filename))
                except Exception as e:
                    logging.warning(f"Failed to read attachment: {e}")
        # Optionally, check embeds for images
        for embed in getattr(message, 'embeds', []):
            if embed.image and embed.image.url:
                try:
                    async with self.aiohttp_session.get(embed.image.url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            filename = os.path.basename(embed.image.url)
                            images.append((img_data, filename))
                except Exception as e:
                    logging.warning(f"Failed to fetch embed image: {e}")
        return images
    """Hydra and Chimera clash processing commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None
        self.server_url = os.getenv('RAIDEYE_SERVER', '127.0.0.1:8000')
        if not self.server_url.startswith('http'):
            self.server_url = f'http://{self.server_url}'
        self.api_url = f"{self.server_url}/api/discord"
        
        # Clan list fetched from API
        self.clan_list = []

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

    async def cog_load(self):
        """Called when the cog is loaded"""
        self.aiohttp_session = aiohttp.ClientSession()
        # Fetch clan list from API
        try:
            async with self.aiohttp_session.get(f"{self.api_url}/clans/") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.clan_list = data.get('clans', [])
                    print(f"[clash_processing] Loaded clans: {self.clan_list}")
                    logging.info(f"Loaded clans: {self.clan_list}")
                else:
                    print(f"[clash_processing] Failed to fetch clans from API: HTTP {resp.status}")
                    logging.warning(f"Failed to fetch clans from API: HTTP {resp.status}")
        except Exception as e:
            print(f"[clash_processing] Error fetching clans from API: {e}")
            logging.warning(f"Error fetching clans from API: {e}")
    
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor MAIN_CHANNEL_ID and auto-process images when posted.

        Behavior: the first image is sent to a classifier endpoint (configurable via
        AUTO_CLASSIFY_ENDPOINT) which should return JSON like { "Clash Type": "Hydra" }
        or { "Clash Type": "Chimera" }. The returned type determines which processing
        path is used.
        """
        try:
            # Ignore bot messages
            if not message or message.author.bot:
                return

            # Also ignore if this bot has already reacted to the message
            try:
                bot_user_id = getattr(self.bot.user, 'id', None)
                if bot_user_id and getattr(message, 'reactions', None):
                    for react in message.reactions:
                        try:
                            async for u in react.users():
                                if getattr(u, 'id', None) == bot_user_id:
                                    return
                        except Exception:
                            # Some reaction user enumerations can fail; ignore and continue
                            continue
            except Exception:
                # Be conservative: if reaction inspection fails, continue processing
                return
            # Ensure message is from configured guild and channel
            if not message.guild or int(message.guild.id) != int(GUILD_ID):
                return
            if int(message.channel.id) != int(MAIN_CHANNEL_ID):
                return

            # Extract images
            images = await self._extract_images_from_message(message)
            if not images:
                return

            # Classify the first image by reusing the existing image extraction endpoint
            # with a prompt_type of 'classify'. The endpoint should return JSON that
            # includes a type field, e.g. {"type": "Hydra"} or {"type": "Chimera"}.
            clash_type = None
            try:
                img0_data, img0_name = images[0]
                extraction_result = await self._post_image_extraction(img0_data, img0_name, "classify")
                print(f"[clash_processing] Classifier extraction result: {extraction_result}")
                if extraction_result.get('success'):
                    data = extraction_result.get('data')
                    ctype = None
                    if isinstance(data, dict):
                        # Try several common keys
                        ctype = data.get('Clash Type')
                    elif isinstance(data, list) and data:
                        first = data[0]
                        if isinstance(first, dict):
                            ctype = first.get('Clash Type')
                        else:
                            ctype = str(first)
                    elif isinstance(data, str):
                        ctype = data
                    else:
                        ctype = None

                    if ctype:
                        ctype_str = str(ctype).lower()
                        if 'hydra' in ctype_str:
                            clash_type = 'hydra'
                        elif 'chimera' in ctype_str:
                            clash_type = 'chimera'
                else:
                    logging.warning(f"Classifier extraction failed: {extraction_result.get('error')}")
            except Exception as e:
                logging.exception(f"Error during classification via extraction endpoint: {e}")

            if clash_type not in ('hydra', 'chimera'):
                # Could not determine type; include full extraction_result for debugging
                try:
                    dump = json.dumps(extraction_result, indent=2, default=str)
                except Exception:
                    dump = str(extraction_result)

                try:
                    # If small enough to include in message, send inline; otherwise attach as file
                    if len(dump) <= 1900:
                        await message.reply(f"❌ Could not classify image type for automatic processing.\n```json\n{dump}\n```")
                    else:
                        fp = io.BytesIO(dump.encode('utf-8'))
                        fname = f"classify_result_{message.id}.json"
                        file = discord.File(fp, filename=fname)
                        await message.reply("❌ Could not classify image type for automatic processing. Full result attached.", file=file)
                except Exception:
                    # As a last resort, send a short fallback message
                    try:
                        await message.reply("❌ Could not classify image type for automatic processing. (failed to attach full result)")
                    except Exception:
                        pass
                return

            # Indicate processing
            try:
                await message.add_reaction('🔄')
            except Exception:
                pass

            # Process images with the classifier-provided type
            result = await self._process_clash_images(images, clash_type, None)

            # Build response
            if result.get('success'):
                view_url = result.get('view_url')
                reply = f"✅ Auto-processed {clash_type.title()} Clash\n"
                if view_url:
                    reply += f"[View Record]({result['view_url']})"
            else:
                reply = f"❌ Auto-processing failed: {result.get('error', 'Unknown error')}"

            # Reply in-channel to the original message
            try:
                await message.reply(reply)
            except Exception:
                # Fallback: send to channel
                try:
                    await message.channel.send(reply)
                except Exception:
                    pass

        except Exception as e:
            logging.exception(f"Error in on_message auto-process: {e}")
    
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
                            await interaction.followup.send(content=assignments_text, allowed_mentions=discord.AllowedMentions(users=True))

                            
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
        if not self.clan_list:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await interaction.followup.send("❌ Clan list is not loaded. Please try again later.", ephemeral=True)
            print("[clash_processing] Clan list is empty when context_hydra called!")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        view = ClanSelectView(message, "hydra", self, self.clan_list, interaction.user)
        await interaction.followup.send("Select your clan for Hydra clash:", view=view, ephemeral=True)

    async def context_chimera(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu: Process message as Chimera clash"""
        if not self.clan_list:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await interaction.followup.send("❌ Clan list is not loaded. Please try again later.", ephemeral=True)
            print("[clash_processing] Clan list is empty when context_chimera called!")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        view = ClanSelectView(message, "chimera", self, self.clan_list, interaction.user)
        await interaction.followup.send("Select your clan for Chimera clash:", view=view, ephemeral=True)
    async def _process_clash_message(self, message: discord.Message, clash_type: str, clan_token: str, dry_run: bool = False, date_recorded: Optional[str] = None):
        """Process a message for clash data"""
        try:
            # Extract images from the message
            images = await self._extract_images_from_message(message)
            if not images:
                return {'success': False, 'error': 'No images found'}
            return await self._process_clash_images(images, clash_type, clan_token, dry_run, date_recorded)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _process_clash_images(self, images: list, clash_type: str, clan_token: Optional[str], dry_run: bool = False, date_recorded: Optional[str] = None):
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
            # Prepare payload for injection
            payload = {
                "opponent_scores": extraction_result['data'],
                "date_recorded": discord.utils.utcnow().isoformat().replace("+00:00", "Z") if not date_recorded else date_recorded
            }
            # Only add clan if provided
            if clan_token:
                payload["clan"] = clan_token
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

# --- ClanSelectView for dropdown-based clan selection ---
class ClanSelectView(discord.ui.View):
    def __init__(self, message: discord.Message, clash_type: str, cog: HydraChimeraCommands, clan_list: list, user: discord.User):
        super().__init__(timeout=60)
        self.message = message
        self.clash_type = clash_type
        self.cog = cog
        self.user = user
        self.add_item(ClanSelectDropdown(clan_list, self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who invoked the context action to interact
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
            return False
        return True


class ClanTokenModal(discord.ui.Modal, title='Clan Information'):
    """Modal dialog to collect clan token for processing"""
    
    def __init__(self, message: discord.Message, clash_type: str, cog: HydraChimeraCommands, clan_list: list):
        super().__init__()
        self.message = message
        self.clash_type = clash_type
        self.cog = cog
        self.clan_list = clan_list
        # Use a String Select for clan selection (discord.py handles Action Row)
        self.clan_token = discord.ui.Select(
            placeholder='Select your clan',
            options=[discord.SelectOption(label=clan, value=clan) for clan in clan_list[:25]],
            min_values=0 if clash_type == 'hydra' else 1,
            max_values=1
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
            clan_token_value = self.clan_token.values[0] if self.clan_token.values else None
            # For chimera, clan token is required
            if self.clash_type == 'chimera' and not clan_token_value:
                await interaction.followup.send("❌ Clan name is required for Chimera processing.")
                return
            # Process the message
            result = await self.cog._process_clash_message(
                self.message, 
                self.clash_type, 
                clan_token_value,
                dry_run=False
            )
            if result['success']:
                embed = discord.Embed(
                    title=f"✅ {self.clash_type.title()} Processing Complete",
                    color=discord.Color.green()
                )
                embed.add_field(name="🏰 Clan", value=clan_token_value or "Not specified", inline=True)
                embed.add_field(name="📊 Images", value=str(result.get('image_count', 0)), inline=True)
                embed.add_field(name="🔄 Mode", value="Live", inline=True)
                if result.get('view_url'):
                    embed.add_field(name="🔗 View Record", value=f"[Click Here]({result['view_url']})", inline=False)
                if result.get('dry_run_payload'):
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


class ClanSelectDropdown(discord.ui.Select):
    def __init__(self, clan_list: list, parent_view: ClanSelectView):
        options = [discord.SelectOption(label=clan, value=clan) for clan in clan_list[:25]]
        super().__init__(placeholder="Select your clan", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        clan_token_value = self.values[0]
        # Show modal for date input after clan selection
        parent_view = self.parent_view
        class DateInputModal(discord.ui.Modal, title="Date Recorded"):
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                self.date_recorded = discord.ui.TextInput(
                    label="Date Recorded (YYYY-MM-DD)",
                    placeholder="e.g. 2025-10-15 (leave blank for today)",
                    required=False,
                    max_length=10
                )
                self.add_item(self.date_recorded)

            async def on_submit(self, modal_interaction: discord.Interaction):
                import datetime
                from discord.utils import utcnow
                date_str = self.date_recorded.value.strip()
                if date_str:
                    try:
                        # Use noon to avoid timezone issues, then format as UTC Z
                        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc)
                        date_iso = date_obj.isoformat().replace("+00:00", "Z")
                    except Exception:
                        await modal_interaction.response.send_message("❌ Invalid date format. Use YYYY-MM-DD.", ephemeral=True)
                        return
                else:
                    date_iso = utcnow().isoformat().replace("+00:00", "Z")
                await modal_interaction.response.defer(thinking=True)
                result = await self.parent_view.cog._process_clash_message(
                    self.parent_view.message,
                    self.parent_view.clash_type,
                    clan_token_value,
                    dry_run=False,
                    date_recorded=date_iso
                )
                if result['success']:
                    embed = discord.Embed(
                        title=f"✅ {self.parent_view.clash_type.title()} Processing Complete",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="🏰 Clan", value=clan_token_value or "Not specified", inline=True)
                    embed.add_field(name="📊 Images", value=str(result.get('image_count', 0)), inline=True)
                    embed.add_field(name="🔄 Mode", value="Live", inline=True)
                    if result.get('view_url'):
                        embed.add_field(name="🔗 View Record", value=f"[Click Here]({result['view_url']})", inline=False)
                    if result.get('dry_run_payload'):
                        preview = result['dry_run_payload'][:1000]
                        if len(result['dry_run_payload']) > 1000:
                            preview += "\n... (truncated)"
                        embed.add_field(name="📋 Preview Payload", value=f"```json\n{preview}\n```", inline=False)
                    embed.set_footer(text=f"Processed from message {self.parent_view.message.id}")
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    embed = discord.Embed(
                        title=f"❌ {self.parent_view.clash_type.title()} Processing Failed",
                        description=result.get('error', 'Unknown error occurred'),
                        color=discord.Color.red()
                    )
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.response.send_modal(DateInputModal(parent_view))
    
    
    