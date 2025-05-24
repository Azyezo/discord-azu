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
                
                # Update embed - import here to avoid circular dependency
                from ui.views import PartyView
                view = PartyView(self.party_id, None)
                await view.update_embed(interaction)
            else:
                await interaction.response.send_message("❌ Update failed! Party not found.", ephemeral=True)
            
        except Exception as e:
            print(f"Error in PartyEditModal: {e}")
            await interaction.response.send_message("❌ Update failed! Please try again.", ephemeral=True)