"""
user_permissions.py

Utility to inspect a user's permissions in a guild and list channels they can access.

Usage:
  python user_permissions.py [properties_file] <user_identifier>

Where <user_identifier> can be:
  - A numeric user ID (recommended)
  - A mention like <@123456789012345678>
  - A username with discriminator like UserName#1234 (best-effort; may require privileged intents)

If a properties file is provided (e.g., bots/bot1.properties) the script will load it and apply the keys to environment variables.
Required environment keys: DISCORD_BOT_TOKEN or DISCORD_TOKEN, GUILD_ID

Notes:
  - This script needs the Members intent to fetch guild members reliably.
  - For large guilds or name#discriminator lookups you may need privileged intent enabled in the Developer Portal and in your bot's intents.
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Optional

import discord


def load_properties_config(path: str) -> dict:
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
        os.environ[k] = v


def parse_user_identifier(identifier: str) -> Optional[int]:
    """Return user ID if identifier is a mention or numeric ID; otherwise None."""
    # Mention formats: <@1234> or <@!1234>
    m = re.match(r"^<@!?(\d+)>$", identifier)
    if m:
        return int(m.group(1))

    if identifier.isdigit():
        return int(identifier)

    return None


def parse_channel_identifier(identifier: str) -> Optional[int]:
    """Return channel ID if identifier is a channel mention or explicit channel:<id> string; otherwise None.

    Supported formats:
      - A channel mention: <#123456789012345678>
      - An explicit prefix: channel:123456789012345678 or c:123456789012345678
    Note: plain numeric IDs are treated as user IDs by default to avoid ambiguity. If you need to
    specify a numeric channel ID, prefix it with "channel:" or "c:".
    """
    if not identifier:
        return None

    m = re.match(r"^<#(\d+)>$", identifier)
    if m:
        return int(m.group(1))

    m2 = re.match(r"^(?:channel:|c:)(\d+)$", identifier)
    if m2:
        return int(m2.group(1))

    return None


async def main():
    # CLI args: optional properties file, then optional user identifier
    args = sys.argv[1:]
    props = None
    user_ident = None

    # If first arg is a file that exists, use it as properties file
    if len(args) >= 1 and Path(args[0]).exists():
        props = args[0]
        # second arg (if present) is identifier (user or channel)
        if len(args) >= 2:
            identifier = args[1]
            # prefer explicit channel: prefix or channel mention
            channel_id = parse_channel_identifier(identifier)
            if channel_id:
                user_ident = None
                channel_ident = channel_id
            else:
                user_ident = identifier
                channel_ident = None
    elif len(args) >= 1:
        # First arg is not a properties file, treat it as identifier
        identifier = args[0]
        channel_id = parse_channel_identifier(identifier)
        if channel_id:
            user_ident = None
            channel_ident = channel_id
        else:
            user_ident = identifier
            channel_ident = None
    else:
        # No args provided -> list roles and channels for the configured guild
        user_ident = None
        channel_ident = None

    if props:
        try:
            apply_properties_to_env(props)
            print(f"Loaded properties from: {props}")
        except Exception as e:
            print(f"Failed to load properties '{props}': {e}")
            return

    token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
    guild_id = int(os.getenv('GUILD_ID', '0') or 0)

    if not token:
        print("DISCORD_BOT_TOKEN or DISCORD_TOKEN not set. Provide a properties file or set env vars.")
        return
    if not guild_id:
        print("GUILD_ID not set. Provide it in your properties file or environment.")
        return

    # Intents: members intent required to fetch member details
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as: {client.user} (ID: {client.user.id})")

        try:
            guild = await client.fetch_guild(guild_id)
        except Exception as e:
            print(f"Failed to fetch guild {guild_id}: {e}")
            await client.close()
            return

        # If a channel identifier was provided, stream all messages from that channel
        if 'channel_ident' in locals() and channel_ident is not None:
            print(f"\nFetching messages for channel id: {channel_ident}")
            try:
                # Try to fetch the channel (works for guild channels and many DM/channel types)
                ch = client.get_channel(channel_ident) or await client.fetch_channel(channel_ident)
            except Exception as e:
                print(f"Failed to fetch channel {channel_ident}: {e}")
                await client.close()
                return

            if ch is None:
                print(f"Channel {channel_ident} not found.")
                await client.close()
                return

            out_name = f"messages_{channel_ident}.log"
            count = 0
            try:
                with open(out_name, 'w', encoding='utf-8') as out_f:
                    async for msg in ch.history(limit=None, oldest_first=True):
                        count += 1
                        ts = msg.created_at.isoformat() if getattr(msg, 'created_at', None) else 'unknown'
                        author = f"{getattr(msg.author, 'name', str(msg.author))}#{getattr(msg.author, 'discriminator', '')} ({getattr(msg.author, 'id', 'unknown')})"
                        content = (msg.content or '').replace('\n', '\\n')
                        line = f"[{ts}] {author}: {content}\n"
                        out_f.write(line)
                        # attachments
                        if getattr(msg, 'attachments', None):
                            for a in msg.attachments:
                                out_f.write(f"    attachment: {getattr(a, 'url', str(a))}\n")
                        if count % 1000 == 0:
                            print(f"  fetched {count} messages...")
                print(f"Finished fetching messages: {count} messages written to {out_name}")
            except Exception as e:
                print(f"Error while fetching/writing messages: {e}")
            await client.close()
            return

        # If no user identifier was provided, print all roles and channels and exit
        if user_ident is None:
            print(f"\nListing roles and channels for guild: {guild.name} (ID: {guild.id})")

            # Try to get cached guild object to access roles/channels properties
            guild_obj = client.get_guild(guild_id) or guild

            # Roles
            try:
                roles = getattr(guild_obj, 'roles', [])
                print(f"\nRoles ({len(roles)}):")
                for r in sorted(roles, key=lambda x: getattr(x, 'position', 0), reverse=True):
                    try:
                        print(f"  • {r.name} (ID: {r.id}) position={r.position} hoist={r.hoist}")
                    except Exception:
                        print(f"  • {r}")
            except Exception as e:
                print(f"Failed to enumerate roles: {e}")

            # Channels
            try:
                channels = getattr(guild_obj, 'channels', [])
                print(f"\nChannels ({len(channels)}):")
                for ch in sorted(channels, key=lambda c: (getattr(c, 'position', 0) or 0)):
                    try:
                        type_name = ch.type.name
                    except Exception:
                        type_name = str(getattr(ch, 'type', 'unknown'))
                    print(f"  • {ch.name} (ID: {ch.id}) [{type_name}]")
            except Exception as e:
                print(f"Failed to enumerate channels: {e}")

            await client.close()
            return

    # Resolve member
        member = None
        numeric_id = parse_user_identifier(user_ident)
        if numeric_id:
            try:
                member = await guild.fetch_member(numeric_id)
            except discord.NotFound:
                print(f"Member with ID {numeric_id} not found in guild {guild_id}.")
            except Exception as e:
                # fetch_member may fail if not in cache/permissions; try client.get_user fallback
                print(f"Error fetching member by ID: {e}")

        if member is None and '#' in user_ident:
            # Try name#discriminator lookup (may require privileged intent)
            name, discrim = user_ident.rsplit('#', 1)
            print("Looking up by username#discriminator (may be slow or require privileged intents)...")
            try:
                # Note: fetch_members may return an iterator or a list depending on version
                members_iter = await guild.fetch_members(limit=1000).flatten()
                for m in members_iter:
                    if m.name == name and m.discriminator == discrim:
                        member = m
                        break
            except Exception as e:
                print(f"Failed to enumerate members: {e}")

        if member is None:
            print("Could not resolve member. Try providing a numeric user ID or mention.")
            await client.close()
            return

        # Print member summary
        print(f"\nMember: {member} (ID: {member.id})")
        print(f"Top role: {member.top_role}")
        print(f"Joined at: {member.joined_at}")

        # Guild-level permissions
        guild_perms = member.guild_permissions
        print("\nGuild permissions:")

        # List common permission attributes if True
        perm_attrs = [
            'create_instant_invite', 'kick_members', 'ban_members', 'administrator', 'manage_channels',
            'manage_guild', 'add_reactions', 'view_audit_log', 'priority_speaker', 'stream', 'view_channel',
            'send_messages', 'send_tts_messages', 'manage_messages', 'embed_links', 'attach_files',
            'read_message_history', 'mention_everyone', 'use_external_emojis', 'view_guild_insights',
            'connect', 'speak', 'mute_members', 'deafen_members', 'move_members', 'use_vad',
            'change_nickname', 'manage_nicknames', 'manage_roles', 'manage_webhooks', 'manage_emojis_and_stickers'
        ]

        for attr in perm_attrs:
            val = getattr(guild_perms, attr, None)
            if val:
                print(f"  • {attr}: {val}")

        # Now iterate channels and compute channel-level permissions
        accessible_channels = []
        print("\nScanning channels for view permission (this may take a moment)...")

        guild_obj = client.get_guild(guild_id)
        if guild_obj:
            for ch in guild_obj.channels:
                try:
                    perms = ch.permissions_for(member)
                    if perms.view_channel:
                        accessible_channels.append(ch)
                except Exception:
                    # Some channel types may error on permissions_for; skip
                    continue
        else:
            print("Warning: guild not in cache; channel enumeration may be limited.")

        # Print results
        print(f"\nChannels {member} can view: {len(accessible_channels)}")
        for ch in accessible_channels:
            try:
                type_name = ch.type.name
            except Exception:
                type_name = str(getattr(ch, 'type', 'unknown'))
            print(f"  • {ch.name} (ID: {ch.id}) [{type_name}]")

        await client.close()

    # Run the client (start will connect and call on_ready)
    try:
        await client.start(token)
    except Exception as e:
        print(f"Error running client: {e}")


if __name__ == '__main__':
    asyncio.run(main())
