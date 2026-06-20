from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated, Union
from loguru import logger
from core.security import auth_user
from core import exceptions
from services.user import UserService
from services.term import TermService
import json

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request,
               user=Depends(auth_user)):
    term_service = TermService(request.app.state.client.db)
    vocabs = await term_service.get_vocabs()
    context = {
        "user": user,
        "vocabs": vocabs,
    }
    return templates.TemplateResponse(request=request, name="home.html", context=context)

@router.get("/vocab/{vocab}/digest", response_class=HTMLResponse)
async def vocab_digest(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    term_service = TermService(request.app.state.client.db, vocab)
    vocabobj = await term_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="digest.html", context=context)

@router.get("/vocab/{vocab}/list", response_class=HTMLResponse)
async def vocab_get(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    return await vocab_list(request, vocab, user)
@router.post("/vocab/{vocab}/list", response_class=HTMLResponse)
async def vocab_post(vocab: str,
                    request: Request,
                    filtr: Annotated[str, Form()] = "",
                    user=Depends(auth_user)):
    return await vocab_list(request, vocab, user, filtr=filtr)
async def vocab_list(request, vocab, user, filtr=""):

    # Every user has read access to all vocabs
    
    term_service = TermService(request.app.state.client.db, vocab)
    terms = await term_service.get_terms(filtr)
    vocabobj = await term_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "terms": terms,
        "filter": filtr,
    }
    return templates.TemplateResponse(request=request, name="list.html", context=context)

@router.get("/vocab/{vocab}/graph", response_class=HTMLResponse)
async def vocab_graph(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    term_service = TermService(request.app.state.client.db, vocab)
    elements = await term_service.get_graph_elements()
    vocabobj = await term_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "elements": elements,
    }
    return templates.TemplateResponse(request=request, name="graph.html", context=context)

@router.get("/vocab/{vocab}/graph2", response_class=HTMLResponse)
async def vocab_graph2(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    term_service = TermService(request.app.state.client.db, vocab)
    elements = await term_service.get_graph_elements()
    vocabobj = await term_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "elements": elements,
    }
    return templates.TemplateResponse(request=request, name="graph2.html", context=context)


@router.get("/vocab/{vocab}/term/{tid}", response_class=HTMLResponse)
async def show_term(vocab: str, tid: str, request: Request, user=Depends(auth_user)):

    term_service = TermService(request.app.state.client.db, vocab)

    term = await term_service.get_term(tid)
    vocabobj = await term_service.get_vocab_info(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "term": term,
    }
    return templates.TemplateResponse(request=request, name="term.html", context=context)

@router.get("/vocab/{vocab}/export", response_class=HTMLResponse)
async def export(vocab: str, request: Request, user=Depends(auth_user)):

    vocabobj = await term_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="export.html", context=context)

@router.post("/vocab/{vocab}/export")
async def export_post(vocab: str, request: Request, action: Annotated[str, Form()] = "",  user=Depends(auth_user)):

    term_service = TermService(request.app.state.client.db, vocab)
    terms = await term_service.get_terms()
    vocabobj = await term_service.get_vocab_info(vocab)

    export_data = []
    for item in terms:
        out = {}
        for k,v in item.model_dump().items():
            if k[0] != '_':
                # Don't export any temporary keys
                out[k] = v
            elif k == '_key':
                out['key'] = v
        export_data.append(out)
    # sort terms on key
    export_data.sort(key=lambda x:x['key'].lower()) 
        
    if action == "json":
        # Generate JSON in consistent and human-readable format for revision control
        data_str = json.dumps({'terms':export_data}, sort_keys=True, indent=2)
        return PlainTextResponse(data_str,
                            headers={"Content-Disposition": f"attachment; filename=qcvocab.json"}
                            )
    elif action == "csv":
        fp = io.StringIO()
        fieldnames = ['key', 'term', 'definition', 'section', 'source', 'rev', 'tags', 'status', 'cluster', 'src']
        csvwriter = csv.writer(fp, quoting=csv.QUOTE_NONNUMERIC)
        csvwriter.writerow(fieldnames+['synonyms','notes','log'])
        for item in export_data:
            row = [item[f] for f in fieldnames]
            row.append(";".join(item['synonyms']))
            row.append(";".join(item['notes']))
            row.append(";".join([str(l) for l in item['log']]))
            csvwriter.writerow(row)
        return PlainTextResponse(fp.getvalue(),
                            headers={"Content-Disposition": f"attachment; filename=qcvocab.csv"}
                            )

        
    context = {
    }
    
    return templates.TemplateResponse(request=request, name="export.html", context=context)
