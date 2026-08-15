from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import starlette.status as status
from typing import Annotated, Union
from loguru import logger
from core.security import auth_user
from core import exceptions
from core.util import ago
from db import schema
from services.user import UserService
from services.vocab import VocabService, term2key
import json, io, csv

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
templates.env.filters['ago'] = ago

# ---------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def home(request: Request,
               user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db)
    vocabs = await vocab_service.get_vocabs()
    context = {
        "user": user,
        "vocabs": vocabs,
    }
    return templates.TemplateResponse(request=request, name="home.html", context=context)


# ---------------------------------------------------
@router.get("/user", response_class=HTMLResponse)
async def home(request: Request,
               user=Depends(auth_user)):
    context = {
        "user": user,
    }
    return templates.TemplateResponse(request=request, name="user.html", context=context)


# ---------------------------------------------------
@router.get("/vocab/{vocab}/digest", response_class=HTMLResponse)
async def vocab_digest(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    log = await vocab_service.get_log(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "log": log,
    }
    return templates.TemplateResponse(request=request, name="digest.html", context=context)


# ---------------------------------------------------
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
    # Use name of filtr as filter is a python keyword
    return await vocab_list(request, vocab, user, filtr=filtr)

async def vocab_list(request, vocab, user, filtr=""):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    terms = await vocab_service.get_terms(filtr)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "terms": terms,
        "filtr": filtr,
    }
    return templates.TemplateResponse(request=request, name="list.html", context=context)


# ---------------------------------------------------
@router.get("/vocab/{vocab}/graph", response_class=HTMLResponse)
async def vocab_graph(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    elements = await vocab_service.get_graph_elements()
    vocabobj = await vocab_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "elements": elements,
    }
    return templates.TemplateResponse(request=request, name="graph.html", context=context)


# ---------------------------------------------------
@router.get("/vocab/{vocab}/graph2", response_class=HTMLResponse)
async def vocab_graph2(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    elements = await vocab_service.get_graph_elements()
    vocabobj = await vocab_service.get_vocab_info(vocab)
    context = {
        "user": user,
        "vocab": vocabobj,
        "elements": elements,
    }
    return templates.TemplateResponse(request=request, name="graph2.html", context=context)


# ---------------------------------------------------
@router.get("/vocab/{vocab}/tasks", response_class=HTMLResponse)
async def vocab_tasks(vocab: str,
                   request: Request,
                   user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    tasks = await vocab_service.get_tasks()
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "tasks": tasks,
    }
    return templates.TemplateResponse(request=request, name="tasks.html", context=context)

# ---------------------------------------------------
@router.post("/vocab/{vocab}/tasks", response_class=HTMLResponse)
async def vocab_tasks(vocab: str,
                   request: Request,
                   task_name: Annotated[str, Form()],
                   task_order: Annotated[float, Form()],
                   task_description: Annotated[str, Form()] = "",
                   user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)

    await vocab_service.add_task(task_name, task_description, task_order)
    
    vocabobj = await vocab_service.get_vocab_info(vocab)
    tasks = await vocab_service.get_tasks()
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "tasks": tasks,
    }
    return templates.TemplateResponse(request=request, name="tasks.html", context=context)

# ---------------------------------------------------
@router.get("/vocab/{vocab}/task/{task}/inline/edit", response_class=HTMLResponse)
async def vocab_task_inline_edit(vocab: str,
                                 task: str,
                                 request: Request,
                                 user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    
    task = await vocab_service.get_task(task)
    context = {
        "vocab": vocabobj,
        "task": task,
    }
    return templates.TemplateResponse(request=request, name="task_edit_component.html", context=context)

# ---------------------------------------------------
@router.post("/vocab/{vocab}/task/{task}/inline/edit", response_class=HTMLResponse)
async def put_vocab_task_inline(vocab: str,
                            task: str,
                            request: Request,
                            task_name: Annotated[str, Form()],
                            task_order: Annotated[float, Form()],
                            task_description: Annotated[str, Form()] = "",
                            task_locked: Annotated[bool, Form()] = False,
                            user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)

    await vocab_service.update_task(task, task_name, task_description, task_order, task_locked)
    target = f"/vocab/{vocab}/tasks"
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)

# ---------------------------------------------------
@router.get("/vocab/{vocab}/task/{tid}", response_class=HTMLResponse)
async def vocab_task(vocab: str,
                      tid: str,
                   request: Request,
                   user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)

    task = await vocab_service.get_task(tid)
    works = await vocab_service.get_task_works(tid)
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "task": task,
        "works": works,
    }
    return templates.TemplateResponse(request=request, name="task.html", context=context)


