import re
import json
from db import schema



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
        RETURN { "term":t, "tags":tags, "links":links }
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
        RETURN {"term":DOCUMENT(@tid), "tags":tags, "links":links}
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"tid": f"{self.collection}/{tid}"},
        )
        async with cursor as ctx:
            async for t in ctx:
                T = schema.Term(**t["term"])
                extend_term(T, t["tags"], t["links"], self.collection, context="term")
                
        return T

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
        RETURN { "term":t, "tags":tags, "links":links }
        """
        cursor = await self.db.aql.execute(
            query,
            bind_vars={"@coll": self.collection},
        )
        
        elements = { 'nodes':[], 'edges':[] }
        async with cursor as ctx:
            async for t in ctx:
                elements['nodes'].append({
                    'data': {'id': t['term']['_id'], 'n':t['term']['term']}
                    })
                for lnk in t['links']:
                    if lnk['context'] == 'def':
                        elements['edges'].append({
                            'data': {'source': t['term']['_id'], 'target':lnk['_id'], 'n':'link'}
                        })

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
            
        else:
            raise Exception()
    
