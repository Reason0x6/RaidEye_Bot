# 🤖 RaidEye Discord Bot

A powerful, modular Discord bot built with discord.py that specializes in raid management, clan activities, and image processing for gaming communities. The bot features modern slash commands, context menus, and seamless integration with RaidEye server for advanced image analysis.

## ✨ Features

### 🎯 **Core Functionality**
- **Modern Slash Commands**: Full Discord slash command support with autocomplete
- **Context Menus**: Right-click any message to process images instantly
- **Image Processing**: Advanced image analysis for clash records and statistics
- **Clan Management**: Comprehensive clan information and statistics system
- **Modular Design**: Easy to extend with new commands and features
- **Auto-sync**: Automatically syncs commands with Discord on startup

### 🖼️ **Image Processing**
- **Hydra & Chimera Clash Processing**: Extract data from game screenshots
- **Batch Processing**: Process multiple images from message history
- **Direct Upload**: Attach images directly to slash commands
- **URL Analysis**: Process images from any web URL
- **Smart Detection**: Automatic clash type detection from message content

### 🏰 **Clan Features**
- **Real-time Statistics**: Live clan stats and performance metrics
- **Member Tracking**: Monitor clan member activity and performance
- **Raid Scheduling**: Track and display raid schedules and events
- **Multi-clan Support**: Handle multiple clans with token mapping

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Discord application with bot token
- RaidEye server (for image processing features)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd RaidEye_Discord_bot
   ```

2. **Create a virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```powershell
   # Copy the template
   copy .env.template .env
   
   # Edit .env with your actual values
   notepad .env
   ```

5. **Set up Discord bot**:
   - Go to https://discord.com/developers/applications
   - Create new application → Bot section → Copy token
   - Add token to your `.env` file

6. **Generate invite link**:
   ```powershell
   python generate_invite.py
   ```

7. **Run the bot**:
   ```powershell
   python start.py
   ```

## 📋 Available Commands

### 🏛️ **Clash Processing**
| Command | Description | Usage |
|---------|-------------|-------|
| `/hydra` | Process Hydra clash images | `clan_token`, `image`, `message_link`, `dry_run` |
| `/chimera` | Process Chimera clash images | `clan_token`, `image`, `message_link`, `dry_run` |
| **Context Menu** | Right-click → "Process as Hydra/Chimera" | Opens modal for clan input |

### 📊 **Clan Management**
| Command | Description | Usage |
|---------|-------------|-------|
| `/clan-stats` | Get detailed clan statistics | `include_image`, `message_link` |
| `/clan-info-query` | Query specific clan information | `query_type`, `clan_filter` |
| `/server-status` | Check RaidEye server connectivity | - |

### 🖼️ **Image Processing**
| Command | Description | Usage |
|---------|-------------|-------|
| `/scan-images` | Scan messages for images | `channel`, `limit`, `image_type`, `save_locally` |
| `/process-batch` | Process multiple images | `channel`, `limit`, `analysis_type`, `auto_detect_type` |
| `/analyze-url` | Analyze image from URL | `image_url`, `analysis_type` |

### ℹ️ **Information & Utilities**
| Command | Description | Usage |
|---------|-------------|-------|
| `/info` | Bot information and stats | - |
| `/ping` | Check bot response time | - |
| `/help` | Display available commands | - |
| `/server-info` | Server information | - |
| `/setup-check` | Verify bot configuration | - |

### 🔧 **Admin Commands** (Bot Owner Only)
| Command | Description | Usage |
|---------|-------------|-------|
| `!sync` | Manually sync slash commands | - |
| `!clear` | Clear all slash commands | - |
| `!list` | List current slash commands | - |

## 🏗️ Project Structure

```
RaidEye_Discord_bot/
├── 📁 commands/                    # Command modules
│   ├── 🔍 clash_processing.py     # Hydra/Chimera processing
│   ├── 📊 clan_stats.py           # Clan statistics
│   ├── 🖼️ image_processing.py     # Image analysis
│   ├── 🖱️ context_menus.py        # Right-click commands
│   ├── ℹ️ info.py                  # Bot information
│   ├── 🏰 clan.py                 # Clan management
│   ├── 🖥️ server.py               # Server utilities
│   └── 📝 _template.py            # Command template
├── 🤖 bot.py                      # Main bot file
├── ⚙️ config.py                   # Configuration management
├── 🔧 start.py                    # Startup script with checks
├── 🔗 generate_invite.py          # Bot invite link generator
├── 🗂️ manage_commands.py          # Command management utility
├── 🧹 clear_commands.py           # Command clearing utility
├── 📄 requirements.txt            # Python dependencies
├── 🔒 .env.template               # Environment template
├── 📚 README.md                   # This file
├── 📋 COMMANDS_MIGRATION.md       # Migration guide
└── 🗃️ clans.json                  # Clan data storage
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file using `.env.template` as a guide:

