from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from core.security import get_auth_github_user, get_auth_user
from core.config import config
from core.exceptions import UnauthorizedException
import httpx
import time
from loguru import logger
from db.db import SESSIONS

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

def auth_user(request: Request):
    '''
    Verify that user has a valid session.
    Return uid if valid otherwise raise exceptions
    '''
    access_token = request.session.get('access_token')
    result = get_auth_user(access_token)
    return result['uid']

@router.get("/login")
async def login():
    redirect_uri = f"{config.authorize_url}?client_id={config.client_id}&redirect_uri={config.redirect_uri}&scope=read:user"
    return RedirectResponse(redirect_uri)

@router.get("/callback")
async def auth_callback(request: Request, code: str):
    token_data = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": config.redirect_uri
    }

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        headers = {'Accept': 'application/json'}
        response = await client.post(config.token_url, data=token_data, headers=headers)
        token_response = response.json()
        access_token = token_response.get("access_token")
        if not access_token:
            logger.warning('no access_token token_response=%s',str(token_response))
            raise UnauthorizedException("Failed to obtain access token")

    # Fetch GitHub user information
    headers = {"Authorization": f"token {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(config.user_url, headers=headers)
        user_data = response.json()

    # 'login' field has GitHub username
    guser = user_data.get('login', None)
    uid = get_auth_github_user(guser)

    if uid is not None:
        # Store access token in session
        request.session['access_token'] = access_token
        SESSIONS[access_token] = {'uid':uid, 'timestamp':time.time()}
        return RedirectResponse('/')
    else:
        raise UnauthorizedException("Failed authentication")

@router.get("/logout")
async def logout(request: Request):
    if 'access_token' in request.session:
        SESSIONS.pop(request.session['access_token'], None)
        request.session.pop('access_token', None)

    return templates.TemplateResponse(
       request = request,
       name = "logout.html",
       context = {}
   )



