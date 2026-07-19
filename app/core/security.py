import secrets
from datetime import datetime
import bcrypt
from fastapi import Request
from loguru import logger
from core.config import config
from core.exceptions import UnauthorizedException
from db.db import SESSIONS
from services.user import UserService
from fastapi import Request

def verify_password(plain_password: str, hashed_password: str) -> bool:
    '''
    Verify password against hashed password.
    '''
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

def get_password_hash(password: str) -> str:
    '''
    Hash password so hash can be stored.
    '''
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_user(username, plain_password, G):
    '''
    Verify password of user in G.
    '''
    user = G.getUser(username)
    
    if user is not None:
        if verify_password(plain_password, user["hashedpass"]):
            return username
        else:
            logger.warning("Incorrect password for username '%s'", username)

    else:
        logger.warning("Unknown username '%s'", username)

    return None


def make_session_id() -> str:
    '''
    Make a URL safe random session ID
    '''
    return secrets.token_urlsafe(64)

async def current_user(request: Request):
    session_authorization = request.cookies.get("ook_token")
    session_id = request.session.get("session_id")
    token_exp = request.session.get("token_expiry")

    if not session_authorization and not session_id:
        logger.info("No token or Session ID")
        raise UnauthorizedException("You must be logged in")
    
    if session_authorization != session_id:
        logger.info("Token does not match Session ID")
        raise UnauthorizedException("You must be logged in")
    
    if is_token_expired(token_exp):
        logger.info("Access_token is expired")
        raise UnauthorizedException("Log in expired")
    
    logger.debug("Valid Session, Access granted.")
    user_id = request.session.get("user_id")
    
    return user_id

# ---------------------------------------------------
# GitHub auth
# ---------------------------------------------------

async def get_auth_github_user(db, guser):
    '''
    Return DB userid if user is authorised
    None otherwise
    '''

    user_service = UserService(db)
    uid = await user_service.github_to_uid(guser)
    return uid

def is_token_expired(timestamp: int) -> bool:
    if timestamp:
        datetime_from_timestamp = datetime.fromtimestamp(timestamp)
        current_time = datetime.now()
        difference_in_minutes = (current_time - datetime_from_timestamp).total_seconds() / 60
        return difference_in_minutes >= config.max_session_minutes
    else:
        return True

async def auth_user(request: Request):
    '''
    Verify that user has a valid session.
    Return uid if valid otherwise raise exceptions
    '''

    # broken internet .. shortcut
    user_service = UserService(request.app.state.client.db)
    uid = await user_service.github_to_uid("aalexei")
    user = await user_service.get(uid)
    return user

    
    sessionid = request.session.get('access_token')
    
    if not sessionid or sessionid not in SESSIONS:
        logger.info('No session ID')
        raise UnauthorizedException('You must be logged in')
    elif is_token_expired(SESSIONS[sessionid]['timestamp']):
        logger.info('Session expired')
        SESSIONS.pop(sessionid, None)
        raise UnauthorizedException('Log in expired')
    else:
        logger.debug('Session valid')
        uid = SESSIONS[sessionid]['uid']
        user_service = UserService(request.app.state.client.db)
        user = await user_service.get(uid)
        return user

    



