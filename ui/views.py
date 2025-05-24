"""
Discord UI Views
"""
import discord
from typing import Optional
from database.party_operations import party_ops
from config.settings import EMBED_COLOR, DEFAULT_TANK_SLOTS, DEFAULT_HEALER_SLOTS, DEFAULT_DPS_SLOTS
from utils.helpers import format_party_embed
from ui.modals import PartyEditModal

class PartyView(discord.ui.View):
    """View for party interaction buttons"""
    
    def __init__(self, party_id: str, creator_id: Optional[int]):
        super().__init__(timeout=None)
        self.party_id = party_id
        self.creator_id = creator_id
    
    @discord.ui.button(label='Join as Tank', style=discord.ButtonStyle.primary, emoji='🛡️', row=0)
    async def join_tank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.join_role(interaction, 'tank')
    
    @discord.ui.button(label='Join as Healer', style=discord.ButtonStyle.success, emoji='💚', row=0)
    async def join_healer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.join_role(interaction, 'healer')
    
    @discord.ui.button(label='Join as DPS', style=discord.ButtonStyle.danger, emoji='⚔️', row=0)
    async def join_dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.join_role(interaction, 'dps')
    
    @discord.ui.button(label="Can't Attend", style=discord.ButtonStyle.secondary, emoji='❌', row=1)
    async def cant_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.join_role(interaction, 'cant_attend')
    
    @discord.ui.button(label='Leave Party', style=discord.ButtonStyle.secondary, emoji='🚪', row=1)
    async def leave_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get party data
            party_data = party_ops.get_party(self.party_id)
            if not party_data:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            members = party_data.get('members', {})
            user_id_str = str(interaction.user.id)
            
            # Check if user is in party
            if user_id_str not in members:
                await interaction.response.send_message("❌ You're not in this party!", ephemeral=True)
                return
            
            # Remove user from party
            success = party_ops.remove_member(self.party_id, interaction.user.id)
            
            if success:
                await interaction.response.send_message("🚪 **Left the party** - You're no longer signed up.", ephemeral=True)
                await self.update_embed(interaction)
            else:
                await interaction.response.send_message("❌ Failed to leave party!", ephemeral=True)
            
        except Exception as e:
            print(f"Error in leave_party: {e}")
            await interaction.response.send_message("❌ Failed to leave party!", ephemeral=True)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user can interact with buttons"""
        # For edit button, only show to creator
        if interaction.data.get('custom_id') == 'edit_party':
            return interaction.user.id == self.creator_id
        return True
    
    @discord.ui.button(label='Edit Party', style=discord.ButtonStyle.primary, emoji='✏️', row=2, custom_id='edit_party')
    async def edit_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get party data
            party_data = party_ops.get_party(self.party_id)
            if not party_data:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            modal = PartyEditModal(
                self.party_id,
                party_data.get('party_name', ''),
                party_data.get('party_timestamp', ''),
                party_data.get('tank_slots', DEFAULT_TANK_SLOTS),
                party_data.get('healer_slots', DEFAULT_HEALER_SLOTS),
                party_data.get('dps_slots', DEFAULT_DPS_SLOTS)
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in edit_party: {e}")
            await interaction.response.send_message("❌ Edit failed!", ephemeral=True)
    
    async def join_role(self, interaction: discord.Interaction, role: str):
        """Handle joining a party with a specific role"""
        try:
            # Get party data
            party_data = party_ops.get_party(self.party_id)
            if not party_data:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            # Handle "can't attend" role differently (no slot limits)
            if role != 'cant_attend':
                # Check if role has slots
                role_slots = {
                    'tank': party_data.get('tank_slots', DEFAULT_TANK_SLOTS),
                    'healer': party_data.get('healer_slots', DEFAULT_HEALER_SLOTS),
                    'dps': party_data.get('dps_slots', DEFAULT_DPS_SLOTS)
                }
                
                max_slots = role_slots.get(role, 0)
                if max_slots == 0:
                    role_name = role.title()
                    await interaction.response.send_message(f"❌ No {role_name} slots available in this party!", ephemeral=True)
                    return
                
                # Check if role is full
                if party_ops.is_role_full(party_data, role):
                    role_name = role.title()
                    counts = party_ops.get_member_counts_by_role(party_data)
                    current_count = counts.get(role, 0)
                    await interaction.response.send_message(f"❌ {role_name} slots are full! ({current_count}/{max_slots})", ephemeral=True)
                    return
            
            # Add/update user in party
            success = party_ops.add_member(self.party_id, interaction.user.id, interaction.user.display_name, role)
            
            if success:
                role_messages = {
                    'tank': '🛡️ **Joined as Tank!**',
                    'healer': '💚 **Joined as Healer!**', 
                    'dps': '⚔️ **Joined as DPS!**',
                    'cant_attend': '❌ **Marked as Can\'t Attend**'
                }
                
                await interaction.response.send_message(role_messages[role], ephemeral=True)
                await self.update_embed(interaction)
            else:
                await interaction.response.send_message("❌ Failed to join party!", ephemeral=True)
            
        except Exception as e:
            print(f"Error in join_role: {e}")
            await interaction.response.send_message("❌ Failed to join party!", ephemeral=True)
    
    async def update_embed(self, interaction: discord.Interaction):
        """Update the party embed with current data"""
        try:
            # Get party data
            party_data = party_ops.get_party(self.party_id)
            if not party_data:
                return
            
            print(f"Party {self.party_id} members: {party_data.get('members', {})}")
            
            # Create embed
            embed = format_party_embed(party_data)
            
            # Update original message
            channel_id = party_data.get('channel_id')
            message_id = party_data.get('message_id')
            
            if channel_id and message_id:
                try:
                    # Use the interaction's client instead of importing bot
                    channel = interaction.client.get_channel(channel_id)
                    if channel:
                        message = await channel.fetch_message(message_id)
                        await message.edit(embed=embed, view=self)
                except Exception as e:
                    print(f"Failed to update message: {e}")
                    
        except Exception as e:
            print(f"Error updating embed: {e}")