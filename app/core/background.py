from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from loguru import logger
from core.config import config
from db.db import Client

#
# Background tasks
#
async def backgroundTasks():
    '''
    Periodically run background tasks in import docs and sync annotations
    '''
    while True:
        try:
            logger.info("Background tasks running...")
            
            # await something
            
            await asyncio.sleep(60*config.background_sleep_minutes)
        except Exception as x:
            # Id a background process fails it should not derail the rest
            logger.error(x)

@asynccontextmanager
async def lifespan(app: FastAPI):
    '''
    Manage the app lifecycle
    '''
    # Create the recurring background tasks
    asyncio.create_task(backgroundTasks())

    # Open a database connection
    app.state.client = Client()
    await app.state.client.connect()
    
    # Run FastAPI
    yield
    
    # Any post app tasks here

    # Close database connection
    await app.state.client.close()
