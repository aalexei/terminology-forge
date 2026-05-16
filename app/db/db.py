from arangoasync import ArangoClient
from arangoasync.auth import Auth
from core.config import config
from arangoasync.typings import UserInfo

# TODO Session data is in memory for the moment
SESSIONS = {}

class Client:
    def __init__(self):
        self._client = None
        self._db = None

    @property
    def db(self):
        return self._db

    async def connect(self):
        if self._client is not None:
            # Already connected
            return
        self._client = ArangoClient(hosts=config.db_url)

        auth = Auth(
            username=config.db_user,
            password=config.db_password
        )
        self._db = await self._client.db(
            config.db_name,
            auth=auth
        )

    async def close(self):
        if self._client is not None:
            await self._client.close()
