"""
Discord Party Management Bot
Main entry point and bot setup
"""
import asyncio
import sys
from discord.ext import commands
from config.settings import DISCORD_TOKEN, COMMAND_PREFIX, get_bot_intents

# Create bot instance
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=get_bot_intents())

async def load_extensions():
    """Load all bot extensions/cogs"""
    extensions = [
        'events.bot_events',
        'commands.party_commands',
        'commands.admin_commands'
    ]
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded {extension}")
        except Exception as e:
            print(f"❌ Failed to load {extension}: {e}")
            return False
    
    return True

async def main():
    """Main function to start the bot"""
    if not DISCORD_TOKEN:
        print("❌ No Discord token found in environment variables!")
        sys.exit(1)
    
    # Load extensions
    success = await load_extensions()
    if not success:
        print("❌ Failed to load extensions!")
        sys.exit(1)
    
    # Start the bot
    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutdown completed")