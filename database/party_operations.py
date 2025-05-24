"""
Party database operations
"""
from typing import Dict, List, Optional, Tuple, Any
from firebase_admin import firestore
from database.firebase_client import get_db
from config.settings import DEFAULT_TANK_SLOTS, DEFAULT_HEALER_SLOTS, DEFAULT_DPS_SLOTS

class PartyOperations:
    """Handle all party-related database operations"""
    
    def __init__(self):
        self.db = get_db()
    
    def create_party(self, guild_id: int, channel_id: int, party_name: str, 
                    party_timestamp: Any, created_by: int) -> str:
        """Create a new party in the database"""
        try:
            party_data = {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'message_id': None,  # Will be updated later
                'party_name': party_name,
                'party_timestamp': party_timestamp,
                'tank_slots': DEFAULT_TANK_SLOTS,
                'healer_slots': DEFAULT_HEALER_SLOTS,
                'dps_slots': DEFAULT_DPS_SLOTS,
                'created_by': created_by,
                'created_at': firestore.SERVER_TIMESTAMP,
                'members': {}
            }
            
            # Add party to Firebase
            doc_time, party_ref = self.db.collection('parties').add(party_data)
            return party_ref.id
            
        except Exception as e:
            print(f"❌ Error creating party: {e}")
            return None
    
    def get_party(self, party_id: str) -> Optional[Dict]:
        """Get party data by ID"""
        try:
            party_ref = self.db.collection('parties').document(party_id)
            party_doc = party_ref.get()
            
            if party_doc.exists:
                party_data = party_doc.to_dict()
                party_data['id'] = party_doc.id
                return party_data
            return None
            
        except Exception as e:
            print(f"❌ Error getting party: {e}")
            return None
    
    def update_party(self, party_id: str, updates: Dict) -> bool:
        """Update party data"""
        try:
            party_ref = self.db.collection('parties').document(party_id)
            
            # Check if party exists
            party_doc = party_ref.get()
            if not party_doc.exists:
                return False
            
            # Add timestamp to updates
            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            
            # Update party
            party_ref.update(updates)
            return True
            
        except Exception as e:
            print(f"❌ Error updating party: {e}")
            return False
    
    def update_message_id(self, party_id: str, message_id: int) -> bool:
        """Update the message ID for a party"""
        return self.update_party(party_id, {'message_id': message_id})
    
    def add_member(self, party_id: str, user_id: int, username: str, role: str) -> bool:
        """Add or update a member in a party"""
        try:
            party_ref = self.db.collection('parties').document(party_id)
            
            # Check if party exists
            party_doc = party_ref.get()
            if not party_doc.exists:
                return False
            
            # Add/update member
            user_id_str = str(user_id)
            party_ref.update({
                f'members.{user_id_str}': {
                    'username': username,
                    'role': role,
                    'joined_at': firestore.SERVER_TIMESTAMP
                }
            })
            return True
            
        except Exception as e:
            print(f"❌ Error adding member to party: {e}")
            return False
    
    def remove_member(self, party_id: str, user_id: int) -> bool:
        """Remove a member from a party"""
        try:
            party_ref = self.db.collection('parties').document(party_id)
            
            # Check if party exists
            party_doc = party_ref.get()
            if not party_doc.exists:
                return False
            
            # Remove member
            user_id_str = str(user_id)
            party_ref.update({
                f'members.{user_id_str}': firestore.DELETE_FIELD
            })
            return True
            
        except Exception as e:
            print(f"❌ Error removing member from party: {e}")
            return False
    
    def get_guild_parties(self, guild_id: int) -> List[Dict]:
        """Get all parties for a guild"""
        try:
            parties_ref = self.db.collection('parties')
            query = parties_ref.where('guild_id', '==', guild_id).order_by('created_at', direction=firestore.Query.DESCENDING)
            parties = query.stream()
            
            party_list = []
            for party_doc in parties:
                party_data = party_doc.to_dict()
                party_data['id'] = party_doc.id
                party_list.append(party_data)
            
            return party_list
            
        except Exception as e:
            print(f"❌ Error getting guild parties: {e}")
            return []
    
    def delete_party(self, party_id: str) -> bool:
        """Delete a party"""
        try:
            party_ref = self.db.collection('parties').document(party_id)
            
            # Check if party exists
            party_doc = party_ref.get()
            if not party_doc.exists:
                return False
            
            # Delete party
            party_ref.delete()
            return True
            
        except Exception as e:
            print(f"❌ Error deleting party: {e}")
            return False
    
    def delete_guild_parties(self, guild_id: int) -> int:
        """Delete all parties for a guild, returns count deleted"""
        try:
            parties_ref = self.db.collection('parties')
            query = parties_ref.where('guild_id', '==', guild_id)
            parties = query.stream()
            
            party_count = 0
            for party_doc in parties:
                party_doc.reference.delete()
                party_count += 1
            
            return party_count
            
        except Exception as e:
            print(f"❌ Error deleting guild parties: {e}")
            return 0
    
    def get_parties_with_message_ids(self) -> List[Dict]:
        """Get all parties that have message IDs (for view restoration)"""
        try:
            parties_ref = self.db.collection('parties')
            parties = parties_ref.where('message_id', '!=', None).stream()
            
            party_list = []
            for party_doc in parties:
                party_data = party_doc.to_dict()
                party_data['id'] = party_doc.id
                party_list.append(party_data)
            
            return party_list
            
        except Exception as e:
            print(f"❌ Error getting parties with message IDs: {e}")
            return []
    
    def is_role_full(self, party_data: Dict, role: str) -> bool:
        """Check if a specific role is full in a party"""
        if role == 'cant_attend':
            return False  # Can't attend has no limit
        
        members = party_data.get('members', {})
        role_slots = {
            'tank': party_data.get('tank_slots', DEFAULT_TANK_SLOTS),
            'healer': party_data.get('healer_slots', DEFAULT_HEALER_SLOTS),
            'dps': party_data.get('dps_slots', DEFAULT_DPS_SLOTS)
        }
        
        max_slots = role_slots.get(role, 0)
        if max_slots == 0:
            return True  # No slots means full
        
        current_count = sum(1 for member in members.values() if member.get('role') == role)
        return current_count >= max_slots
    
    def get_member_counts_by_role(self, party_data: Dict) -> Dict[str, int]:
        """Get count of members by role"""
        members = party_data.get('members', {})
        counts = {'tank': 0, 'healer': 0, 'dps': 0, 'cant_attend': 0}
        
        for member in members.values():
            role = member.get('role', 'unknown')
            if role in counts:
                counts[role] += 1
        
        return counts
    
    def find_party_by_partial_id(self, guild_id: int, partial_id: str) -> Optional[Dict]:
        """Find a party by partial ID within a guild"""
        try:
            parties_ref = self.db.collection('parties')
            query = parties_ref.where('guild_id', '==', guild_id)
            parties = query.stream()
            
            for party_doc in parties:
                if party_doc.id.startswith(partial_id):
                    party_data = party_doc.to_dict()
                    party_data['id'] = party_doc.id
                    return party_data
            
            return None
            
        except Exception as e:
            print(f"❌ Error finding party by partial ID: {e}")
            return None

# Global instance
party_ops = PartyOperations()