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
    
    term_service = TermService(request.app.state.client.db, vocab)
    vocabobj = await term_service.get_vocab_info(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="export.html", context=context)

@router.post("/vocab/{vocab}/export", response_class=HTMLResponse)
async def export_post(vocab: str, request: Request, action: Annotated[str, Form()] = "",  user=Depends(auth_user)):

    term_service = TermService(request.app.state.client.db, vocab)
    vocabobj = await term_service.get_vocab_info(vocab)
    data = await term_service.export(action)

    # TODO implement "all" toggle for editable vocabularies
    if action == "json":
        # Generate JSON in consistent and human-readable format for revision control
        data_str = json.dumps(data, sort_keys=True, indent=2)
        headers={"Content-Disposition": f"attachment; filename={vocabobj.key}.json"}
        return PlainTextResponse(data_str, headers=headers)
    
    elif action == "csv":
        # TODO move CSV export to term_service
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

    # TODO return a message to say successful
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="export.html", context=context)


@router.get("/vocab/{vocab}/add", response_class=HTMLResponse)
async def add_term(vocab: str, request: Request, user=Depends(auth_user)):
    term_service = TermService(request.app.state.client.db, vocab)
    vocabobj = await term_service.get_vocab_info(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="add.html", context=context)


@router.post("/vocab/{vocab}/add", response_class=HTMLResponse)
async def edit_term_post(vocab: str,
                         request: Request,
                         term: Annotated[str, Form()] = "",
                         synonyms: Annotated[str, Form()] = "",
                         definition: Annotated[str, Form()] = "",
                         notes: Annotated[list, Form()] = "",
                         log: Annotated[str, Form()] = "",
                         user=Depends(auth_user)):

    term_service = TermService(request.app.state.client.db, vocab)
    vocabobj = await term_service.get_vocab_info(vocab)

    breakpoint()
    
    notes2=[]
    for n in notes:
        if len(n.strip())>0:
            notes2.append(n.strip())

    key = term2key(term)
    if key in ITEMS:
        # return back most of the data in the form to have another go
        context = {
            "statuses": get_statuses(),
            "clusters": get_clusters(),
            "term": term,
            "synonyms": synonyms,
            "definition": definition,
            "notes": notes2,
            "cluster": cluster,
            "src": src,
            "alert":f"Term '{term}' with key {key} already defined",
            "alert_type":"error",
        }
        return templates.TemplateResponse(request=request, name="add.html", context=context)

    item = {
        'key':key,
        'term':term.strip(),
        'synonyms':[s.strip() for s in synonyms.split(';') if len(s)>0],
        'definition':definition.strip(),
        'notes':notes2,
        'log':[log_entry(log)],
        'source':'',
        'rev':1, # set a revision
        }

    ITEMS[key] = item
    
    context = {
        "statuses": get_statuses(),
        "clusters": get_clusters(),
        "cluster": cluster,
        "src": src,
        "alert":f"Added '{term}'.",
        "alert_type":"success",
    }
    return templates.TemplateResponse(request=request, name="add.html", context=context)
