from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from routes.authentication import auth_user

from core import exceptions

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def root(request: Request, uid=Depends(auth_user)):

    context = {
        "uid": uid,
    }
    return templates.TemplateResponse(request=request, name="home.html", context=context)

