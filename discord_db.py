r"""Discord image saver

This script runs a Discord bot which:
- Scans message history for specified channels and saves image attachments and embed images
- Listens for new messages and saves images in real-time

Behavior implemented:
- POSTs images to the server extraction endpoint: {server_base}/api/discord/extract/personal_scores/
    with form field 'images' and 'prompt_type' set to 'hydra clash record'.
- Determines injest type by searching the message content for the words 'hydra' or 'chimera'.
    If present, POSTs a JSON payload to the corresponding injest endpoint and posts that endpoint's
    plain-text response to the channel. If missing, posts 'no injest type found' and treats the image
    as handled so the original message will be deleted.

Usage (PowerShell):
    $env:DISCORD_BOT_TOKEN = '<your bot token>'
    python ./extractor/discord_db.py --guild-id 123456789012345678 --channels 111111111111,22222 --output ./discord_images --server-url https://example.com
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
import io
from typing import Any, Iterable, List, Optional, Tuple

import aiohttp
from discord import app_commands
import mimetypes
import discord
from discord import Intents, Message
from discord.ext import commands

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}

def sanitize_dirname(name: str) -> str:
    name = name.strip()
    return re.sub(r'[<>:"/\\|?*]', "_", name)

def is_image_filename(filename: Optional[str]) -> bool:
    if not filename:
        return False
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in IMAGE_EXTS)

def is_image_url(url: str) -> bool:
    url_lower = url.split("?")[0].lower()
    return any(url_lower.endswith(ext) for ext in IMAGE_EXTS)

class ImageBot(commands.Bot):
    def __init__(
        self,
        *,
        guild_id: int,
        channels: Optional[Iterable[int]],
        output_dir: str,
        history_limit: Optional[int],
        server_url: Optional[str],
        dry_run: bool = False,
        clan_map_json: Optional[str] = None,
        **kwargs,
    ):
        intents = kwargs.pop("intents", None) or Intents.default()
        super().__init__(intents=intents, **kwargs)
        self.guild_id = guild_id
        self.channel_whitelist = set(channels) if channels else None
        self.output_dir = output_dir
        self.history_limit = history_limit
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None
        # If dry_run is True, the bot will not POST to injest endpoints; it will only show payloads.
        self.dry_run = bool(dry_run)
        # clan_map_json can be a JSON string mapping short tokens (eg. "1") to
        # the real value expected by the server. If not provided, will fall back
        # to the DISCORD_CLAN_MAP env var (JSON string).
        self.clan_map: dict = {}
        cmj = clan_map_json or os.environ.get("DISCORD_CLAN_MAP")
        if cmj:
            try:
                # allow passing a filename by prefixing with @
                if isinstance(cmj, str) and cmj.startswith("@"):
                    path = cmj[1:]
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as fh:
                            cmj = fh.read()
                self.clan_map = json.loads(cmj)
            except Exception:
                logging.exception("Failed to parse clan_map JSON; continuing with empty map")
        # server_url should point to the host root (e.g. https://example.com) - we'll append /api/discord
        self.server_url = None
        self.view_server_url = None  # base URL for viewing hydra/chimera records
        if server_url:
            s = server_url.strip()
            if not s.startswith("http://") and not s.startswith("https://"):
                s = "http://" + s
            self.view_server_url = s.rstrip("/")
            self.server_url = s.rstrip("/") + "/api/discord"

    async def setup_hook(self) -> None:
        self.aiohttp_session = aiohttp.ClientSession()
        logging.info("ImageBot setup_hook starting: creating aiohttp session and registering commands")
        # Register app commands: context menu (message) and slash commands for Hydra and Chimera
        # Context menu commands make it easy to act on a specific message via right-click -> Apps -> Hydra
        async def _hydra_context(interaction: discord.Interaction, message: discord.Message):
            await interaction.response.defer(thinking=True)
            chan_dir_name = sanitize_dirname(f"{message.channel.name}_{message.channel.id}")
            chan_dir = os.path.join(self.output_dir, chan_dir_name)
            os.makedirs(chan_dir, exist_ok=True)
            saved, ok, responses = await self._process_and_save_message(message, chan_dir, injest_type_override='hydra', delete_files_after_success=True)
            await interaction.followup.send(f"Processed {saved} image(s). Success: {ok}")

        async def _chimera_context(interaction: discord.Interaction, message: discord.Message):
            await interaction.response.defer(thinking=True)
            chan_dir_name = sanitize_dirname(f"{message.channel.name}_{message.channel.id}")
            chan_dir = os.path.join(self.output_dir, chan_dir_name)
            os.makedirs(chan_dir, exist_ok=True)
            saved, ok, responses = await self._process_and_save_message(message, chan_dir, injest_type_override='chimera', delete_files_after_success=True)
            await interaction.followup.send(f"Processed {saved} image(s). Success: {ok}")

        # Context menu registration
        # Register message context menu commands (must set type=AppCommandType.message)
        self.tree.add_command(
            app_commands.ContextMenu(
                name="Hydra",
                callback=_hydra_context,
                type=discord.AppCommandType.message,
            )
        )
        self.tree.add_command(
            app_commands.ContextMenu(
                name="Chimera",
                callback=_chimera_context,
                type=discord.AppCommandType.message,
            )
        )
        logging.debug("Registered context menu commands: Hydra, Chimera")

        # Debug: list local commands registered in the CommandTree before syncing
        try:
            local_cmds = [c.name for c in self.tree.walk_commands()]
            logging.info(f"Local command tree contains {len(local_cmds)} commands: {local_cmds}")
        except Exception:
            logging.exception("Failed to enumerate local command tree")

        # Slash commands that accept a message link (optional). If message_link is omitted, instruct the user to use the context menu.
        async def _hydra_slash(interaction: discord.Interaction, message_link: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            if not message_link:
                await interaction.followup.send("Please use the message context menu (right-click a message -> Apps -> Hydra) or provide a message link.")
                return
            # Parse message link: https://discord.com/channels/<guild_id>/<channel_id>/<message_id>
            try:
                parts = message_link.strip().split('/')
                message_id = int(parts[-1])
                channel_id = int(parts[-2])
            except Exception:
                await interaction.followup.send("Invalid message link format")
                return
            try:
                chan = await self.fetch_channel(channel_id)
                msg = await chan.fetch_message(message_id)
            except Exception as e:
                await interaction.followup.send(f"Failed to fetch message: {e}")
                return
            chan_dir_name = sanitize_dirname(f"{msg.channel.name}_{msg.channel.id}")
            chan_dir = os.path.join(self.output_dir, chan_dir_name)
            os.makedirs(chan_dir, exist_ok=True)
            saved, ok, responses = await self._process_and_save_message(msg, chan_dir, injest_type_override='hydra', delete_files_after_success=True)
            await interaction.followup.send(f"Processed {saved} image(s). Success: {ok}")

        hydra_cmd = app_commands.Command(name="hydra", description="Ingest a message's images as a Hydra clash (use context menu for message target)", callback=_hydra_slash)
        self.tree.add_command(hydra_cmd)

        async def _chimera_slash(interaction: discord.Interaction, message_link: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            if not message_link:
                await interaction.followup.send("Please use the message context menu (right-click a message -> Apps -> Chimera) or provide a message link.")
                return
            try:
                parts = message_link.strip().split('/')
                message_id = int(parts[-1])
                channel_id = int(parts[-2])
            except Exception:
                await interaction.followup.send("Invalid message link format")
                return
            try:
                chan = await self.fetch_channel(channel_id)
                msg = await chan.fetch_message(message_id)
            except Exception as e:
                await interaction.followup.send(f"Failed to fetch message: {e}")
                return
            chan_dir_name = sanitize_dirname(f"{msg.channel.name}_{msg.channel.id}")
            chan_dir = os.path.join(self.output_dir, chan_dir_name)
            os.makedirs(chan_dir, exist_ok=True)
            saved, ok, responses = await self._process_and_save_message(msg, chan_dir, injest_type_override='chimera', delete_files_after_success=True)
            await interaction.followup.send(f"Processed {saved} image(s). Success: {ok}")

        chimera_cmd = app_commands.Command(name="chimera", description="Ingest a message's images as a Chimera clash (use context menu for message target)", callback=_chimera_slash)
        self.tree.add_command(chimera_cmd)

        # Sync commands for the guild only (faster iteration). If guild_id is provided, sync to that guild.
        try:
            if self.guild_id:
                logging.info(f"Syncing app commands to guild {self.guild_id}")
                guild = discord.Object(id=self.guild_id)
                result = await self.tree.sync(guild=guild)
                logging.info(f"Synced {len(result)} commands to guild {self.guild_id}")
                # Fetch and log what the guild currently has registered
                try:
                    fetched = await self.tree.fetch_commands(guild=guild)
                    fetched_names = [c.name for c in fetched]
                    logging.info(f"Guild {self.guild_id} currently has {len(fetched_names)} commands: {fetched_names}")
                except Exception:
                    logging.exception("Failed to fetch guild commands after sync")
            else:
                logging.info("Syncing app commands globally")
                result = await self.tree.sync()
                logging.info(f"Synced {len(result)} global commands")
        except Exception:
            # ignore sync errors for now but log
            logging.exception("Failed to sync app commands")

    async def close(self) -> None:
        if self.aiohttp_session:
            await self.aiohttp_session.close()
        await super().close()

    async def on_ready(self) -> None:
        logging.info(f"Logged in as {self.user} (id: {self.user.id})")
        guild = self.get_guild(self.guild_id)
        if guild is None:
            logging.error(
                f"Guild with id {self.guild_id} not found or bot not in guild"
            )
            await self.close()
            return

        logging.info(f"Found guild: {guild.name} ({guild.id})")
        os.makedirs(self.output_dir, exist_ok=True)
        for channel in guild.text_channels:
            if self.channel_whitelist and channel.id not in self.channel_whitelist:
                continue
            chan_dir_name = sanitize_dirname(f"{channel.name}_{channel.id}")
            chan_dir = os.path.join(self.output_dir, chan_dir_name)
            os.makedirs(chan_dir, exist_ok=True)
            logging.info(
                f"Scanning history for #{channel.name} ({channel.id}) -> {chan_dir}"
            )
            saved = 0
            try:
                async for msg in channel.history(
                    limit=self.history_limit, oldest_first=True
                ):
                    count, ok, _saved_files = await self._process_and_save_message(msg, chan_dir, delete_files_after_success=True)
                    if count:
                        if ok:
                            try:
                                await msg.delete()
                                logging.debug(
                                    f"Deleted message {msg.id} from #{channel.name}"
                                )
                            except discord.Forbidden:
                                logging.warning(
                                    f"Missing permission to delete message {msg.id} in #{channel.name}"
                                )
                            except Exception:
                                logging.exception(
                                    f"Failed to delete message {msg.id} in #{channel.name}"
                                )
                        saved += count
            except Exception as e:
                logging.exception(f"Failed scanning channel {channel.name}: {e}")
            logging.info(f"Saved {saved} images from history of #{channel.name}")
        logging.info("History scan complete. Listening for new messages...")

    async def on_message(self, message: Message) -> None:
        if message.author.bot:
            return
        if message.guild is None or message.guild.id != self.guild_id:
            return
        if self.channel_whitelist and message.channel.id not in self.channel_whitelist:
            return

        # If the message contains the standalone word 'info', fetch clan stats
        try:
            if re.search(r"\binfo\b", (message.content or "").lower()):
                if not self.server_url:
                    try:
                        await message.channel.send("Server URL not configured; cannot fetch clan stats.")
                    except Exception:
                        logging.exception("Failed to notify about missing server URL")
                    return

                stats_url = f"{self.server_url}/clans/stats/msg"
                try:
                    async with (self.aiohttp_session or aiohttp.ClientSession()).get(stats_url) as resp:
                        text = await resp.text()
                        if 200 <= resp.status < 300:
                            # Decode JSON if possible, otherwise fall back to raw text
                            try:
                                j = json.loads(text)
                                message_text = j.get("message") if isinstance(j, dict) else str(j)
                            except Exception:
                                message_text = text

                            # Try to locate an image in the original message (attachments, embeds, or links)
                            image_url: Optional[str] = None
                            try:
                                for att in message.attachments:
                                    if att.url and (is_image_url(att.url) or is_image_filename(getattr(att, "filename", None))):
                                        image_url = att.url
                                        break
                                if not image_url:
                                    for emb in message.embeds:
                                        url = None
                                        if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                                            url = emb.image.url
                                        elif getattr(emb, "thumbnail", None) and getattr(emb.thumbnail, "url", None):
                                            url = emb.thumbnail.url
                                        if url and is_image_url(url):
                                            image_url = url
                                            break
                                if not image_url:
                                    # look for image links in content
                                    for u in re.findall(r"(https?://[^\s]+)", message.content or ""):
                                        if is_image_url(u):
                                            image_url = u
                                            break
                            except Exception:
                                logging.exception("Failed while searching for image in original message")

                            # Download image bytes if we found an image URL
                            file_obj = None
                            filename = None
                            if image_url:
                                try:
                                    async with (self.aiohttp_session or aiohttp.ClientSession()).get(image_url) as img_resp:
                                        if img_resp.status == 200:
                                            img_bytes = await img_resp.read()
                                            file_obj = io.BytesIO(img_bytes)
                                            file_obj.seek(0)
                                            filename = os.path.basename(image_url.split("?")[0]) or "image"
                                except Exception:
                                    logging.exception("Failed to download image for info response")

                            # Delete original message (best-effort). Whether delete succeeds or not,
                            # still attempt to reply with the stats and optional image.
                            try:
                                await message.delete()
                            except Exception:
                                logging.exception("Failed to delete original message before replying")

                            try:
                                if file_obj:
                                    await message.channel.send(f"{message.author.mention}, {message_text}", file=discord.File(file_obj, filename=filename))
                                else:
                                    await message.channel.send(f"{message.author.mention}, {message_text}")
                            except Exception:
                                logging.exception("Failed to send clan stats response message")
                        else:
                            # Non-2xx status: include status and body, but cap length or attach
                            if len(text) <= 1600:
                                await message.channel.send(f"Failed to fetch clan stats: {resp.status}\n{text}")
                            else:
                                bio = io.BytesIO(text.encode("utf-8"))
                                bio.seek(0)
                                await message.channel.send(f"Failed to fetch clan stats: {resp.status} (body attached)", file=discord.File(bio, filename="clan_stats_error.txt"))
                except Exception as e:
                    logging.exception("Failed to fetch clan stats")
                    try:
                        await message.channel.send(f"Error fetching clan stats: {e}")
                    except Exception:
                        logging.exception("Failed to send error message for clan stats")
                return
        except Exception:
            logging.exception("Error while handling 'info' command in on_message")


        # Process and save images from the new message
        chan_dir_name = sanitize_dirname(f"{message.channel.name}_{message.channel.id}")
        chan_dir = os.path.join(self.output_dir, chan_dir_name)
        os.makedirs(chan_dir, exist_ok=True)
        saved, ok, _saved_files = await self._process_and_save_message(message, chan_dir, delete_files_after_success=True)
        if saved:
            logging.info(
                f"Saved {saved} image(s) from new message {message.id} in #{message.channel.name}"
            )
            if ok:
                try:
                    await message.delete()
                    logging.debug(
                        f"Deleted message {message.id} in #{message.channel.name}"
                    )
                except discord.Forbidden:
                    logging.warning(
                        f"Missing permission to delete message {message.id} in #{message.channel.name}"
                    )
                except Exception:
                    logging.exception(
                        f"Failed to delete message {message.id} in #{message.channel.name}"
                    )

    async def _post_image_bytes(self, dest: str, data_bytes: bytes) -> Tuple[bool, Any]:
        """POST image bytes to the extraction endpoint.

        Returns (success: bool, response) where response is parsed JSON on success,
        or response text / exception on failure.
        """
        if not (self.aiohttp_session and self.server_url):
            logging.debug("No server_url configured; skipping post")
            return False, "no-server-configured"

        url = f"{self.server_url}/extract/personal_scores/"
        try:
            data = aiohttp.FormData()
            mime_type = mimetypes.guess_type(dest)[0] or "image/png"
            data.add_field(
                "images",
                data_bytes,
                filename=os.path.basename(dest),
                content_type=mime_type,
            )
            data.add_field("prompt_type", "hydra clash record")
            async with self.aiohttp_session.post(url, data=data) as resp:
                text = await resp.text()
                if 200 <= resp.status < 300:
                    try:
                        j = await resp.json()
                        logging.info(f"Extraction response for {dest}: {j}")
                        return True, j
                    except Exception:
                        logging.info(f"Non-JSON success response for {dest}: {text}")
                        return True, text
                else:
                    logging.error(
                        f"Extraction endpoint returned {resp.status} for {dest}: {text}"
                    )
                    return False, text
        except Exception as e:
            logging.exception(f"Failed to post {dest} to extraction endpoint")
            return False, e

    def _determine_injest_type(self, message: Message) -> Optional[str]:
        """Return 'hydra' or 'chimera' if message content indicates injest type, otherwise None."""
        content = (message.content or "").lower()
        if "hydra" in content:
            return "hydra"
        if "chimera" in content:
            return "chimera"
        return None

    async def _call_injest(
        self, extraction_resp: Any, injest_type: str
        , clan_token: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Call the server JSON injest endpoint for given injest_type ('hydra'|'chimera').

        Returns (success, plain_text_response)
        """
        if not (self.aiohttp_session and self.server_url):
            return False, "no-server-configured"

        if injest_type == "hydra":
            url = f"{self.server_url}/injest-hydra/"
        elif injest_type == "chimera":
            url = f"{self.server_url}/injest-chimera/"
        else:
            return False, f"unknown injest type: {injest_type}"

        # Build a minimal, safe payload. Avoid sending fields the server DB may not support (eg. 'rotation').
        def _sanitize_resp(resp: Any) -> Any:
            # Remove any 'rotation' keys from dicts (top-level or nested list items).
            if isinstance(resp, dict):
                resp = dict(resp)  # shallow copy
                resp.pop("rotation", None)
                # if nested under 'opponent_scores', sanitize that too
                if "opponent_scores" in resp and isinstance(
                    resp["opponent_scores"], dict
                ):
                    resp["opponent_scores"] = {
                        k: v
                        for k, v in resp["opponent_scores"].items()
                        if k != "rotation"
                    }
                return resp
            if isinstance(resp, list):
                new_list = []
                for item in resp:
                    if isinstance(item, dict):
                        d = dict(item)
                        d.pop("rotation", None)
                        new_list.append(d)
                    else:
                        new_list.append(item)
                return new_list
            return resp

        payload: dict = {}
        sanitized = _sanitize_resp(extraction_resp)
        payload["opponent_scores"] = sanitized
        if not payload.get("opponent_scores"):
            return False, "no opponent_scores found in extraction response"

        # add date recorded in ISO8601 UTC format (timezone-aware)
        payload["date_recorded"] = (
            datetime.now(tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        # Resolve clan value: prefer mapped value if a mapping is available,
        # otherwise use the raw token if provided. If no clan token, omit field.
        if clan_token:
            resolved = None
            try:
                resolved = self.clan_map.get(str(clan_token)) if self.clan_map else None
            except Exception:
                resolved = None
            payload["clan"] = resolved if resolved is not None else clan_token
        # If running in dry-run mode, don't call the injest endpoint; return a preview string
        if self.dry_run:
            try:
                pretty = json.dumps(payload, indent=2, default=str)
            except Exception:
                pretty = str(payload)
            return True, f"DRY RUN - would POST to {url} with payload:\n{pretty}"

        headers = {"Content-Type": "application/json"}
        async with self.aiohttp_session.post(
            url, data=json.dumps(payload), headers=headers
        ) as resp:
            text = await resp.text()
            if 200 <= resp.status < 300:
                try:
                    j = await resp.json()
                    return True, json.dumps(j)
                except Exception:
                    return True, text
            else:
                return False, f"injest endpoint returned {resp.status}: {text}"

    def _extract_clan_token(self, message: Message, injest_type_override: Optional[str]) -> Optional[str]:
        """Extract a clan token from the message content. Expected formats:
        - 'hydra 1'
        - 'chimera 2'
        If injest_type_override is provided, prefer parsing after that word; otherwise
        parse the message start.
        Returns the token string (eg. '1') or None.
        """
        content = (message.content or "").strip()
        if not content:
            return None
        # Normalize spacing
        parts = content.split()
        # If override provided, look for the override word and take next token
        if injest_type_override:
            try:
                idx = next(i for i, p in enumerate(parts) if p.lower() == injest_type_override.lower())
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            except StopIteration:
                pass
        # Otherwise, if first token is hydra/chimera, next token may be clan id
        if parts[0].lower() in ("hydra", "chimera") and len(parts) > 1:
            return parts[1]
        return None

    async def _process_and_save_message(
        self,
        message: Message,
        chan_dir: str,
        injest_type_override: Optional[str] = None,
        delete_files_after_success: bool = False,
    ) -> Tuple[int, bool, List[str]]:
        """Process a single message and save any images.

        Returns (saved_count, all_posts_success).
        all_posts_success is True when at least one image was posted and all posts returned success.
        If no images were found/saved, saved_count == 0 and all_posts_success is False.
        """
        saved = 0
        post_results: List[bool] = []
        saved_files: List[str] = []
        # Allow overriding injest type via command (context menu or slash)
        injest_type = injest_type_override or self._determine_injest_type(message)

        # Helper to mark handled when injest type missing
        async def _mark_handled_when_no_type():
            try:
                await message.channel.send("no injest type found")
            except Exception:
                logging.exception('Failed to send "no injest type found" message')

        # Attachments
        for idx, att in enumerate(message.attachments):
            filename = att.filename or f"attachment_{message.id}_{idx}"
            if is_image_filename(filename) or (
                att.content_type and att.content_type.startswith("image")
            ):
                dest = os.path.join(
                    chan_dir, f"{message.id}_{idx}_{sanitize_dirname(filename)}"
                )
                try:
                    await att.save(dest)
                    saved += 1
                    logging.debug(f"Saved attachment to {dest}")
                    try:
                        with open(dest, "rb") as fh:
                            data_bytes = fh.read()
                        ok, resp = await self._post_image_bytes(dest, data_bytes)
                        post_results.append(bool(ok))
                        resp = resp[0]
                        saved_files.append(dest)
                        try:
                            if not injest_type:
                                # Notify and treat as handled so the original message will be deleted
                                await _mark_handled_when_no_type()
                                if post_results:
                                    post_results[-1] = True
                            else:
                                # extract clan token (eg. message like 'hydra 1') and pass to injest
                                clan_token = self._extract_clan_token(message, injest_type_override)
                                inj_ok, inj_resp_text = await self._call_injest(
                                    resp, injest_type, clan_token=clan_token
                                )
                                response = json.loads(inj_resp_text) if inj_ok else {}
                                try:
                                    urlHydra = f"{self.view_server_url}/hydra/{response.get('hydra_clash_id')}/edit/"
                                    urlChimera = f"{self.view_server_url}/chimera/{response.get('chimera_clash_id')}/edit/"
                                    messageTxt = f"Clan: {clan_token} - {response.get('message')}- View at {urlHydra if injest_type == 'hydra' else urlChimera}"
                                    try:
                                        await message.channel.send(f"{message.author.mention}, {messageTxt}", file=discord.File(dest))
                                    except Exception:
                                        logging.exception("Failed to send injest response with attachment; sending text only")
                                        await message.channel.send(f"{message.author.mention}, {messageTxt}")
                                except Exception:
                                    logging.exception(
                                        "Failed to send injest response to channel"
                                    )
                                # If injest succeeded and delete_files_after_success is requested, remove saved files
                                if inj_ok and delete_files_after_success:
                                    for fpath in saved_files:
                                        try:
                                            os.remove(fpath)
                                        except Exception:
                                            logging.exception(f"Failed to delete saved file {fpath}")
                        except Exception:
                            logging.exception(
                                "Failed during injest or response posting"
                            )
                        if not ok:
                            logging.warning(f"Post failed for {dest}: {resp}")
                    except Exception:
                        logging.exception(
                            f"Failed to post {dest} to extraction endpoint"
                        )
                        post_results.append(False)
                except Exception:
                    logging.exception(f"Failed to save attachment {att.url}")

        # Embeds
        for j, emb in enumerate(message.embeds):
            url = None
            if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                url = emb.image.url
            elif getattr(emb, "thumbnail", None) and getattr(
                emb.thumbnail, "url", None
            ):
                url = emb.thumbnail.url
            if url and is_image_url(url):
                dest = os.path.join(
                    chan_dir,
                    f"{message.id}_embed_{j}_{os.path.basename(url.split('?')[0])}",
                )
                try:
                    async with self.aiohttp_session.get(url) as resp:
                        if resp.status == 200:
                            data_bytes = await resp.read()
                            with open(dest, "wb") as fh:
                                fh.write(data_bytes)
                            saved += 1
                            logging.debug(f"Saved embed image to {dest}")
                            ok, resp_obj = await self._post_image_bytes(
                                dest, data_bytes
                            )
                            post_results.append(bool(ok))
                            if not injest_type:
                                await _mark_handled_when_no_type()
                                if post_results:
                                    post_results[-1] = True
                            else:
                                inj_ok, inj_resp_text = await self._call_injest(
                                    resp_obj, injest_type
                                )
                                try:
                                    await message.channel.send(f"{message.author.mention}, {inj_resp_text}", file=discord.File(dest))
                                except Exception:
                                    logging.exception("Failed to send injest response with attachment; sending text only")
                                    try:
                                        await message.channel.send(f"{message.author.mention}, {inj_resp_text}")
                                    except Exception:
                                        logging.exception(
                                            "Failed to send injest response to channel"
                                        )
                        else:
                            logging.warning(
                                f"Failed to download embed image {url}: status {resp.status}"
                            )
                except Exception:
                    logging.exception(f"Failed to download or save embed image {url}")

        # Links in message content
        # find URLs and filter by image extension
        url_candidates = re.findall(r"(https?://[^\s]+)", message.content or "")
        for k, url in enumerate(url_candidates):
            if is_image_url(url):
                dest = os.path.join(
                    chan_dir,
                    f"{message.id}_link_{k}_{os.path.basename(url.split('?')[0])}",
                )
                try:
                    async with self.aiohttp_session.get(url) as resp:
                        if resp.status == 200:
                            data_bytes = await resp.read()
                            with open(dest, "wb") as fh:
                                fh.write(data_bytes)
                            saved += 1
                            logging.debug(f"Saved linked image to {dest}")
                            ok, resp_obj = await self._post_image_bytes(
                                dest, data_bytes
                            )
                            post_results.append(bool(ok))
                            if not injest_type:
                                await _mark_handled_when_no_type()
                                if post_results:
                                    post_results[-1] = True
                            else:
                                inj_ok, inj_resp_text = await self._call_injest(
                                    resp_obj, injest_type
                                )
                                try:
                                    await message.channel.send(f"{message.author.mention}, {inj_resp_text}", file=discord.File(dest))
                                except Exception:
                                    logging.exception("Failed to send injest response with attachment; sending text only")
                                    try:
                                        await message.channel.send(f"{message.author.mention}, {inj_resp_text}")
                                    except Exception:
                                        logging.exception(
                                            "Failed to send injest response to channel"
                                        )
                        else:
                            logging.warning(
                                f"Failed to download linked image {url}: status {resp.status}"
                            )
                except Exception:
                    logging.exception(f"Failed to download or save linked image {url}")
        all_success = bool(saved) and all(post_results) if post_results else False
        return saved, all_success, saved_files

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--guild-id", type=int, required=True)
    p.add_argument(
        "--channels", type=str, help="comma separated channel ids", default=""
    )
    p.add_argument("--output", type=str, default="./discord_images")
    p.add_argument("--history-limit", type=int, default=200)
    p.add_argument("--server-url", type=str, default="")
    p.add_argument("--token", type=str, default="")
    p.add_argument("--debug", action="store_true")
    p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Don't POST injest payloads; just show what would be sent",
    )
    p.add_argument(
        "--clan-map",
        type=str,
        default=None,
        help="JSON string or @file path mapping short clan tokens to real clan values, e.g. '{\"1\": \"clan-id\"}' or @clans.json",
    )
    return p.parse_args()

def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    channels = (
        [int(x.strip()) for x in args.channels.split(",") if x.strip()]
        if args.channels
        else None
    )
    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        try:
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env_path = os.path.join(script_dir, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.upper().startswith("DISCORD_BOT_TOKEN"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                candidate = parts[1].strip()
                                if (
                                    candidate.startswith('"')
                                    and candidate.endswith('"')
                                ) or (
                                    candidate.startswith("'")
                                    and candidate.endswith("'")
                                ):
                                    candidate = candidate[1:-1]
                                token = candidate.strip()
                                break
        except Exception:
            logging.exception("Failed to read .env fallback for DISCORD_BOT_TOKEN")

    if not token:
        raise SystemExit(
            "Discord token is required via --token or DISCORD_BOT_TOKEN env var"
        )
    channels = None
    if args.channels:
        channels = [int(x.strip()) for x in args.channels.split(",") if x.strip()]

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    intents = Intents.default()
    intents.message_content = True
    bot = ImageBot(
        guild_id=args.guild_id,
        channels=channels,
        output_dir=args.output,
        history_limit=args.history_limit,
        server_url=args.server_url,
        dry_run=args.dry_run,
        clan_map_json=args.clan_map,
        intents=intents,
        command_prefix="/",
    )
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logging.info("Shutting down")

if __name__ == "__main__":
    main()