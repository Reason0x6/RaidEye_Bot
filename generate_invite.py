"""
Bot Invite Link Generator

Run this script to generate the correct invite link for your Discord bot.
"""

import discord
from config import DISCORD_BOT_TOKEN

def generate_invite_link():
    """Generate the bot invite link with proper permissions"""
    
    # Required permissions for the bot
    permissions = discord.Permissions(
        send_messages=True,
        use_application_commands=True,  # This is crucial for slash commands
        embed_links=True,
        read_message_history=True,
        add_reactions=True,
        manage_messages=True,  # For announcement command
        view_channel=True
    )
    
    # You need to get your bot's client ID from the Discord Developer Portal
    print("🔗 Bot Invite Link Generator")
    print("=" * 40)
    print("\nTo get your bot's Client ID:")
    print("1. Go to https://discord.com/developers/applications")
    print("2. Select your bot application")
    print("3. Copy the 'Application ID' from the General Information tab")
    
    client_id = input("\nEnter your bot's Client ID: ").strip()
    
    if not client_id.isdigit():
        print("❌ Invalid Client ID. It should be a number.")
        return
    
    # Generate the invite URL
    invite_url = discord.utils.oauth_url(
        client_id=int(client_id),
        permissions=permissions,
        scopes=('bot', 'applications.commands')  # Both scopes are needed
    )
    
    print(f"\n✅ Generated invite link:")
    print(f"{invite_url}")
    print("\n📋 This link includes:")
    print("• Bot scope (for the bot to join)")
    print("• Applications.commands scope (for slash commands)")
    print("• Required permissions for all bot features")
    print("\n🚀 Use this link to invite your bot to your server!")

if __name__ == "__main__":
    generate_invite_link()