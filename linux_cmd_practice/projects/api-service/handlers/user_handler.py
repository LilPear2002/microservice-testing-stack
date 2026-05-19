"""User API Handler"""
import logging
logger = logging.getLogger("api.user")

class UserHandler:
    def get_user(self, user_id):
        logger.info(f"Fetching user {user_id}")
        return {"id": user_id, "name": "TestUser"}

    def create_user(self, data):
        """Create a new user account"""
        if not data.get("email"):
            raise ValueError("email is required")
        logger.info(f"Creating user: {data['email']}")
        return {"id": 100, **data}

    def delete_user(self, user_id):
        """Soft-delete a user account"""
        logger.warning(f"Deleting user {user_id}")
        return {"status": "deleted", "id": user_id}

    def list_users(self, page=1, limit=20):
        """List all users with pagination"""
        logger.debug(f"Listing users page={page} limit={limit}")
        return {"page": page, "limit": limit, "total": 150, "users": []}
