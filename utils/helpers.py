"""
Utility functions and helpers
"""
import discord
import datetime
from typing import Dict, Any, Optional, Union
from config.settings import EMBED_COLOR

def parse_time_string(time_str: str, guild_id: int = None) -> Union[int, str]:
    """Parse a time string and return timestamp or original string if parsing fails"""
    try:
        import dateutil.parser
        
        time_str = time_str.lower()
        
        # Parse time as UTC - users should input UTC time
        dt = dateutil.parser.parse(time_str, fuzzy=True)
        return int(dt.timestamp())
        
    except Exception:
        # If parsing fails, return original string
        return time_str

def format_party_embed(party_data: Dict) -> discord.Embed:
    """Format party data into a Discord embed"""
    party_creator_id = party_data.get('created_by')
    members = party_data.get('members', {})
    
    embed = discord.Embed(
        title=f"⚔️ {party_data.get('party_name', 'Unknown Party')}",
        color=EMBED_COLOR
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
    creator_name = get_creator_name(members, party_creator_id)
    
    embed.set_footer(text=f"{creator_name}'s Party • {total_members}/{total_slots} members")
    
    return embed

def get_creator_name(members: Dict, creator_id: int) -> str:
    """Get the creator's display name from members or return Unknown"""
    for user_id_str, member_data in members.items():
        if int(user_id_str) == creator_id:
            return member_data.get('username', 'Unknown')
    return 'Unknown'

def format_party_list_embed(party_list: list, guild_name: str) -> discord.Embed:
    """Format a list of parties into a Discord embed"""
    embed = discord.Embed(title="⚔️ Active Parties", color=EMBED_COLOR)
    
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
    
    return embed

def format_admin_stats_embed(stats: Dict, guild_name: str) -> discord.Embed:
    """Format admin statistics into a Discord embed"""
    embed = discord.Embed(
        title="📊 Server Party Statistics",
        description=f"Complete party data for **{guild_name}**",
        color=EMBED_COLOR
    )
    
    total_parties = stats.get('total_parties', 0)
    total_members = stats.get('total_members', 0)
    role_stats = stats.get('role_stats', {})
    user_party_count = stats.get('user_party_count', {})
    
    # Basic stats
    if total_parties > 0:
        overview_text = f"**Total Parties:** {total_parties}\n**Total Members:** {total_members}\n**Avg Members/Party:** {total_members/total_parties:.1f}"
    else:
        overview_text = "No parties yet"
    
    embed.add_field(
        name="📈 Overview",
        value=overview_text,
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
    
    return embed

def calculate_party_stats(parties: list) -> Dict:
    """Calculate statistics from a list of parties"""
    total_parties = len(parties)
    total_members = 0
    role_stats = {'tank': 0, 'healer': 0, 'dps': 0, 'cant_attend': 0}
    user_party_count = {}
    
    for party_data in parties:
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
    
    return {
        'total_parties': total_parties,
        'total_members': total_members,
        'role_stats': role_stats,
        'user_party_count': user_party_count
    }