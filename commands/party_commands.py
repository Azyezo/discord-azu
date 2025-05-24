"""
Party-related slash commands
"""
import discord
from discord import app_commands
from discord.ext import commands
from database.party_operations import party_ops
from ui.views import PartyView
from utils.helpers import parse_time_string, format_party_embed, format_party_list_embed
from config.settings import EMBED_COLOR

class PartyCommands(commands.Cog):
    """Party management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="party", description="Create a new party")
    @app_commands.describe(
        name="Party name",
        starttime="When does the party start? Use your timezone (e.g. 'Tomorrow 7PM UTC+3', 'Friday 8PM UTC-5')",
        ping="Optional: Who to ping (e.g. @everyone, @Raiders, @PvP Team)"
    )
    async def create_party(self, interaction: discord.Interaction, name: str, starttime: str, ping: str = None):
        """Create a new party"""
        try:
            # Parse the time and convert to Discord timestamp if possible
            parsed_timestamp = parse_time_string(starttime)
            
            # Create party in database
            party_id = party_ops.create_party(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                party_name=name,
                party_timestamp=parsed_timestamp,
                created_by=interaction.user.id
            )
            
            if not party_id:
                await interaction.response.send_message("❌ Failed to create party!", ephemeral=True)
                return
            
            # Get the created party data for embed
            party_data = party_ops.get_party(party_id)
            if not party_data:
                await interaction.response.send_message("❌ Failed to retrieve party data!", ephemeral=True)
                return
            
            # Create embed
            embed = format_party_embed(party_data)
            
            # Create view
            view = PartyView(party_id, interaction.user.id)
            
            # Send message with optional ping text
            await interaction.response.send_message(content=ping, embed=embed, view=view)
            
            # Save message ID
            message = await interaction.original_response()
            party_ops.update_message_id(party_id, message.id)
            
            ping_info = f" with ping: {ping}" if ping else ""
            print(f"✅ Party created: {name} at {starttime}{ping_info}")
            
        except Exception as e:
            print(f"❌ Error creating party: {e}")
            await interaction.response.send_message("❌ Failed to create party!", ephemeral=True)
    
    @app_commands.command(name="parties", description="List all parties")
    async def list_parties(self, interaction: discord.Interaction):
        """List all parties in the server"""
        try:
            print(f"🔍 User {interaction.user.display_name} requested parties for guild {interaction.guild.id}")
            
            # Get all parties for this guild
            party_list = party_ops.get_guild_parties(interaction.guild.id)
            
            print(f"📊 Query returned {len(party_list)} parties")
            
            if not party_list:
                await interaction.response.send_message("📭 No parties found!\n\n*If you just created a party, try the `/admin-debug-db` command to check the database.*", ephemeral=True)
                return
            
            # Create embed
            embed = format_party_list_embed(party_list, interaction.guild.name)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ Error listing parties: {e}")
            await interaction.response.send_message("❌ Failed to list parties! Try `/admin-debug-db` to check the database.", ephemeral=True)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(PartyCommands(bot))