# ---------------------------------------------------
@router.post("/x/vocab/{vocab}/term/{term_key}/task/{task_key}/setwork", response_class=HTMLResponse)
async def set_work(vocab: str,
                   term_key: str,
                   task_key: str,
                   request: Request,
                   work_id: Annotated[str, Form()],
                   content: Annotated[str, Form()],
                   user = Depends(auth_user)
                   ):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    response = await vocab_service.set_work(term_key, task_key, work_id, content, user)
    # TODO log changes
    
    return HTMLResponse(response)



# ---------------------------------------------------
@router.get("/vocab/{vocab}/term/{tid}", response_class=HTMLResponse)
async def show_term(vocab: str, tid: str, request: Request, user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)

    term = await vocab_service.get_term(tid)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    if vocabobj.editable:
        log = await vocab_service.get_log(f"{vocab}/{tid}")
        works = await vocab_service.get_term_works(tid)
    else:
        # The UI won't show these anyway
        log = []
        works = []

    context = {
        "user": user,
        "vocab": vocabobj,
        "term": term,
        "log": log,
        "works": works,
    }
    return templates.TemplateResponse(request=request, name="term.html", context=context)


# ---------------------------------------------------
@router.post("/x/settags", response_class=HTMLResponse)
async def set_tags(request: Request,
                   key: Annotated[str, Form()],
                   vocab: Annotated[str, Form()],
                   tags: Annotated[str, Form()],
                   user = Depends(auth_user)
                   ):

    # TODO fix up url to include vocab and term etc
    vocab_service = VocabService(request.app.state.client.db, vocab)
    tags = [t.strip() for t in tags.split()]
    respose = await vocab_service.set_tags(key, tags)
    
    return HTMLResponse("<b>Saved!</b>")



# ---------------------------------------------------
@router.get("/vocab/{vocab}/export", response_class=HTMLResponse)
async def export(vocab: str, request: Request, user=Depends(auth_user)):
    
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
    }
    return templates.TemplateResponse(request=request, name="export.html", context=context)


# ---------------------------------------------------
@router.post("/vocab/{vocab}/export", response_class=HTMLResponse)
async def export_post(vocab: str, request: Request, action: Annotated[str, Form()] = "",  user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    data = await vocab_service.export(action)

    # TODO implement "all" toggle for editable vocabularies
    if action == "json":
        # Generate JSON in consistent and human-readable format for revision control
        data_str = json.dumps(data, sort_keys=True, indent=2)
        headers={"Content-Disposition": f"attachment; filename={vocabobj.key}.json"}
        return PlainTextResponse(data_str, headers=headers)
    
    elif action == "csv":
        # TODO move CSV export to vocab_service
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


# ---------------------------------------------------
@router.get("/vocab/{vocab}/add", response_class=HTMLResponse)
async def add_term(vocab: str, request: Request, user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "tags": "status.propose",
    }
    return templates.TemplateResponse(request=request, name="add.html", context=context)

# ---------------------------------------------------
@router.post("/vocab/{vocab}/add", response_class=HTMLResponse)
async def add_term_post(vocab: str,
                         request: Request,
                         term: Annotated[str, Form()] = "",
                         synonyms: Annotated[str, Form()] = "",
                         definition: Annotated[str, Form()] = "",
                         notes: Annotated[list, Form()] = "",
                         tags: Annotated[str, Form()] = "",
                         comment: Annotated[str, Form()] = "",
                         log: Annotated[str, Form()] = "",
                         user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)

    notes2=[]
    for n in notes:
        if len(n.strip())>0:
            notes2.append(n.strip())

    key = term2key(term)
    
    if await vocab_service.has_term(key):
        # return back most of the data in the form to have another go
        context = {
            "user": user,
            "vocab": vocabobj,
            "term": term,
            "synonyms": synonyms,
            "definition": definition,
            "notes": notes2,
            "comment": comment,
            "tags": tags,
            "log": log,
            "alert":f"Term '{term}' with key '{key}' already defined",
            "alert_type":"error",
        }
        return templates.TemplateResponse(request=request, name="add.html", context=context)

    item = schema.Term(
        key = key,
        term = term.strip(),
        synonyms = [s.strip() for s in synonyms.split(';') if len(s)>0],
        definition = definition.strip(),
        notes = notes2,
        source = '',
        context = '',
        section = ''
    )
    
    await vocab_service.add_term(item)
    # TODO tags
    # TODO comment
    
    await vocab_service.add_log(user.github, f"{vocab}/{item.key}", log)
    # TODO improve log .. strings or objects
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "tags": tags,
        "alert": f"Added '{term}'.",
        "alert_type":"success",
    }
    return templates.TemplateResponse(request=request, name="add.html", context=context)


