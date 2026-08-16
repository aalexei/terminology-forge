import re
import json
import time
from db import schema
from core.util import diff

def term2key(term):
    """
    Convert term to canonical key
    valid characters: [a-z0-9_]
    term -> lowercase -> non (letters or numbers) to _
    """
    return re.sub(r"[^a-z0-9]","_",term.lower())


def linkify(so, links, vocab):
    '''
    Transform link of form [[key][text]] or [[key]] to actual html links
    '''
    raw = so.group(1)
    pieces = raw.split('][')
    key = pieces[0].strip()
    
    if '/' in key:
        target_vocab,target_key = key.split('/')
    else:
        target_key = key
        target_vocab = vocab
        
    target_id = f"{target_vocab}/{target_key}"
        
    if len(pieces)>1:
        text = pieces[1].strip()
    else:
        if target_id in links:
            text = links[target_id]
        else:
            text = key

    if target_id in links:
        out = f'<a href="/vocab/{target_vocab}/term/{target_key}" class="link">{text}</a>'
    else:
        # highlight that the link is dangling
        out = f'<a href="#" class="link link-warning">{text}</a>'

    return out

class LinkedText:
    '''
    Helper class for text with links
    '''
    def __init__(self, text):
        self.text = text

    def has_key(self, key):
        return f'[[{key}]' in self.text

    def links(self):
        return re.findall(r'\[\[([^]]+)', self.text)

    def html(self):
        return self.text

    def highlight_key(self, key):
        html = self.text.replace(f'[[{key}]',f'[[<span class="text-secondary">{key}</span>]')
        return html

    def linkify(self, links, vocab):
        linkf = lambda x: linkify(x, links, vocab)
        return re.sub(r'\[\[(.*?)\]\]', linkf, self.text)


def extend_term(term, tags, links, vocab):
    '''
    Add extra fields for display
    '''

    term._tags = tags
    term._links = { l['_id']:l['term'] for l in links }
    term._vocab = vocab
    
    term._definition_html = LinkedText(term.definition).linkify(term._links, term._vocab)

    notes_html = []
    for n in term.notes:
        notes_html.append(LinkedText(n).linkify(term._links, term._vocab))
    term._notes_html = notes_html
        
    return term


async def relink(G, t1):
    """
    Recreate the links from this item's definition and notes out.
    """
    vcol = t1['_id'].split('/')[0]
    TERM = G.vertex_collection(vcol)
    LINK = G.edge_collection('link')

    # Delete existing links
    existing_links = await LINK.edges(t1['_id'], direction='out')
    existing_links = existing_links['edges']
    for link in existing_links:
        await LINK.delete(link['_id'])

    # Reform links from definition and notes
    async def add_link(t1, target, context):
        t2 = await TERM.get(target)
        if t2 is not None:
            await LINK.insert({'_from':t1['_id'], '_to':t2['_id'], 'context': context})
    for target in LinkedText(t1['definition']).links():
        await add_link(t1,target,'def')
    for n in t1['notes']:
        for target in LinkedText(n).links():
            await add_link(t1,target,'note')

class Ref:
    def __init__(self, key, term, context, src, src_html=""):
        self.key = key
        self.term = term
        self.context = context
        self.src = src
        if src_html=="":
            src_html=src
        self.src_html = src_html

