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
        starttime="When does the party start? Use UTC time (e.g. 'Tomorrow 4PM UTC', 'Friday 5PM UTC')"
    )
    async def create_party(self, interaction: discord.Interaction, name: str, starttime: str):
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
            
            # Send message
            await interaction.response.send_message(embed=embed, view=view)
            
            # Save message ID
            message = await interaction.original_response()
            party_ops.update_message_id(party_id, message.id)
            
            print(f"✅ Party created: {name} at {starttime}")
            
        except Exception as e:
            print(f"❌ Error creating party: {e}")
            await interaction.response.send_message("❌ Failed to create party!", ephemeral=True)
    
    @app_commands.command(name="parties", description="List all parties")
    async def list_parties(self, interaction: discord.Interaction):
        """List all parties in the server"""
        try:
            # Get all parties for this guild
            party_list = party_ops.get_guild_parties(interaction.guild.id)
            
            if not party_list:
                await interaction.response.send_message("📭 No parties found!", ephemeral=True)
                return
            
            # Create embed
            embed = format_party_list_embed(party_list, interaction.guild.name)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ Error listing parties: {e}")
            await interaction.response.send_message("❌ Failed to list parties!", ephemeral=True)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(PartyCommands(bot))