# ---------------------------------------------------
@router.get("/vocab/{vocab}/edit/{tid}", response_class=HTMLResponse)
async def edit_term(vocab: str, tid: str, request: Request, user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    term = await vocab_service.get_term(tid)

    context = {
        "user": user,
        "vocab": vocabobj,
        "term": term,
    }
    return templates.TemplateResponse(request=request, name="edit.html", context=context)


# ---------------------------------------------------
@router.post("/vocab/{vocab}/edit/{tid}", response_class=HTMLResponse)
async def edit_term_post(vocab: str,
                         tid: str,
                         request: Request,
                         term: Annotated[str, Form()] = "",
                         synonyms: Annotated[str, Form()] = "",
                         definition: Annotated[str, Form()] = "",
                         section: Annotated[str, Form()] = "",
                         context: Annotated[str, Form()] = "",
                         source: Annotated[str, Form()] = "",
                         notes: Annotated[list, Form()] = "",
                         log: Annotated[str, Form()] = "",
                         rev: Annotated[int, Form()] = 1,
                         user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)

    notes2=[]
    for n in notes:
        if len(n.strip())>0:
            notes2.append(n.strip())

    item = schema.Term(
        key = tid,
        term = '', # Not actually updated
        synonyms = [s.strip() for s in synonyms.split(';') if len(s)>0],
        definition = definition.strip(),
        notes = notes2,
        source = source,
        context = context,
        section = section
    )

    # TODO Seems fragile to have to set everything and del term
    
    await vocab_service.update_term(item)
    
    await vocab_service.add_log(user.github, f"{vocab}/{item.key}", log)

    term = await vocab_service.get_term(tid)

    context = {
        "user": user,
        "vocab": vocabobj,
        "term": term,
        "alert": f"Updated '{term.key}'.",
        "alert_type":"success",
    }
    return templates.TemplateResponse(request=request, name="edit.html", context=context)


    
# ---------------------------------------------------
@router.get("/vocab/{vocab}/editterm/{tid}", response_class=HTMLResponse)
async def edit_theterm(vocab: str, tid: str, request: Request, user=Depends(auth_user)):
    vocab_service = VocabService(request.app.state.client.db, vocab)
    vocabobj = await vocab_service.get_vocab_info(vocab)
    term = await vocab_service.get_term(tid)

    refs = await vocab_service.get_refs(tid)
    
    context = {
        "user": user,
        "vocab": vocabobj,
        "item": term,
        "refs": refs,
    }
    return templates.TemplateResponse(request=request, name="editterm.html", context=context)


# ---------------------------------------------------
@router.post("/vocab/{vocab}/editterm/{tid}", response_class=HTMLResponse)
async def edit_theterm_post(vocab: str,
                         tid: str,
                         request: Request,
                         new_term: Annotated[str, Form()] = "",
                         log: Annotated[str, Form()] = "",
                         user=Depends(auth_user)):

    vocab_service = VocabService(request.app.state.client.db, vocab)

    log = log.strip()
    # Collect together changes that potentially should be made
    batch_changes = []
    
    batch_changes.append(
        schema.Change(key=tid, context='term', value=new_term)
    )
    
    # Potentially changed linked terms
    form_data = await request.form()
    for k,v in form_data.items():
        # Form keys have the patterns:
        #   link--<term_key>--definition
        #   link--<term_key>--note-<i>
        if not k.startswith("link--"):
            continue
        bits = k.split('--')
        ckey = bits[1]
        cref = bits[2].split('-')
        context = cref[0]
        cvalue = v.strip()
        n = 0
        if len(cref)>1:
            n = int(cref[1])
        batch_changes.append(
            schema.Change(key=ckey, context=context, value=cvalue, n=n)
        )

    message = await vocab_service.batch_change(batch_changes, user.github, log)

    # Refresh the data and present form again
    vocabobj = await vocab_service.get_vocab_info(vocab)
    term = await vocab_service.get_term(tid)
    refs = await vocab_service.get_refs(tid)

    context = {
        "user": user,
        "vocab": vocabobj,
        "item": term,
        "refs": refs,
        "alert": message,
        "alert_type":"success",
    }
    return templates.TemplateResponse(request=request, name="editterm.html", context=context)

