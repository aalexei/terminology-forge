import re
import json
import time
from db import schema


class TaskService:

    collection = None
    
    def __init__(self, db, vocab=''):
        self.db = db
        self.collection = vocab+'_task'

    async def get_tasks(self):
        
        tasks = []
        cursor = await self.db.aql.execute(
            "FOR t IN @@coll RETURN t",
            bind_vars={"@coll": f"{self.collection}"})
        async for task in cursor:
            tasks.append(schema.Task(**task))
        return tasks 
