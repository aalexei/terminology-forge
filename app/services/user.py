from db.schema import User

class UserService:

    collection = "users"
    
    def __init__(self, db):
        self.db = db

    async def github_to_uid(self, github_uid):
        users = self.db.collection(self.collection)
        cursor = await users.find({"github": github_uid}, limit=1)
        if cursor.empty():
            uid = None
        else:
            data = cursor.pop()
            uid = data['_id']
        await cursor.close()
        return uid

    async def get(self, uid):
        users = self.db.collection(self.collection)
        userdata = await users.get(uid)
        user = User(**userdata)
        return user
