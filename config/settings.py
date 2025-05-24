"""
Configuration settings for the Discord Party Bot
"""
import os
import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
COMMAND_PREFIX = '!'

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT = os.getenv('FIREBASE_SERVICE_ACCOUNT')

# Discord Intents
def get_bot_intents():
    """Configure and return Discord intents"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents

# Party Configuration Constants
DEFAULT_TANK_SLOTS = 2
DEFAULT_HEALER_SLOTS = 2
DEFAULT_DPS_SLOTS = 4

# Embed Colors
EMBED_COLOR = 0x5865F2
ERROR_COLOR = 0xFF5555
SUCCESS_COLOR = 0x57F287

# Validation Constants
MAX_PARTY_NAME_LENGTH = 50
MAX_STARTTIME_LENGTH = 100
MAX_SLOT_VALUE = 99