```env
# Required
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
MAIN_CHANNEL_ID=your_main_channel_id_here
RAIDEYE_SERVER=http://localhost:8000

# Optional
BOT_PREFIX=!
DEBUG_MODE=false
DISCORD_CLAN_MAP={"1": "main_clan", "2": "sister_clan"}
```

### Clan Mapping

Map short tokens to full clan names for easier user input:

```json
{
  "1": "Dragons of Fire",
  "2": "Phoenix Rising", 
  "3": "Shadow Wolves"
}
```

Users can then type `/hydra clan_token:1` instead of the full clan name.

## 🎮 Usage Examples

### Processing Clash Results

```bash
# Direct image upload (easiest)
/hydra clan_token:1 image:[attach_screenshot] dry_run:false

# From message link
/chimera clan_token:2 message_link:https://discord.com/channels/.../...

# Right-click method
Right-click message → Apps → "Process as Hydra" → Enter clan token
```

### Batch Processing

```bash
# Scan recent messages for clash images
/scan-images channel:#raids limit:50 image_type:Clash Records Only

# Process multiple images with auto-detection
/process-batch channel:#results limit:20 auto_detect_type:true
```

### Getting Statistics

```bash
# Get clan stats with image
/clan-stats include_image:true message_link:https://discord.com/...

# Query specific information
/clan-info-query query_type:Performance Stats clan_filter:Dragons
```

## 🔧 Adding New Commands

The bot uses a modular command system. To add new commands:

1. **Create a new file** in `commands/` directory:

```python
import discord
from discord.ext import commands
from discord import app_commands

class YourCommands(commands.Cog):
    """Description of your command group"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="your-command", description="Command description")
    async def your_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello World!")

async def setup(bot):
    await bot.add_cog(YourCommands(bot))
```

2. **Restart the bot** - Commands are auto-loaded on startup

## 🛠️ Management Tools

### Command Management
```powershell
# Interactive command manager
python manage_commands.py

# Quick command clearing
python clear_commands.py

# Startup with checks
python start.py
```

### Bot Invite
```powershell
# Generate proper invite link with all permissions
python generate_invite.py
```

## 🔍 Troubleshooting

### Common Issues

**Commands not showing in Discord:**
- Verify bot has `applications.commands` scope
- Check server permissions
- Use `!sync` command to manually sync

**Image processing fails:**
- Verify `RAIDEYE_SERVER` is accessible
- Check `/server-status` command
- Ensure images are valid formats (PNG, JPG, etc.)

**Environment issues:**
- Verify `.env` file exists and has correct values
- Check `python start.py` for configuration validation
- Enable `DEBUG_MODE=true` for detailed logging

### Debug Commands

```powershell
# Check bot configuration
/setup-check

# Test server connectivity  
/server-status

# List current commands
!list

# View bot information
/info
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-feature`
3. **Follow existing patterns** in `commands/` directory
4. **Test thoroughly** with dry run mode
5. **Submit pull request**

### Code Style
- Use Discord embeds for rich formatting
- Include proper error handling
- Add command descriptions and parameter info
- Follow existing naming conventions

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

- **Documentation**: Check `COMMANDS_MIGRATION.md` for detailed command info
- **Issues**: Report bugs via GitHub issues
- **Discord**: Join our support server (link in bot info)

---

Built with ❤️ for gaming communities using Discord.py and modern Python practices.