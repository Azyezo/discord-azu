"""
Discord bot event handlers
"""
import discord
from discord.ext import commands
from database.firebase_client import firebase_client
from database.party_operations import party_ops
from ui.views import PartyView

class BotEvents(commands.Cog):
    """Bot event handlers"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready"""
        print(f'🎮 {self.bot.user} is online!')
        
        # Initialize Firebase
        firebase_client.initialize()
        
        try:
            # Sync slash commands
            synced = await self.bot.tree.sync()
            print(f"⚡ Synced {len(synced)} commands")
        except Exception as e:
            print(f"❌ Sync failed: {e}")
        
        # Restore views after restart
        await self.restore_views()
    
    async def restore_views(self):
        """Restore views for all active parties after bot restart"""
        try:
            # Get all parties with message IDs
            parties = party_ops.get_parties_with_message_ids()
            
            restored_count = 0
            for party_data in parties:
                try:
                    party_id = party_data['id']
                    channel_id = party_data.get('channel_id')
                    message_id = party_data.get('message_id')
                    creator_id = party_data.get('created_by')
                    
                    if channel_id and message_id:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            message = await channel.fetch_message(message_id)
                            view = PartyView(party_id, creator_id)
                            await message.edit(view=view)
                            restored_count += 1
                except Exception as e:
                    print(f"Failed to restore view for party {party_data.get('id', 'unknown')}: {e}")
            
            print(f"✅ Restored {restored_count} party views")
            
        except Exception as e:
            print(f"❌ Failed to restore views: {e}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(BotEvents(bot))