from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Config(BaseSettings):
    #
    # App
    #
    app_name: str = "TerminologyForge"
    app_version: str = "0.1"
    host: str = "localhost"
    port: int = 8001
    ssl_keyfile: str = "ssl.key"
    ssl_certfile: str = "ssl.crt"
    background_sleep_minutes: int = 60*6 
    
    #
    # Log
    #
    loglevel: str = "DEBUG"
    logfile: str = "logs/terminologyforge.log"
    
    #
    # DB
    #
    db_user: str = ""
    db_password: str = ""
    db_url: str = "http://localhost:8529"
    db_name: str = "TFDB"
    
    #
    # OAuth2 configuration
    #
    client_id: str = ""
    client_secret: str = ""
    authorize_url: str = "https://github.com/login/oauth/authorize"
    token_url: str = "https://github.com/login/oauth/access_token"
    user_url: str = "https://api.github.com/user"
    redirect_uri: str = ""

    #
    # Sessions
    #
    max_session_minutes: int = 60*24
    session_secret: str = ""

    # @property
    # def db_url(self):
    #     return f"sqlite:///./{self.db_name}"


config = Config()

