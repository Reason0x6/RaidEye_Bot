#!/usr/bin/env python3
"""
Quick start script for the RaidEye Discord Bot

This script provides an easy way to run the bot with proper setup checks.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required!")
        print(f"Current version: {sys.version}")
        return False
    return True

def check_virtual_environment():
    """Check if we're in a virtual environment"""
    return hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import discord
        import aiohttp
        import dotenv
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False

def check_bot_token():
    """Check if bot token is configured"""
    # Load .env file first
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ Discord bot token not found!")
        print("\nPlease set your bot token using one of these methods:")
        print("1. Set environment variable: $env:DISCORD_BOT_TOKEN='your_token_here'")
        print("2. Create a .env file with: DISCORD_BOT_TOKEN=your_token_here")
        print("\nGet your bot token from: https://discord.com/developers/applications")
        return False
    print(f"Token found: {token[:20]}...")  # Show first 20 characters for verification
    return True

def main():
    """Main startup function"""
    print("🤖 RaidEye Discord Bot - Startup Check")
    print("=" * 40)
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_environment),
        ("Dependencies", check_dependencies),
        ("Bot Token", check_bot_token),
    ]
    
    failed_checks = []
    for check_name, check_func in checks:
        print(f"Checking {check_name}...", end=" ")
        if check_func():
            print("✅")
        else:
            print("❌")
            failed_checks.append(check_name)
    
    if failed_checks:
        print(f"\n❌ {len(failed_checks)} check(s) failed. Please fix the issues above.")
        return False
    
    print("\n✅ All checks passed! Starting the bot...")
    print("=" * 40)
    
    # Import and run the bot
    try:
        from bot import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()