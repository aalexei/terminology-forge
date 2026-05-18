from db.schema import User

class UserService:

    collection = "users"
    
    def __init__(self, db):
        self.db = db

    async def get_github(self, github_uid):
        users = self.db.collection(self.collection)
        cursor = await users.find({"github": github_uid}, limit=1)
        if cursor.empty():
            user = None
        else:
            user = User(**cursor.pop())
        await cursor.close()
        return user