class VocabService:

    collection = None
    
    def __init__(self, db, vocab:str, user:schema.User):
        self.db = db
        self.collection: str = vocab
        self.user: schema.User = user


    async def add_log(self, target, summary):
        """
        Add an entry to the log.
        """
        log = self.db.collection('log')
        log_entry = schema.Log(
            timestamp = time.time(),
            user = self.user.username,
            target = target,
            summary = summary,
        )
        await log.insert(log_entry.model_dump(exclude_unset=True))


    async def get_terms(self, filtr=''):

        query_filter = r"""
        LET search_terms = REGEX_SPLIT(LOWER(@filtr), "\\s+")
        FOR t in @@coll
          LET tags = (
            FOR v IN INBOUND t._id tagged
            RETURN {"_id":v._id, "name":v.name, "description":v.description} 
            )
          LET combined = LOWER(CONCAT_SEPARATOR(" ",
            t.term,
            t.definition,
            CONCAT_SEPARATOR(" ",tags[*].name),
            CONCAT_SEPARATOR(" ",t.notes[*])
          ))
          FILTER LENGTH(
            FOR s in search_terms
              FILTER CONTAINS(combined, s)
              RETURN 1)
          == LENGTH(search_terms)
        
          LET links = (
            FOR v IN OUTBOUND t._id link
            RETURN {"_id":v._id, "term":v.term} 
            )
          LET indegree = LENGTH(FOR e IN INBOUND t._id link RETURN true)
          LET outdegree = LENGTH(FOR e IN OUTBOUND t._id link RETURN true)
        RETURN { "term":t, "tags":tags, "links":links, "indegree":indegree, "outdegree":outdegree }
        """        
        
        query = """
        FOR t IN @@coll
          LET tags = (
            FOR v IN INBOUND t._id tagged
            RETURN {"_id":v._id, "name":v.name, "description":v.description} 
            )
          LET links = (
            FOR v IN OUTBOUND t._id link
            RETURN {"_id":v._id, "term":v.term} 
            )
          LET indegree = LENGTH(FOR e IN INBOUND t._id link RETURN true)
          LET outdegree = LENGTH(FOR e IN OUTBOUND t._id link RETURN true)
        RETURN { "term":t, "tags":tags, "links":links, "indegree":indegree, "outdegree":outdegree }
        """
        filtr = filtr.strip()

        if len(filtr) == 0:
            cursor = await self.db.aql.execute(
                query,
                bind_vars={"@coll": self.collection,
                           },
            )
        else:
            cursor = await self.db.aql.execute(
                query_filter,
                bind_vars={"@coll": self.collection,
                           "filtr": filtr},
            )
        terms = []
        async with cursor as ctx:
            async for t in ctx:
                T = schema.Term(**t["term"])
                extend_term(T, t["tags"], t["links"], self.collection)
                T._indegree = t["indegree"]
                T._outdegree = t["outdegree"]
                terms.append(T)
                
        return terms

    
    async def get_term(self, tid):
        query = """
        LET tags = (
          FOR v IN INBOUND @tid tagged
            RETURN {"_id":v._id, "name":v.name} 
        )
        LET links = (
          FOR v IN OUTBOUND @tid link
            RETURN {"_id":v._id, "term":v.term} 
        )
        LET indegree = LENGTH(FOR e IN INBOUND @tid link RETURN true)
        LET outdegree = LENGTH(FOR e IN OUTBOUND @tid link RETURN true)
        RETURN {"term":DOCUMENT(@tid), "tags":tags, "links":links, "indegree":indegree, "outdegree":outdegree}
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"tid": f"{self.collection}/{tid}"},
        )
        async with cursor as ctx:
            async for t in ctx:
                T = schema.Term(**t["term"])
                extend_term(T, t["tags"], t["links"], self.collection)
                T._indegree = t["indegree"]
                T._outdegree = t["outdegree"]
                
        return T

    
    async def has_term(self, tid):
        TERMS = self.db.collection(self.collection)
        return await TERMS.has(tid) 

    
    async def add_term(self, term):
        TERMS = self.db.collection(self.collection)
        await TERMS.insert(term.model_dump(by_alias=True))
        
        # Relink
        TERM = await TERMS.get(term.key)
        # TODO go off preferences instead of hard-coded TFG
        GRAPH = self.db.graph('TFG')
        await relink(GRAPH, TERM)

        
    async def update_term(self, term):
        TERMS = self.db.collection(self.collection)

        # Adjust the data removing what we don't want to update
        term_data = term.model_dump(by_alias=True)
        del term_data['term']
        
        await TERMS.update(term_data)

        # Relink
        TERM = await TERMS.get(term.key)
        # TODO go off preferences instead of hard-coded TFG
        graph = self.db.graph('TFG')
        await relink(graph, TERM)


    async def get_tag_names(self):

        tag_names = []
        cursor = await self.db.aql.execute(
            "FOR t IN @@coll RETURN t.name",
            bind_vars={"@coll": f"{self.collection}_tag"})
        async for tag in cursor:
            tag_names.append(tag)
        return tag_names

    
    async def set_tags(self, term_key, tag_names):

        # TODO go off name in defaults
        graph = self.db.graph("TFG")
        
        all_tag_names = await self.get_tag_names()
        As = set(all_tag_names)

        Ts = set(tag_names)
        
        # New tags and edges to create
        Ns = Ts-As

        term_id = f"{self.collection}/{term_key}"
        
        query = """
        FOR v,e IN INBOUND @tid tagged
          RETURN {"_id":e._id, "name":v.name} 
        """
        edges = []
        cursor = await self.db.aql.execute(query, bind_vars={"tid": term_id})
        async for e in cursor:
            edges.append(e)

        # Remove edges not in tag set Ts
        for e in edges:
            if e['name'] not in Ts:
                await graph.delete_edge(e['_id'])

        # New existing tags to link
        tags = self.db.collection(f"{self.collection}_tag")
        Es = set([e['name'] for e in edges])
        Ls = Ts-Es-Ns
        for tag_name in Ls:
            matches = await tags.find({'name': tag_name})
            tag = matches.pop()
            await graph.link("tagged", tag['_id'], term_id)

        for tag_name in Ns:
            tag = await graph.insert_vertex(f"{self.collection}_tag", {"name": tag_name})
            await graph.link("tagged", tag['_id'], term_id)
            
        return True

    
    async def get_log(self, target):

        # Execute the query
        cursor = await self.db.aql.execute('''
        FOR entry IN log 
          FILTER STARTS_WITH(entry.target, @target) 
          SORT entry.timestamp DESC
          RETURN entry''',
            bind_vars={"target": target}
        )
        entries = []
        async for entry in cursor:
            entries.append(entry)
            
        return entries 

    
    async def get_vocab_info(self, vocab):
        vocabularies = self.db.collection("vocabularies")
        infodata = await vocabularies.get(vocab)
        info = schema.Vocabulary(**infodata)
        return info

    
    async def get_vocabs(self):

        query = """
        FOR v IN vocabularies
        RETURN v
        """
        cursor = await self.db.aql.execute(
            query
        )
        vocabs = []
        async with cursor as ctx:
            async for v in ctx:
                V = schema.Vocabulary(**v)
                vocabs.append(V)
                
        return vocabs

    
    async def get_graph_elements(self):

        query = """
        FOR t IN @@coll
          LET tags = (
            FOR v IN INBOUND t._id tagged
            RETURN {"_id":v._id, "name":v.name, "description":v.description} 
            )
          LET links = (
            FOR v,e IN OUTBOUND t._id link
            RETURN {"_id":v._id, "term":v.term, "context":e.context} 
            )

        RETURN { "term":t, "tags":tags, "links":links}
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"@coll": self.collection},
        )

        # Collect together data for js graph
        elements = { 'nodes':[], 'edges':[] }
        async for t in cursor:
            links = {l["_id"]:l["term"] for l in t["links"]}
            elements['nodes'].append({
                'data': {
                    'id': t['term']['_id'],
                    'key': t['term']['_key'],
                    'term': t['term']['term'],
                    'definition': t['term']['definition'],
                    'definition_html': LinkedText(t['term']['definition']).linkify(links, self.collection),
                    'tags': t['tags'],
                }})
            for lnk in t['links']:
                if lnk['context'] == 'def':
                    elements['edges'].append({
                        'data': {
                            'source': t['term']['_id'],
                            'target':lnk['_id'],
                        }})

        return json.dumps(elements)

    
    async def export(self, action, all=True):

        if action == "json":

            # Get vocabulary info
            info_item = await self.get_vocab_info(self.collection)
            info = info_item.model_dump(by_alias=False)

            # Get all terms
            terms = []
            cursor = await self.db.aql.execute(
                "FOR doc IN @@coll RETURN doc",
                bind_vars={"@coll": self.collection},
            )
            async for t in cursor:
                T = schema.Term(**t)
                T2 = T.model_dump(by_alias=False)
                if not info['editable'] and 'rev' in T2:
                    del T2['rev']
                terms.append(T2)
            terms.sort(key=lambda x:x['key'].lower())

            if not info['editable'] or not all:
                # Bundle everything together
                export_data={
                    'info': info,
                    'terms': terms,
                }
            else:
                # Vocab is editable
                # Get all tags and their targets
                tags = []
                query = """
                FOR tag IN @@coll
                  SORT tag.name
                  LET targets = (
                    FOR v IN OUTBOUND tag._id tagged
                      SORT v._key
                      RETURN v._key
                  )
                RETURN { "tag":tag, "targets":targets }
                """
                cursor = await self.db.aql.execute(
                    query,
                    bind_vars={"@coll": f"{self.collection}_tag"},
                )
                async for t in cursor:
                    T = schema.Tag(**t['tag'])
                    T2 = T.model_dump(by_alias=False)
                    T2['targets'] = t['targets']
                    del T2['key']
                    tags.append(T2)

                # Get all tasks and their targets
                tasks = []
                query = """
                FOR task IN @@coll
                  SORT task.name
                  LET works = (
                    FOR v,e IN OUTBOUND task._id work
                      SORT v._key
                      RETURN {content:e.content, target:v._key}
                  )
                RETURN { "task":task, "works":works }
                """
                cursor = await self.db.aql.execute(
                    query,
                    bind_vars={"@coll": f"{self.collection}_task"},
                )
                async for t in cursor:
                    T = schema.Task(**t['task'])
                    T2 = T.model_dump(by_alias=False)
                    T2['works'] = t['works']
                    del T2['key']
                    tasks.append(T2)
                
                # TODO logs
                # TODO comments

                # Bundle everything together
                export_data={
                    'info': info,
                    'tags': tags,
                    'terms': terms,
                    'tasks': tasks,
                }
    
            return export_data

        # TODO implement CSV export
        
        else:
            raise Exception()

        
    
    async def get_tasks(self):
        
        tasks = []
        cursor = await self.db.aql.execute(
            "FOR t IN @@coll SORT t.order RETURN t",
            bind_vars={"@coll": f"{self.collection}_task"})
        async for task in cursor:
            tasks.append(schema.Task(**task))
        return tasks 

    
    async def get_task(self, task_key):
        """
        Get a task by key
        """
        TASKS = self.db.collection(f"{self.collection}_task")
        task = await TASKS.get(task_key)
        return schema.Task(**task)

    
    async def add_task(self, name, description, order):
        """
        Add a new task
        """
        TASKS = self.db.collection(f"{self.collection}_task")
        T = schema.Task(name=name, description=description, order=order)
        await TASKS.insert(T.model_dump(exclude_unset=True))

    
    async def update_task(self, key, name, description, order, locked):
        """
        Update an existing task
        """
        TASKS = self.db.collection(f"{self.collection}_task")
        T = schema.Task(key=key, name=name, description=description, order=order, locked=locked)
        # TODO update log
        # TODO record user in vocab initialisation (make logging easier)
        await TASKS.update(T.model_dump(exclude_unset=True))

    
    async def get_task_works(self, task_key):
        """
        Get the works and terms linked to a task
        """
        query = """
        FOR term,e IN OUTBOUND @task_id work
          SORT term.term
          RETURN { "term_key":term._key, "vocab":@vocab,
                   "term_term":term.term, 
                   "work_id":e._id,  "work_content":e.content } 
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"task_id": f"{self.collection}_task/{task_key}", "vocab":self.collection},
        )
        works = []
        async for t in cursor:
            works.append(t)

        return works

    
    async def get_term_works(self, term_key):
        """
        Get the tasks and works linked to a term
        """
        # Get tasks and include work if available
        query = """
        FOR t IN @@coll
          SORT t.order
          LET w = (
            FOR e in work
            FILTER e._from == t._id && e._to == @term_id
            LIMIT 1
            RETURN e
          )[0]
        RETURN { task_key:t._key, task_name:t.name,
                 task_description:t.description, task_order:t.order,
                 work_id:w._id, work_content:w.content }
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={
                "@coll": f"{self.collection}_task",
                "term_id": f"{self.collection}/{term_key}",
            },
        )
        works = []
        async for t in cursor:
            works.append(t)
                
        return works


    async def set_work(self, term_key, task_key, work_id, content):
        """
        Set work on task
        """
        content = content.strip()

        WORK = self.db.collection("work")
        TASK = self.db.collection(f"{self.collection}_task")

        task = schema.Task(**(await TASK.get(task_key)))
        if task.locked:
            # Check the task has not been locked since form
            return "Task is locked"
        
        if work_id == 'None':
            # Create edge
            # TODO what if edge was created in the mean time?
            work_edge = {
                "_from": f"{self.collection}_task/{task_key}",
                "_to": f"{self.collection}/{term_key}",
                "content": content,
                }
            await WORK.insert(work_edge)
            response = f'Created content for task "{task.name}"'
            
        elif len(content)==0:
            # Delete edge
            await WORK.delete(work_id)
            response = f'Deleted content for task "{task.name}"'
            
        else:
            # Update edge
            # TODO what if content was changed in the mean time?
            await WORK.update({'_id':work_id, 'content':content})
            response = f'Updated content for task "{task.name}"'

        await self.add_log(
            target = f"{self.collection}/{term_key}",
            summary = response,
        )

        return response

    async def get_refs(self, tid):
        query = """
        FOR v IN INBOUND @tid link
          OPTIONS { uniqueVertices: "global", bfs: true }
          RETURN v 
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"tid": f"{self.collection}/{tid}"},
        )
        refs = []
        async for t in cursor:
            T = schema.Term(**t)
            if LinkedText(T.definition).has_key(tid):
                src_html = LinkedText(T.definition).highlight_key(tid)
                refs.append( Ref(T.key, T.term, 'definition', T.definition, src_html) )
            for i,n in enumerate(T.notes):
                if LinkedText(n).has_key(tid):
                    src_html = LinkedText(n).highlight_key(tid)
                    refs.append( Ref(T.key, T.term, f'note-{i}', n, src_html) )

        return refs

    
    async def batch_change(self, batch_changes, username, log=""):

        # For the message
        changes = []
        VOCAB = self.db.collection(self.collection)
        LOG = self.db.collection('log')

        # TODO relink changed terms
        for change in batch_changes:
            if change.context == "term":
                term = await self.get_term(change.key)
                if term.term != change.value:
                    d = diff(term.term,change.value)
                    m = f"{term.key}.term: {d}"
                    changes.append(m)
                    # TODO update term
                    await VOCAB.update({'_key':change.key, 'term':change.value})
                    
                    log_entry = schema.Log(
                        timestamp = time.time(),
                        user = username,
                        target = f"{self.collection}/{change.key}",
                        summary = log,
                        diff = m,
                    )
                    await LOG.insert(log_entry.model_dump(exclude_unset=True))

            elif change.context == "definition":
                term = await self.get_term(change.key)
                if term.definition != change.value:
                    d = diff(term.definition,change.value)
                    m = f"{term.key}.definition: {d}"
                    changes.append(m)
                    # TODO update definition
                    await VOCAB.update({'_key':change.key, 'definition':change.value})
                    
                    log_entry = schema.Log(
                        timestamp = time.time(),
                        user = username,
                        target = f"{self.collection}/{change.key}",
                        summary = log,
                        diff = m,
                    )
                    await LOG.insert(log_entry.model_dump(exclude_unset=True))
                    
            elif change.context == "note":
                term = await self.get_term(change.key)
                if term.notes[change.n] != change.value:
                    d = diff(term.notes[change.n],change.value)
                    m = f"{term.key}.notes[{change.n}]: {d}"
                    changes.append(m)
                    # TODO update note
                    term.notes[change.n] = change.value
                    await VOCAB.update({'_key':change.key, 'notes':term.notes})

                    log_entry = schema.Log(
                        timestamp = time.time(),
                        user = username,
                        target = f"{self.collection}/{change.key}",
                        summary = log,
                        diff = m,
                    )
                    await LOG.insert(log_entry.model_dump(exclude_unset=True))
                    
            else:
                # Should not get here as all internal
                raise Exception(f"Unknown change item {change.context}")

        message = "Changes: " + "; ".join(changes)

        return message
