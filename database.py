import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Tuple, Optional
import os
import json

# Initialize Firebase if not already done
def init_firebase():
    """Initialize Firebase if not already initialized"""
    try:
        # Check if app is already initialized
        firebase_admin.get_app()
        return firestore.client()
    except ValueError:
        # App not initialized, initialize it
        service_account_info = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        return firestore.client()

# Get Firebase client
db = init_firebase()

def get_event_participants(event_id: str) -> List[Tuple[str, str]]:
    """Get all participants for an event"""
    try:
        # Get event document
        event_ref = db.collection('events').document(event_id)
        event_doc = event_ref.get()
        
        if not event_doc.exists:
            return []
        
        event_data = event_doc.to_dict()
        participants = event_data.get('participants', {})
        
        # Convert to list of tuples (username, status)
        result = []
        for user_id, participant_data in participants.items():
            username = participant_data.get('username', 'Unknown')
            status = participant_data.get('status', 'unknown')
            result.append((username, status))
        
        return result
        
    except Exception as e:
        print(f"❌ Error getting event participants: {e}")
        return []

def get_user_events(user_id: int, guild_id: int) -> List[Tuple]:
    """Get all events a user has participated in"""
    try:
        # Query events for this guild
        events_ref = db.collection('events')
        query = events_ref.where('guild_id', '==', guild_id)
        events = query.stream()
        
        result = []
        user_id_str = str(user_id)
        
        for event_doc in events:
            event_data = event_doc.to_dict()
            participants = event_data.get('participants', {})
            
            # Check if user participated in this event
            if user_id_str in participants:
                event_id = event_doc.id
                title = event_data.get('title', 'Unknown Event')
                status = participants[user_id_str].get('status', 'unknown')
                result.append((event_id, title, status))
        
        return result
        
    except Exception as e:
        print(f"❌ Error getting user events: {e}")
        return []

def create_event(guild_id: int, channel_id: int, title: str, description: str = "", creator_id: int = None) -> str:
    """Create a new event"""
    try:
        event_data = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'title': title,
            'description': description,
            'created_by': creator_id,
            'created_at': firestore.SERVER_TIMESTAMP,
            'participants': {}
        }
        
        # Add event to Firebase
        doc_time, event_ref = db.collection('events').add(event_data)
        
        print(f"✅ Event created: {title}")
        return event_ref.id
        
    except Exception as e:
        print(f"❌ Error creating event: {e}")
        return None

def add_participant_to_event(event_id: str, user_id: int, username: str, status: str) -> bool:
    """Add or update a participant in an event"""
    try:
        event_ref = db.collection('events').document(event_id)
        
        # Check if event exists
        event_doc = event_ref.get()
        if not event_doc.exists:
            print(f"❌ Event {event_id} not found")
            return False
        
        # Add/update participant
        user_id_str = str(user_id)
        event_ref.update({
            f'participants.{user_id_str}': {
                'username': username,
                'status': status,
                'joined_at': firestore.SERVER_TIMESTAMP
            }
        })
        
        print(f"✅ Added {username} to event {event_id} with status: {status}")
        return True
        
    except Exception as e:
        print(f"❌ Error adding participant to event: {e}")
        return False

def remove_participant_from_event(event_id: str, user_id: int) -> bool:
    """Remove a participant from an event"""
    try:
        event_ref = db.collection('events').document(event_id)
        
        # Check if event exists
        event_doc = event_ref.get()
        if not event_doc.exists:
            print(f"❌ Event {event_id} not found")
            return False
        
        # Remove participant
        user_id_str = str(user_id)
        event_ref.update({
            f'participants.{user_id_str}': firestore.DELETE_FIELD
        })
        
        print(f"✅ Removed user {user_id} from event {event_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error removing participant from event: {e}")
        return False

def get_event(event_id: str) -> Optional[dict]:
    """Get event data by ID"""
    try:
        event_ref = db.collection('events').document(event_id)
        event_doc = event_ref.get()
        
        if event_doc.exists:
            event_data = event_doc.to_dict()
            event_data['id'] = event_doc.id
            return event_data
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting event: {e}")
        return None

