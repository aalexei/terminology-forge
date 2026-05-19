from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated, Union
from loguru import logger
from routes.authentication import auth_user

from core import exceptions
# from db.schema import User
from services.user import UserService

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request,
               uid=Depends(auth_user)):

    user_service = UserService(request.app.state.client.db)
    user = await user_service.get(uid)
    
    context = {
        "uid": uid,
        "user": user,
    }
    return templates.TemplateResponse(request=request, name="home.html", context=context)


@router.get("/list/{vocab}", response_class=HTMLResponse)
async def root_get(vocab: str,
                   request: Request,
                   uid=Depends(auth_user)):
    return vocab_list(request)
@router.post("/list/{vocab}", response_class=HTMLResponse)
async def root_post(vocab: str,
                    request: Request,
                    filtr: Annotated[str, Form()] = "",
                    uid=Depends(auth_user)):
    return vocab_list(request,filtr=filtr)
def vocab_list(request, filtr=""):
    items = [extend_item(t) for t in ITEMS.values()]
    
    context = {
        "uid": uid,
        "items": items,
        "filter": filtr,
    }
    return templates.TemplateResponse(request=request, name="list.html", context=context)


# @router.get("/", response_class=HTMLResponse)
# async def root(request: Request, uid=Depends(auth_user)):

#     context = {
#         "uid": uid,
#     }
#     return templates.TemplateResponse(request=request, name="home.html", context=context)

