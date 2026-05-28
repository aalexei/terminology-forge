from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated, Union
from loguru import logger
from routes.authentication import auth_user

from core import exceptions
from services.user import UserService
from services.term import TermService

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


@router.get("/vocab/{vocab}/list", response_class=HTMLResponse)
async def root_get(vocab: str,
                   request: Request,
                   uid=Depends(auth_user)):
    return await vocab_list(request, vocab, uid)
@router.post("/vocab/{vocab}/list", response_class=HTMLResponse)
async def root_post(vocab: str,
                    request: Request,
                    filtr: Annotated[str, Form()] = "",
                    uid=Depends(auth_user)):
    return await vocab_list(request,vocab, uid, filtr=filtr)
async def vocab_list(request, vocab, uid, filtr=""):

    user_service = UserService(request.app.state.client.db)
    user = await user_service.get(uid)

    # Every user has read access to all vocabs
    
    term_service = TermService(request.app.state.client.db, vocab)
    terms = await term_service.get_terms(filtr)
    
    context = {
        "user": user,
        "terms": terms,
        "filter": filtr,
        "vocab": vocab,
    }
    return templates.TemplateResponse(request=request, name="list.html", context=context)

@router.get("/vocab/{vocab}/term/{tid}", response_class=HTMLResponse)
async def show_term(vocab: str, tid: str, request: Request, uid=Depends(auth_user)):

    user_service = UserService(request.app.state.client.db)
    user = await user_service.get(uid)
    term_service = TermService(request.app.state.client.db, vocab)

    term = await term_service.get_term(tid)
    
    context = {
        "user": user,
        "vocab": vocab,
        "term": term,
    }
    return templates.TemplateResponse(request=request, name="term.html", context=context)

@router.get("/vocab/{vocab}/export", response_class=HTMLResponse)
async def show_term(vocab: str, request: Request, uid=Depends(auth_user)):

    user_service = UserService(request.app.state.client.db)
    user = await user_service.get(uid)
    #term_service = TermService(request.app.state.client.db, vocab)

    #term = await term_service.get_term(tid)
    
    context = {
        "user": user,
        "vocab": vocab,
    }
    return templates.TemplateResponse(request=request, name="export.html", context=context)
