import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import sqlite3
import datetime
from typing import Optional

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

def init_db():
    conn = sqlite3.connect('parties.db')
    cursor = conn.cursor()
    
    # Check existing table structure first
    cursor.execute("PRAGMA table_info(parties)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    print(f"Existing party table columns: {existing_columns}")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            channel_id INTEGER,
            message_id INTEGER,
            party_name TEXT,
            tank_slots INTEGER DEFAULT 0,
            healer_slots INTEGER DEFAULT 0,
            dps_slots INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if party_members table exists and get its structure
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='party_members'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # Check current constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='party_members'")
        table_sql = cursor.fetchone()[0]
        
        # If the constraint doesn't include 'cant_attend', we need to recreate the table
        if 'cant_attend' not in table_sql:
            print("Updating party_members table to support 'cant_attend'...")
            
            # Backup existing data
            cursor.execute('SELECT * FROM party_members')
            existing_data = cursor.fetchall()
            
            # Drop old table
            cursor.execute('DROP TABLE party_members')
            
            # Create new table with updated constraint
            cursor.execute('''
                CREATE TABLE party_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    party_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    role TEXT CHECK(role IN ('tank', 'healer', 'dps', 'cant_attend')),
                    FOREIGN KEY (party_id) REFERENCES parties (id)
                )
            ''')
            
            # Restore data
            for row in existing_data:
                cursor.execute('''
                    INSERT INTO party_members (id, party_id, user_id, username, role)
                    VALUES (?, ?, ?, ?, ?)
                ''', row)
            
            print("✅ party_members table updated!")
        else:
            print("✅ party_members table already supports 'cant_attend'")
    else:
        # Create new table
        cursor.execute('''
            CREATE TABLE party_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                party_id INTEGER,
                user_id INTEGER,
                username TEXT,
                role TEXT CHECK(role IN ('tank', 'healer', 'dps', 'cant_attend')),
                FOREIGN KEY (party_id) REFERENCES parties (id)
            )
        ''')
        print("✅ party_members table created!")
    
    # Add party_timestamp column if it doesn't exist
    if 'party_timestamp' not in existing_columns:
        print("Adding party_timestamp column...")
        cursor.execute('ALTER TABLE parties ADD COLUMN party_timestamp TEXT')
        print("✅ party_timestamp column added!")
    
    # Verify final structure
    cursor.execute("PRAGMA table_info(parties)")
    final_columns = [column[1] for column in cursor.fetchall()]
    print(f"Final party table columns: {final_columns}")
    
    conn.commit()
    conn.close()

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
            
            conn = sqlite3.connect('parties.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE parties 
                SET party_name = ?, party_timestamp = ?, tank_slots = ?, healer_slots = ?, dps_slots = ?
                WHERE id = ?
            ''', (self.name_input.value, starttime_value, tank_slots, healer_slots, dps_slots, self.party_id))
            
            conn.commit()
            conn.close()
            
            await interaction.response.send_message("✅ Party updated successfully!", ephemeral=True)
            
            # Update embed
            view = PartyView(self.party_id, None)  # We don't have creator_id in modal context
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
            conn = sqlite3.connect('parties.db')
            cursor = conn.cursor()
            
            # Check if user is in party
            cursor.execute('SELECT * FROM party_members WHERE party_id = ? AND user_id = ?', 
                          (self.party_id, interaction.user.id))
            member = cursor.fetchone()
            
            if not member:
                await interaction.response.send_message("❌ You're not in this party!", ephemeral=True)
                conn.close()
                return
            
            # Remove from party
            cursor.execute('DELETE FROM party_members WHERE party_id = ? AND user_id = ?', 
                          (self.party_id, interaction.user.id))
            conn.commit()
            conn.close()
            
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
            conn = sqlite3.connect('parties.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM parties WHERE id = ?', (self.party_id,))
            party = cursor.fetchone()
            conn.close()
            
            if not party:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                return
            
            modal = PartyEditModal(
                self.party_id,
                party[4],  # party_name
                party[10] if len(party) > 10 else "",  # party_timestamp
                party[5],  # tank_slots
                party[6],  # healer_slots
                party[7]   # dps_slots
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("❌ Edit failed!", ephemeral=True)
    
    async def join_role(self, interaction: discord.Interaction, role: str):
        try:
            conn = sqlite3.connect('parties.db')
            cursor = conn.cursor()
            
            # Get party info
            cursor.execute('SELECT * FROM parties WHERE id = ?', (self.party_id,))
            party = cursor.fetchone()
            
            if not party:
                await interaction.response.send_message("❌ Party not found!", ephemeral=True)
                conn.close()
                return
            
            # Handle "can't attend" role differently (no slot limits)
            if role != 'cant_attend':
                tank_slots = party[5]
                healer_slots = party[6]
                dps_slots = party[7]
                
                # Check if role has slots
                max_slots = {'tank': tank_slots, 'healer': healer_slots, 'dps': dps_slots}
                if max_slots[role] == 0:
                    role_name = role.title()
                    await interaction.response.send_message(f"❌ No {role_name} slots available in this party!", ephemeral=True)
                    conn.close()
                    return
                
                # Check if role is full
                cursor.execute('SELECT COUNT(*) FROM party_members WHERE party_id = ? AND role = ?', 
                              (self.party_id, role))
                current_count = cursor.fetchone()[0]
                
                if current_count >= max_slots[role]:
                    role_name = role.title()
                    await interaction.response.send_message(f"❌ {role_name} slots are full! ({current_count}/{max_slots[role]})", ephemeral=True)
                    conn.close()
                    return
            
            # Remove user from any existing role in this party
            cursor.execute('DELETE FROM party_members WHERE party_id = ? AND user_id = ?', 
                          (self.party_id, interaction.user.id))
            
            # Add user to new role
            cursor.execute('''
                INSERT INTO party_members (party_id, user_id, username, role)
                VALUES (?, ?, ?, ?)
            ''', (self.party_id, interaction.user.id, interaction.user.display_name, role))
            
            conn.commit()
            conn.close()
            
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
            conn = sqlite3.connect('parties.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM parties WHERE id = ?', (self.party_id,))
            party = cursor.fetchone()
            
            cursor.execute('SELECT user_id, username, role FROM party_members WHERE party_id = ?', (self.party_id,))
            members = cursor.fetchall()
            
            # Debug: Print members to console
            print(f"Party {self.party_id} members: {members}")
            
            conn.close()
            
            if not party:
                return
            
            party_creator_id = party[8]  # created_by is at index 8
            
            embed = discord.Embed(
                title=f"⚔️ {party[4]}",
                color=0x5865F2
            )
            
            # Add timestamp if exists (party_timestamp column)
            if len(party) > 10 and party[10]:  # party_timestamp should be at index 10
                timestamp_value = party[10]
                # Handle both integer timestamps and string times
                try:
                    timestamp = int(timestamp_value)
                    embed.add_field(
                        name="🕐 Party Starts",
                        value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                        inline=False
                    )
                except (ValueError, TypeError):
                    # It's a string
                    embed.add_field(
                        name="🕐 Party Starts",
                        value=f"**{timestamp_value}**",
                        inline=False
                    )
            
            # Organize members with creator crown logic
            tanks = []
            healers = []
            dps = []
            cant_attend = []
            
            for user_id, username, role in members:
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
            
            # Tank section
            if party[5] == 0:
                tank_text = "*No Tank Slots Set*"
            else:
                tank_display = []
                for i in range(party[5]):
                    if i < len(tanks):
                        tank_display.append(f"{tanks[i]}")
                    else:
                        tank_display.append("*Empty*")
                tank_text = "\n".join(tank_display)
            
            embed.add_field(
                name=f"🛡️ Tanks ({len(tanks)}/{party[5]})",
                value=tank_text,
                inline=True
            )
            
            # Healer section
            if party[6] == 0:
                healer_text = "*No Healer Slots Set*"
            else:
                healer_display = []
                for i in range(party[6]):
                    if i < len(healers):
                        healer_display.append(f"{healers[i]}")
                    else:
                        healer_display.append("*Empty*")
                healer_text = "\n".join(healer_display)
            
            embed.add_field(
                name=f"💚 Healers ({len(healers)}/{party[6]})",
                value=healer_text,
                inline=True
            )
            
            # DPS section
            if party[7] == 0:
                dps_text = "*No DPS Slots Set*"
            else:
                dps_display = []
                for i in range(party[7]):
                    if i < len(dps):
                        dps_display.append(f"{dps[i]}")
                    else:
                        dps_display.append("*Empty*")
                dps_text = "\n".join(dps_display)
            
            embed.add_field(
                name=f"⚔️ DPS ({len(dps)}/{party[7]})",
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
            total_slots = party[5] + party[6] + party[7]
            
            # Get creator's name for footer
            creator_name = "Unknown"
            for user_id, username, role in members:
                if user_id == party_creator_id:
                    creator_name = username
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
            channel = bot.get_channel(party[2])
            if channel and party[3]:
                try:
                    message = await channel.fetch_message(party[3])
                    await message.edit(embed=embed, view=self)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error updating embed: {e}")

@bot.event
async def on_ready():
    print(f'🎮 {bot.user} is online!')
    init_db()
    
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.tree.command(name="party", description="Create a new party")
@app_commands.describe(
    name="Party name",
    starttime="When does the party start? (e.g. 'Tomorrow 7PM', 'Friday 8PM')"
)
async def create_party(interaction: discord.Interaction, name: str, starttime: str):
    try:
        # Parse the time and convert to Discord timestamp if possible
        parsed_timestamp = None
        display_time = starttime
        
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
            display_time = f"<t:{parsed_timestamp}:F>"
            
        except Exception as parse_error:
            print(f"Time parsing failed: {parse_error}")
            # Just use the original text if parsing fails
            pass
        
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        
        # Store the timestamp (or original text if parsing failed)
        cursor.execute('''
            INSERT INTO parties (guild_id, channel_id, party_name, party_timestamp, tank_slots, healer_slots, dps_slots, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (interaction.guild.id, interaction.channel.id, name, parsed_timestamp if parsed_timestamp else starttime, 2, 2, 4, interaction.user.id))
        
        party_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
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
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE parties SET message_id = ? WHERE id = ?', (message.id, party_id))
        conn.commit()
        conn.close()
        
        print(f"✅ Party created: {name} at {starttime}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to create party!", ephemeral=True)

@bot.tree.command(name="parties", description="List all parties")
async def list_parties(interaction: discord.Interaction):
    try:
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.id, p.party_name, p.tank_slots, p.healer_slots, p.dps_slots, p.party_timestamp,
                   COUNT(pm.id) as member_count
            FROM parties p
            LEFT JOIN party_members pm ON p.id = pm.party_id
            WHERE p.guild_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        ''', (interaction.guild.id,))
        parties = cursor.fetchall()
        conn.close()
        
        if not parties:
            await interaction.response.send_message("📭 No parties found!", ephemeral=True)
            return
        
        embed = discord.Embed(title="⚔️ Active Parties", color=0x5865F2)
        
        for party in parties:
            party_id, name, tank_slots, healer_slots, dps_slots, timestamp, member_count = party
            total_slots = tank_slots + healer_slots + dps_slots
            
            info = f"**#{party_id}** • {member_count}/{total_slots} members\n🛡️{tank_slots} 💚{healer_slots} ⚔️{dps_slots}"
            
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
        
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        
        # Count parties first
        cursor.execute('SELECT COUNT(*) FROM parties WHERE guild_id = ?', (interaction.guild.id,))
        party_count = cursor.fetchone()[0]
        
        if party_count == 0:
            await interaction.response.send_message("📭 No parties to delete in this server.", ephemeral=True)
            conn.close()
            return
        
        # Delete all party members first (foreign key constraint)
        cursor.execute('''
            DELETE FROM party_members 
            WHERE party_id IN (SELECT id FROM parties WHERE guild_id = ?)
        ''', (interaction.guild.id,))
        
        # Delete all parties
        cursor.execute('DELETE FROM parties WHERE guild_id = ?', (interaction.guild.id,))
        
        conn.commit()
        conn.close()
        
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
        
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        
        # Get party statistics
        cursor.execute('SELECT COUNT(*) FROM parties WHERE guild_id = ?', (interaction.guild.id,))
        total_parties = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM party_members pm
            JOIN parties p ON pm.party_id = p.id
            WHERE p.guild_id = ?
        ''', (interaction.guild.id,))
        total_members = cursor.fetchone()[0]
        
        # Get role distribution
        cursor.execute('''
            SELECT pm.role, COUNT(*) FROM party_members pm
            JOIN parties p ON pm.party_id = p.id
            WHERE p.guild_id = ?
            GROUP BY pm.role
        ''', (interaction.guild.id,))
        role_stats = cursor.fetchall()
        
        # Get most active users
        cursor.execute('''
            SELECT pm.username, COUNT(*) as party_count FROM party_members pm
            JOIN parties p ON pm.party_id = p.id
            WHERE p.guild_id = ?
            GROUP BY pm.user_id
            ORDER BY party_count DESC
            LIMIT 5
        ''', (interaction.guild.id,))
        active_users = cursor.fetchall()
        
        conn.close()
        
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
        if role_stats:
            role_text = ""
            role_names = {'tank': '🛡️ Tanks', 'healer': '💚 Healers', 'dps': '⚔️ DPS'}
            for role, count in role_stats:
                role_text += f"{role_names.get(role, role.title())}: {count}\n"
            embed.add_field(name="🎭 Role Distribution", value=role_text, inline=True)
        
        # Most active users
        if active_users:
            active_text = ""
            for username, count in active_users:
                active_text += f"• {username}: {count} parties\n"
            embed.add_field(name="🌟 Most Active Users", value=active_text, inline=True)
        
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to get statistics!", ephemeral=True)

@bot.tree.command(name="admin-delete-party", description="🗑️ Admin: Force delete any party by ID")
@app_commands.describe(party_id="Party ID to delete")
async def admin_delete_party(interaction: discord.Interaction, party_id: int):
    try:
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **Admin Only** - You need Administrator permissions to use this command.", ephemeral=True)
            return
        
        conn = sqlite3.connect('parties.db')
        cursor = conn.cursor()
        
        # Check if party exists
        cursor.execute('SELECT party_name, created_by FROM parties WHERE id = ? AND guild_id = ?', 
                      (party_id, interaction.guild.id))
        result = cursor.fetchone()
        
        if not result:
            await interaction.response.send_message(f"❌ Party **#{party_id}** not found in this server.", ephemeral=True)
            conn.close()
            return
        
        party_name, creator_id = result
        
        # Delete party members first
        cursor.execute('DELETE FROM party_members WHERE party_id = ?', (party_id,))
        
        # Delete party
        cursor.execute('DELETE FROM parties WHERE id = ?', (party_id,))
        
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🗑️ Admin Party Deletion",
            description=f"Successfully deleted party **{party_name}** (ID: #{party_id})",
            color=0xFF5555
        )
        embed.add_field(name="Original Creator", value=f"<@{creator_id}>", inline=True)
        embed.set_footer(text=f"Deleted by Admin {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        print(f"🗑️ Admin {interaction.user.display_name} deleted party #{party_id} ({party_name})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("❌ Failed to delete party!", ephemeral=True)

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No Discord token found!")
    else:
        bot.run(token)