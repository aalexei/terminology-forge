from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger
from core.applogging import setup_logging
from core.background import lifespan
from core.config import config
import routes.authentication
import routes.presentation
from routes.exception_handlers import register_exception_handlers


app = FastAPI(lifespan=lifespan, title=config.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(SessionMiddleware, secret_key=config.session_secret, max_age=None)

setup_logging()

register_exception_handlers(app)

app.include_router(routes.authentication.router)
app.include_router(routes.presentation.router)
        

# ====================================================================
if __name__ == "__main__":

    import uvicorn
    logger.info("Launched app")
    
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=True,
        reload_dirs=['app'],
        log_config=None, # Prevent Uvicorn from Overriding Logging 
        log_level=None, # Prevent Uvicorn from Overriding Logging 
        ssl_keyfile=config.ssl_keyfile,
        ssl_certfile=config.ssl_certfile,
    )
