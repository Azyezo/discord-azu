"""
Discord UI Modals
"""
import discord
import datetime
from firebase_admin import firestore
from database.party_operations import party_ops
from config.settings import MAX_PARTY_NAME_LENGTH, MAX_STARTTIME_LENGTH
from utils.helpers import parse_time_string

class PartyEditModal(discord.ui.Modal, title="✏️ Edit Party"):
    """Modal for editing party details"""
    
    def __init__(self, party_id: str, current_name: str, current_starttime: str, 
                 current_tanks: int, current_healers: int, current_dps: int):
        super().__init__()
        self.party_id = party_id
        
        self.name_input = discord.ui.TextInput(
            label="🎮 Party Name",
            default=current_name,
            max_length=MAX_PARTY_NAME_LENGTH
        )
        self.add_item(self.name_input)
        
        self.starttime_input = discord.ui.TextInput(
            label="🕐 Party Start Time",
            placeholder="When does the party start? (e.g. 'Tomorrow 7PM', 'Friday 8PM')",
            default=current_starttime or "",
            required=False,
            max_length=MAX_STARTTIME_LENGTH
        )
        self.add_item(self.starttime_input)
        
        self.tank_input = discord.ui.TextInput(
            label="🛡️ Tank Slots",
            default=str(current_tanks),
            max_length=2
        )
        self.add_item(self.tank_input)
        
        self.healer_input = discord.ui.TextInput(
            label="💚 Healer Slots",
            default=str(current_healers),
            max_length=2
        )
        self.add_item(self.healer_input)
        
        self.dps_input = discord.ui.TextInput(
            label="⚔️ DPS Slots",
            default=str(current_dps),
            max_length=2
        )
        self.add_item(self.dps_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            # Validate slot inputs
            try:
                tank_slots = int(self.tank_input.value)
                healer_slots = int(self.healer_input.value)
                dps_slots = int(self.dps_input.value)
            except ValueError:
                await interaction.response.send_message("❌ Please enter valid numbers for slots!", ephemeral=True)
                return
            
            # Parse the start time if provided
            starttime_value = None
            if self.starttime_input.value.strip():
                starttime_value = parse_time_string(self.starttime_input.value.strip())
            
            # Update party in database
            updates = {
                'party_name': self.name_input.value,
                'party_timestamp': starttime_value,
                'tank_slots': tank_slots,
                'healer_slots': healer_slots,
                'dps_slots': dps_slots
            }
            
            success = party_ops.update_party(self.party_id, updates)
            
            if success:
                await interaction.response.send_message("✅ Party updated successfully!", ephemeral=True)
                
                # Get updated party data and refresh the view
                party_data = party_ops.get_party(self.party_id)
                if party_data:
                    embed = format_party_embed(party_data)
                    
                    # Create a fresh view with the same party ID and creator
                    from ui.views import PartyView
                    creator_id = party_data.get('created_by')
                    view = PartyView(self.party_id, creator_id)
                    
                    # Update the original message
                    channel_id = party_data.get('channel_id')
                    message_id = party_data.get('message_id')
                    
                    if channel_id and message_id:
                        try:
                            channel = interaction.client.get_channel(channel_id)
                            if channel:
                                message = await channel.fetch_message(message_id)
                                await message.edit(embed=embed, view=view)
                        except Exception as e:
                            print(f"Failed to update message after edit: {e}")
            else:
                await interaction.response.send_message("❌ Update failed! Party not found.", ephemeral=True)
            
        except Exception as e:
            print(f"Error in PartyEditModal: {e}")
            await interaction.response.send_message("❌ Update failed! Please try again.", ephemeral=True)