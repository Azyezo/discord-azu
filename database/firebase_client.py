"""
Firebase client initialization and management
"""
import json
import firebase_admin
from firebase_admin import credentials, firestore
from config.settings import FIREBASE_SERVICE_ACCOUNT

class FirebaseClient:
    """Firebase client singleton"""
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseClient, cls).__new__(cls)
        return cls._instance
    
    def initialize(self):
        """Initialize Firebase connection"""
        if self._db is not None:
            return self._db
            
        try:
            # Check if app is already initialized
            try:
                firebase_admin.get_app()
                self._db = firestore.client()
                print("✅ Firebase already initialized!")
                return self._db
            except ValueError:
                # App not initialized, initialize it
                service_account_info = json.loads(FIREBASE_SERVICE_ACCOUNT)
                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(cred)
                
                self._db = firestore.client()
                print("✅ Firebase initialized!")
                return self._db
                
        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            raise e
    
    @property
    def db(self):
        """Get the database client"""
        if self._db is None:
            self.initialize()
        return self._db

# Global instance
firebase_client = FirebaseClient()

def get_db():
    """Get the Firebase database client"""
    return firebase_client.initialize()  # Call initialize() directly to ensure connection