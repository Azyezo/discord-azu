import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
import json

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Firebase
def init_firebase():
    try:
        # Use service account JSON from environment variable
        service_account_info = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        
        global db
        db = firestore.client()
        print("✅ Firebase initialized!")
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise e

class PartyEditModal(discord.ui.Modal, title="✏️ Edit Party"):
    def __init__(self, party_id, current_name, current_starttime, current_tanks, current_healers, current_dps):
        super().__init__()
        self.party_id = party_id
        
        self.name_input = discord.ui.TextInput(
            label="🎮 Party Name",
            default=current_name,
            max_length=50
        )
        self.add_item(self.name_input)
        
        self.starttime_input = discord.ui.TextInput(
            label="🕐 Party Start Time",
            placeholder="When does the party start? (e.g. 'Tomorrow 7PM', 'Friday 8PM')",
            default=current_starttime or "",
            required=False,
            max_length=100
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
        try:
            tank_slots = int(self.tank_input.value)
            healer_slots = int(self.healer_input.value)
            dps_slots = int(self.dps_input.value)
            
            # Parse the start time if provided
            starttime_value = None
            if self.starttime_input.value.strip():
                try:
                    import dateutil.parser
                    dt = dateutil.parser.parse(self.starttime_input.value, fuzzy=True)
                    
                    # Handle past times
                    if dt < datetime.datetime.now():
                        if "tomorrow" in self.starttime_input.value.lower():
                            dt = dt.replace(year=datetime.datetime.now().year, month=datetime.datetime.now().month, day=datetime.datetime.now().day) + datetime.timedelta(days=1)
                        elif dt.time() > datetime.datetime.now().time():
                            pass
                        else:
                            dt = dt.replace(year=datetime.datetime.now().year + 1)
                    
                    starttime_value = int(dt.timestamp())
                    
                except Exception:
                    # If parsing fails, store as text
                    starttime_value = self.starttime_input.value.strip()
            
            # Update party in Firebase
            party_ref = db.collection('parties').document(self.party_id)
            party_ref.update({
                'party_name': self.name_input.value,
                'party_timestamp': starttime_value,
                'tank_slots': tank_slots,
                'healer_slots': healer_slots,
                'dps_slots': dps_slots,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            await interaction.response.send_message("✅ Party updated successfully!", ephemeral=True)
            
            # Update embed
            view = PartyView(self.party_id, None)
            await view.update_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for slots!", ephemeral=True)
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("❌ Update failed! Please try again.", ephemeral=True)

class PartyView(discord.ui.View):
    def __init__(self, party_id, creator_id):
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
            party_ref = db.collection('parties').document(self.party_id)
            party_doc = party_ref.get()
            
            if not party_doc.exists:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            party_data = party_doc.to_dict()
            members = party_data.get('members', {})
            
            # Check if user is in party
            user_id_str = str(interaction.user.id)
            if user_id_str not in members:
                await interaction.response.send_message("❌ You're not in this party!", ephemeral=True)
                return
            
            # Remove user from party
            party_ref.update({
                f'members.{user_id_str}': firestore.DELETE_FIELD
            })
            
            await interaction.response.send_message("🚪 **Left the party** - You're no longer signed up.", ephemeral=True)
            await self.update_embed(interaction)
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("❌ Failed to leave party!", ephemeral=True)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # For edit button, only show to creator
        if interaction.data.get('custom_id') == 'edit_party':
            return interaction.user.id == self.creator_id
        return True
    
    @discord.ui.button(label='Edit Party', style=discord.ButtonStyle.primary, emoji='✏️', row=2, custom_id='edit_party')
    async def edit_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get party data from Firebase
            party_ref = db.collection('parties').document(self.party_id)
            party_doc = party_ref.get()
            
            if not party_doc.exists:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            party_data = party_doc.to_dict()
            
            modal = PartyEditModal(
                self.party_id,
                party_data.get('party_name', ''),
                party_data.get('party_timestamp', ''),
                party_data.get('tank_slots', 2),
                party_data.get('healer_slots', 2),
                party_data.get('dps_slots', 4)
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("❌ Edit failed!", ephemeral=True)
    
    async def join_role(self, interaction: discord.Interaction, role: str):
        try:
            # Get party data from Firebase
            party_ref = db.collection('parties').document(self.party_id)
            party_doc = party_ref.get()
            
            if not party_doc.exists:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            party_data = party_doc.to_dict()
            members = party_data.get('members', {})
            
            # Handle "can't attend" role differently (no slot limits)
            if role != 'cant_attend':
                tank_slots = party_data.get('tank_slots', 2)
                healer_slots = party_data.get('healer_slots', 2)
                dps_slots = party_data.get('dps_slots', 4)
                
                # Check if role has slots
                max_slots = {'tank': tank_slots, 'healer': healer_slots, 'dps': dps_slots}
                if max_slots[role] == 0:
                    role_name = role.title()
                    await interaction.response.send_message(f"❌ No {role_name} slots available in this party!", ephemeral=True)
                    return
                
                # Check if role is full
                current_count = sum(1 for member in members.values() if member.get('role') == role)
                
                if current_count >= max_slots[role]:
                    role_name = role.title()
                    await interaction.response.send_message(f"❌ {role_name} slots are full! ({current_count}/{max_slots[role]})", ephemeral=True)
                    return
            
            # Add/update user in party
            user_id_str = str(interaction.user.id)
            party_ref.update({
                f'members.{user_id_str}': {
                    'username': interaction.user.display_name,
                    'role': role,
                    'joined_at': firestore.SERVER_TIMESTAMP
                }
            })
            
            role_messages = {
                'tank': '🛡️ **Joined as Tank!**',
                'healer': '💚 **Joined as Healer!**', 
                'dps': '⚔️ **Joined as DPS!**',
                'cant_attend': '❌ **Marked as Can\'t Attend**'
            }
            
            await interaction.response.send_message(role_messages[role], ephemeral=True)
            await self.update_embed(interaction)
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("❌ Failed to join party!", ephemeral=True)
    
    async def update_embed(self, interaction: discord.Interaction):
        try:
            # Get party data from Firebase
            party_ref = db.collection('parties').document(self.party_id)
            party_doc = party_ref.get()
            
            if not party_doc.exists:
                return
            
            party_data = party_doc.to_dict()
            members = party_data.get('members', {})
            
            print(f"Party {self.party_id} members: {members}")
            
            party_creator_id = party_data.get('created_by')
            
            embed = discord.Embed(
                title=f"⚔️ {party_data.get('party_name', 'Unknown Party')}",
                color=0x5865F2
            )
            
            # Add timestamp if exists
            party_timestamp = party_data.get('party_timestamp')
            if party_timestamp:
                try:
                    timestamp = int(party_timestamp)
                    embed.add_field(
                        name="🕐 Party Starts",
                        value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                        inline=False
                    )
                except (ValueError, TypeError):
                    # It's a string
                    embed.add_field(
                        name="🕐 Party Starts",
                        value=f"**{party_timestamp}**",
                        inline=False
                    )
            
            # Organize members with creator crown logic
            tanks = []
            healers = []
            dps = []
            cant_attend = []
            
            for user_id_str, member_data in members.items():
                user_id = int(user_id_str)
                username = member_data.get('username', 'Unknown')
                role = member_data.get('role', 'unknown')
                
                # Add crown if this user is the party creator
                display_name = f"👑 {username}" if user_id == party_creator_id else username
                
                if role == 'tank':
                    tanks.append(display_name)
                elif role == 'healer':
                    healers.append(display_name)
                elif role == 'dps':
                    dps.append(display_name)
                elif role == 'cant_attend':
                    cant_attend.append(display_name)
            
            tank_slots = party_data.get('tank_slots', 2)
            healer_slots = party_data.get('healer_slots', 2)
            dps_slots = party_data.get('dps_slots', 4)
            
            # Tank section
            if tank_slots == 0:
                tank_text = "*No Tank Slots Set*"
            else:
                tank_display = []
                for i in range(tank_slots):
                    if i < len(tanks):
                        tank_display.append(f"{tanks[i]}")
                    else:
                        tank_display.append("*Empty*")
                tank_text = "\n".join(tank_display)
            
            embed.add_field(
                name=f"🛡️ Tanks ({len(tanks)}/{tank_slots})",
                value=tank_text,
                inline=True
            )
            
            # Healer section
            if healer_slots == 0:
                healer_text = "*No Healer Slots Set*"
            else:
                healer_display = []
                for i in range(healer_slots):
                    if i < len(healers):
                        healer_display.append(f"{healers[i]}")
                    else:
                        healer_display.append("*Empty*")
                healer_text = "\n".join(healer_display)
            
            embed.add_field(
                name=f"💚 Healers ({len(healers)}/{healer_slots})",
                value=healer_text,
                inline=True
            )
            
            # DPS section
            if dps_slots == 0:
                dps_text = "*No DPS Slots Set*"
            else:
                dps_display = []
                for i in range(dps_slots):
                    if i < len(dps):
                        dps_display.append(f"{dps[i]}")
                    else:
                        dps_display.append("*Empty*")
                dps_text = "\n".join(dps_display)
            
            embed.add_field(
                name=f"⚔️ DPS ({len(dps)}/{dps_slots})",
                value=dps_text,
                inline=True
            )
            
            # Can't Attend section - always show this section
            if cant_attend:
                cant_attend_text = "\n".join(cant_attend)
            else:
                cant_attend_text = "*Empty*"
            
            embed.add_field(
                name=f"❌ Can't Attend ({len(cant_attend)})",
                value=cant_attend_text,
                inline=False
            )
            
            total_members = len(tanks) + len(healers) + len(dps)  # Don't count cant_attend in member total
            total_slots = tank_slots + healer_slots + dps_slots
            
            # Get creator's name for footer
            creator_name = "Unknown"
            for user_id_str, member_data in members.items():
                if int(user_id_str) == party_creator_id:
                    creator_name = member_data.get('username', 'Unknown')
                    break
            else:
                # If creator isn't in party, try to get their name from the guild
                try:
                    if hasattr(interaction, 'guild') and interaction.guild:
                        creator_member = interaction.guild.get_member(party_creator_id)
                        if creator_member:
                            creator_name = creator_member.display_name
                except:
                    pass
            
            embed.set_footer(text=f"{creator_name}'s Party • {total_members}/{total_slots} members")
            
            # Update original message
            channel_id = party_data.get('channel_id')
            message_id = party_data.get('message_id')
            
            if channel_id and message_id:
                try:
                    channel = bot.get_channel(channel_id)
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed, view=self)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error updating embed: {e}")

async def restore_views():
    """Restore views for all active parties after bot restart"""
    try:
        # Get all parties with message IDs
        parties_ref = db.collection('parties')
        parties = parties_ref.where('message_id', '!=', None).stream()
        
        restored_count = 0
        for party_doc in parties:
            try:
                party_data = party_doc.to_dict()
                party_id = party_doc.id
                
                channel_id = party_data.get('channel_id')
                message_id = party_data.get('message_id')
                creator_id = party_data.get('created_by')
                
                if channel_id and message_id:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        message = await channel.fetch_message(message_id)
                        view = PartyView(party_id, creator_id)
                        await message.edit(view=view)
                        restored_count += 1
            except Exception as e:
                print(f"Failed to restore view for party {party_doc.id}: {e}")
        
        print(f"✅ Restored {restored_count} party views")
        
    except Exception as e:
        print(f"❌ Failed to restore views: {e}")

@bot.event
async def on_ready():
    print(f'🎮 {bot.user} is online!')
    init_firebase()
    
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    
    # Restore views after restart
    await restore_views()

@bot.tree.command(name="party", description="Create a new party")
@app_commands.describe(
    name="Party name",
    starttime="When does the party start? (e.g. 'Tomorrow 7PM', 'Friday 8PM')"
)
async def create_party(interaction: discord.Interaction, name: str, starttime: str):
    try:
        # Parse the time and convert to Discord timestamp if possible
        parsed_timestamp = None
        
        try:
            import dateutil.parser
            dt = dateutil.parser.parse(starttime, fuzzy=True)
            
            # If parsed time is in the past, assume next occurrence
            if dt < datetime.datetime.now():
                if "tomorrow" in starttime.lower():
                    dt = dt.replace(year=datetime.datetime.now().year, month=datetime.datetime.now().month, day=datetime.datetime.now().day) + datetime.timedelta(days=1)
                elif dt.time() > datetime.datetime.now().time():
                    # Same day but later time - keep as is
                    pass
                else:
                    # Assume next year if date seems to be in past
                    dt = dt.replace(year=datetime.datetime.now().year + 1)
            
            parsed_timestamp = int(dt.timestamp())
            
        except Exception as parse_error:
            print(f"Time parsing failed: {parse_error}")
            # Just use the original text if parsing fails
            pass
        
        # Create party in Firebase
        party_data = {
            'guild_id': interaction.guild.id,
            'channel_id': interaction.channel.id,
            'message_id': None,  # Will be updated later
            'party_name': name,
            'party_timestamp': parsed_timestamp if parsed_timestamp else starttime,
            'tank_slots': 2,
            'healer_slots': 2,
            'dps_slots': 4,
            'created_by': interaction.user.id,
            'created_at': firestore.SERVER_TIMESTAMP,
            'members': {}
        }
        
        # Add party to Firebase
        doc_time, party_ref = db.collection('parties').add(party_data)
        party_id = party_ref.id
        
        embed = discord.Embed(
            title=f"⚔️ {name}",
            color=0x5865F2
        )
        
        # Display the time
        if parsed_timestamp:
            embed.add_field(
                name="🕐 Party Starts",
                value=f"<t:{parsed_timestamp}:F>\n<t:{parsed_timestamp}:R>",
                inline=False
            )
        else:
            embed.add_field(
                name="🕐 Party Starts", 
                value=f"**{starttime}**",
                inline=False
            )
        
        embed.add_field(name="🛡️ Tanks (0/2)", value="*Empty*\n*Empty*", inline=True)
        embed.add_field(name="💚 Healers (0/2)", value="*Empty*\n*Empty*", inline=True)
        embed.add_field(name="⚔️ DPS (0/4)", value="*Empty*\n*Empty*\n*Empty*\n*Empty*", inline=True)
        embed.add_field(name="❌ Can't Attend (0)", value="*No one has marked Can't Attend*", inline=False)
        
        embed.set_footer(text=f"{interaction.user.display_name}'s Party • 0/8 members")
        
        view = PartyView(party_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        
        # Save message ID
        message = await interaction.original_response()
        party_ref.update({'message_id': message.id})
        
        print(f"✅ Party created: {name} at {starttime}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to create party!", ephemeral=True)

@bot.tree.command(name="parties", description="List all parties")
async def list_parties(interaction: discord.Interaction):
    try:
        # Get all parties for this guild from Firebase
        parties_ref = db.collection('parties')
        query = parties_ref.where('guild_id', '==', interaction.guild.id).order_by('created_at', direction=firestore.Query.DESCENDING)
        parties = query.stream()
        
        party_list = []
        for party_doc in parties:
            party_data = party_doc.to_dict()
            party_data['id'] = party_doc.id
            party_list.append(party_data)
        
        if not party_list:
            await interaction.response.send_message("📭 No parties found!", ephemeral=True)
            return
        
        embed = discord.Embed(title="⚔️ Active Parties", color=0x5865F2)
        
        for party_data in party_list:
            party_id = party_data['id']
            name = party_data.get('party_name', 'Unknown')
            tank_slots = party_data.get('tank_slots', 2)
            healer_slots = party_data.get('healer_slots', 2)
            dps_slots = party_data.get('dps_slots', 4)
            timestamp = party_data.get('party_timestamp')
            
            members = party_data.get('members', {})
            member_count = len([m for m in members.values() if m.get('role') != 'cant_attend'])
            total_slots = tank_slots + healer_slots + dps_slots
            
            info = f"**#{party_id[:8]}...** • {member_count}/{total_slots} members\n🛡️{tank_slots} 💚{healer_slots} ⚔️{dps_slots}"
            
            if timestamp:
                try:
                    ts = int(timestamp)
                    info += f"\n🕐 <t:{ts}:R>"
                except:
                    info += f"\n🕐 {timestamp}"
            
            embed.add_field(name=f"🎮 {name}", value=info, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to list parties!", ephemeral=True)

# Admin Commands
@bot.tree.command(name="admin-clear-parties", description="🔨 Admin: Delete all parties in this server")
async def admin_clear_parties(interaction: discord.Interaction):
    try:
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **Admin Only** - You need Administrator permissions to use this command.", ephemeral=True)
            return
        
        # Get all parties for this guild
        parties_ref = db.collection('parties')
        query = parties_ref.where('guild_id', '==', interaction.guild.id)
        parties = query.stream()
        
        party_count = 0
        for party_doc in parties:
            party_doc.reference.delete()
            party_count += 1
        
        if party_count == 0:
            await interaction.response.send_message("📭 No parties to delete in this server.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔨 Admin Action Complete",
            description=f"Successfully deleted **{party_count}** parties and all their members.",
            color=0xFF5555
        )
        embed.set_footer(text=f"Action performed by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        print(f"🔨 Admin {interaction.user.display_name} deleted {party_count} parties in {interaction.guild.name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to clear parties!", ephemeral=True)

@bot.tree.command(name="admin-party-stats", description="📊 Admin: View detailed party statistics")
async def admin_party_stats(interaction: discord.Interaction):
    try:
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **Admin Only** - You need Administrator permissions to use this command.", ephemeral=True)
            return
        
        # Get all parties for this guild
        parties_ref = db.collection('parties')
        query = parties_ref.where('guild_id', '==', interaction.guild.id)
        parties = query.stream()
        
        total_parties = 0
        total_members = 0
        role_stats = {'tank': 0, 'healer': 0, 'dps': 0, 'cant_attend': 0}
        user_party_count = {}
        
        for party_doc in parties:
            total_parties += 1
            party_data = party_doc.to_dict()
            members = party_data.get('members', {})
            
            for user_id_str, member_data in members.items():
                role = member_data.get('role', 'unknown')
                username = member_data.get('username', 'Unknown')
                
                if role != 'cant_attend':
                    total_members += 1
                
                if role in role_stats:
                    role_stats[role] += 1
                
                # Count user participation
                if username in user_party_count:
                    user_party_count[username] += 1
                else:
                    user_party_count[username] = 1
        
        embed = discord.Embed(
            title="📊 Server Party Statistics",
            description=f"Complete party data for **{interaction.guild.name}**",
            color=0x5865F2
        )
        
        # Basic stats
        embed.add_field(
            name="📈 Overview",
            value=f"**Total Parties:** {total_parties}\n**Total Members:** {total_members}\n**Avg Members/Party:** {total_members/total_parties:.1f}" if total_parties > 0 else "No parties yet",
            inline=False
        )
        
        # Role distribution
        if any(role_stats.values()):
            role_text = ""
            role_names = {'tank': '🛡️ Tanks', 'healer': '💚 Healers', 'dps': '⚔️ DPS', 'cant_attend': '❌ Can\'t Attend'}
            for role, count in role_stats.items():
                if count > 0:
                    role_text += f"{role_names.get(role, role.title())}: {count}\n"
            if role_text:
                embed.add_field(name="🎭 Role Distribution", value=role_text, inline=True)
        
        # Most active users
        if user_party_count:
            sorted_users = sorted(user_party_count.items(), key=lambda x: x[1], reverse=True)[:5]
            active_text = ""
            for username, count in sorted_users:
                active_text += f"• {username}: {count} parties\n"
            embed.add_field(name="🌟 Most Active Users", value=active_text, inline=True)
        
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to get statistics!", ephemeral=True)

@bot.tree.command(name="admin-delete-party", description="🗑️ Admin: Force delete any party by ID")
@app_commands.describe(party_id="Party ID to delete (first 8 chars shown in /parties)")
async def admin_delete_party(interaction: discord.Interaction, party_id: str):
    try:
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **Admin Only** - You need Administrator permissions to use this command.", ephemeral=True)
            return
        
        # Find party by partial ID
        parties_ref = db.collection('parties')
        query = parties_ref.where('guild_id', '==', interaction.guild.id)
        parties = query.stream()
        
        found_party = None
        for party_doc in parties:
            if party_doc.id.startswith(party_id):
                found_party = party_doc
                break
        
        if not found_party:
            await interaction.response.send_message(f"❌ Party with ID starting with **{party_id}** not found in this server.", ephemeral=True)
            return
        
        party_data = found_party.to_dict()
        party_name = party_data.get('party_name', 'Unknown')
        creator_id = party_data.get('created_by')
        
        # Delete party
        found_party.reference.delete()
        
        embed = discord.Embed(
            title="🗑️ Admin Party Deletion",
            description=f"Successfully deleted party **{party_name}** (ID: {found_party.id[:8]}...)",
            color=0xFF5555
        )
        embed.add_field(name="Original Creator", value=f"<@{creator_id}>", inline=True)
        embed.set_footer(text=f"Deleted by Admin {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        print(f"🗑️ Admin {interaction.user.display_name} deleted party {found_party.id} ({party_name})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to delete party!", ephemeral=True)

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No Discord token found!")
    else:
        bot.run(token)