def get_guild_events(guild_id: int) -> List[dict]:
    """Get all events for a guild"""
    try:
        events_ref = db.collection('events')
        query = events_ref.where('guild_id', '==', guild_id).order_by('created_at', direction=firestore.Query.DESCENDING)
        events = query.stream()
        
        event_list = []
        for event_doc in events:
            event_data = event_doc.to_dict()
            event_data['id'] = event_doc.id
            event_list.append(event_data)
        
        return event_list
        
    except Exception as e:
        print(f"❌ Error getting guild events: {e}")
        return []

def update_event(event_id: str, updates: dict) -> bool:
    """Update event data"""
    try:
        event_ref = db.collection('events').document(event_id)
        
        # Check if event exists
        event_doc = event_ref.get()
        if not event_doc.exists:
            print(f"❌ Event {event_id} not found")
            return False
        
        # Add timestamp to updates
        updates['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Update event
        event_ref.update(updates)
        
        print(f"✅ Updated event {event_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating event: {e}")
        return False

def delete_event(event_id: str) -> bool:
    """Delete an event"""
    try:
        event_ref = db.collection('events').document(event_id)
        
        # Check if event exists
        event_doc = event_ref.get()
        if not event_doc.exists:
            print(f"❌ Event {event_id} not found")
            return False
        
        # Delete event
        event_ref.delete()
        
        print(f"✅ Deleted event {event_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting event: {e}")
        return False

def get_participant_count_by_status(event_id: str) -> dict:
    """Get count of participants by status for an event"""
    try:
        event_ref = db.collection('events').document(event_id)
        event_doc = event_ref.get()
        
        if not event_doc.exists:
            return {}
        
        event_data = event_doc.to_dict()
        participants = event_data.get('participants', {})
        
        status_counts = {}
        for participant_data in participants.values():
            status = participant_data.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return status_counts
        
    except Exception as e:
        print(f"❌ Error getting participant counts: {e}")
        return {}

def search_events_by_title(guild_id: int, search_term: str) -> List[dict]:
    """Search events by title (case-insensitive)"""
    try:
        events_ref = db.collection('events')
        query = events_ref.where('guild_id', '==', guild_id)
        events = query.stream()
        
        search_term_lower = search_term.lower()
        matching_events = []
        
        for event_doc in events:
            event_data = event_doc.to_dict()
            title = event_data.get('title', '').lower()
            
            if search_term_lower in title:
                event_data['id'] = event_doc.id
                matching_events.append(event_data)
        
        return matching_events
        
    except Exception as e:
        print(f"❌ Error searching events: {e}")
        return []

def get_user_participation_stats(user_id: int, guild_id: int) -> dict:
    """Get detailed participation statistics for a user"""
    try:
        events_ref = db.collection('events')
        query = events_ref.where('guild_id', '==', guild_id)
        events = query.stream()
        
        user_id_str = str(user_id)
        stats = {
            'total_events': 0,
            'status_counts': {},
            'events_created': 0
        }
        
        for event_doc in events:
            event_data = event_doc.to_dict()
            participants = event_data.get('participants', {})
            created_by = event_data.get('created_by')
            
            # Count events created by user
            if created_by == user_id:
                stats['events_created'] += 1
            
            # Count participation
            if user_id_str in participants:
                stats['total_events'] += 1
                status = participants[user_id_str].get('status', 'unknown')
                stats['status_counts'][status] = stats['status_counts'].get(status, 0) + 1
        
        return stats
        
    except Exception as e:
        print(f"❌ Error getting user participation stats: {e}")
        return {'total_events': 0, 'status_counts': {}, 'events_created': 0}

# Legacy compatibility functions (keeping same interface as SQLite version)
def get_events_by_status(guild_id: int, status: str) -> List[dict]:
    """Get all events where user has specific status"""
    try:
        events_ref = db.collection('events')
        query = events_ref.where('guild_id', '==', guild_id)
        events = query.stream()
        
        matching_events = []
        for event_doc in events:
            event_data = event_doc.to_dict()
            participants = event_data.get('participants', {})
            
            # Check if any participant has the specified status
            for participant_data in participants.values():
                if participant_data.get('status') == status:
                    event_data['id'] = event_doc.id
                    matching_events.append(event_data)
                    break
        
        return matching_events
        
    except Exception as e:
        print(f"❌ Error getting events by status: {e}")
        return []