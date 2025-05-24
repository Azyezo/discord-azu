import sqlite3
from typing import List, Tuple, Optional

def get_event_participants(event_id: int) -> List[Tuple[str, str]]:
    """Get all participants for an event"""
    conn = sqlite3.connect('events.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, status FROM participants WHERE event_id = ?', (event_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_user_events(user_id: int, guild_id: int) -> List[Tuple]:
    """Get all events a user has participated in"""
    conn = sqlite3.connect('events.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.id, e.title, p.status 
        FROM events e 
        JOIN participants p ON e.id = p.event_id 
        WHERE p.user_id = ? AND e.guild_id = ?
    ''', (user_id, guild_id))
    result = cursor.fetchall()
    conn.close()
    return result