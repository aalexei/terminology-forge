import re
import json
import time
from db import schema

def term2key(term):
    """
    Convert term to canonical key
    valid characters: [a-z0-9_]
    term -> lowercase -> non (letters or numbers) to _
    """
    return re.sub(r"[^a-z0-9]","_",term.lower())


def linkify(so, links, vocab, context):
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
        if context == 'list':
            out = f'<a href="/vocab/{target_vocab}/list#{target_key}" class="link">{text}</a>'
        else:
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

    def linkify(self, links, vocab, context):
        linkf = lambda x: linkify(x, links, vocab, context)
        return re.sub(r'\[\[(.*?)\]\]', linkf, self.text)


def extend_term(term, tags, links, vocab, context='list'):
    '''
    Add extra fields for display
    '''

    term._tags = tags
    term._links = { l['_id']:l['term'] for l in links }
    term._vocab = vocab
    
    term._definition_html = LinkedText(term.definition).linkify(term._links, term._vocab,  context)

    notes_html = []
    for n in term.notes:
        notes_html.append(LinkedText(n).linkify(term._links, term._vocab, context))
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


class TermService:

    collection = None
    
    def __init__(self, db, vocab=''):
        self.db = db
        self.collection = vocab


    async def get_terms(self, filtr=''):

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

        cursor = await self.db.aql.execute(
            query,
            bind_vars={"@coll": self.collection},
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
                extend_term(T, t["tags"], t["links"], self.collection, context="term")
                T._indegree = t["indegree"]
                T._outdegree = t["outdegree"]
                
        return T

    
    async def has_term(self, tid):
        terms = self.db.collection(self.collection)
        return await terms.has(tid) 

    
    async def add_term(self, term):
        terms = self.db.collection(self.collection)
        await terms.insert(term.model_dump(by_alias=True))
        
        # Relink
        TERM = await terms.get(term.key)
        # TODO go off preferences instead of hard-coded TFG
        graph = self.db.graph('TFG')
        await relink(graph, TERM)

        
    async def update_term(self, term):
        terms = self.db.collection(self.collection)

        # Adjust the data removing what we don't want to update
        term_data = term.model_dump(by_alias=True)
        del term_data['term']
        
        await terms.update(term_data)

        # Relink
        TERM = await terms.get(term.key)
        # TODO go off preferences instead of hard-coded TFG
        graph = self.db.graph('TFG')
        await relink(graph, TERM)
        
    async def add_log(self, user, target, summary):
        log = self.db.collection("log")

        entry = schema.Log(
                timestamp = time.time(),
                user = user.github,
                target = target,
                summary = summary,
                )

        await log.insert(entry.model_dump(exclude_unset=True))


    async def get_log(self, target):
        #log = self.db.collection("log")

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
            
        # async for entry in await log.find({"target": target}):
        #     entries.append(schema.Log(**entry))
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
        
        elements = { 'nodes':[], 'edges':[] }
        async with cursor as ctx:
            async for t in ctx:
                elements['nodes'].append({
                    'data': {
                        'id': t['term']['_id'],
                        'key': t['term']['_key'],
                        'term':t['term']['term'],
                        'definition':t['term']['definition'],
                        'definition_html':LinkedText(t['term']['definition']).linkify(t['links'], self.collection, "term"),
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
            async with cursor as ctx:
                async for t in ctx:
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

                # Get all tags and their targets
                tags = []
                query = """
                FOR tag IN @@coll
                  LET targets = (
                    FOR v IN OUTBOUND tag._id tagged
                    RETURN v._key
                  )
                RETURN { "tag":tag, "targets":targets }
                """
                cursor = await self.db.aql.execute(
                    query,
                    bind_vars={"@coll": self.collection+'_tag'},
                )
                async with cursor as ctx:
                    async for t in ctx:
                        T = schema.Tag(**t['tag'])
                        T2 = T.model_dump(by_alias=False)
                        T2['targets'] = t['targets']
                        del T2['key']
                        tags.append(T2)
                tags.sort(key=lambda x:x['name'].lower())

                # TODO tasks
                # TODO logs
                # TODO comments

                # Bundle everything together
                export_data={
                    'info': info,
                    'tags': tags,
                    'terms': terms,
                }
    
            return export_data

        # TODO implement CSV export
    
        
        else:
            raise Exception()

        
    async def get_tasks(self):
        
        tasks = []
        cursor = await self.db.aql.execute(
            "FOR t IN @@coll RETURN t",
            bind_vars={"@coll": f"{self.collection}_task"})
        async for task in cursor:
            tasks.append(schema.Task(**task))
        return tasks 
