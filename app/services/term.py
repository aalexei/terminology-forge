import re
from db.schema import Term


def linkify(so, links, collection, context):
    '''
    Transform link of form [[key][text]] or [[key]] to actual html links
    '''
    raw = so.group(1)
    pieces = raw.split('][')
    key = pieces[0].strip()
    if len(pieces)>1:
        text = pieces[1].strip()
    else:
        if key in links:
            text = links[key]['n']
        else:
            text = key

    if '/' in key:
        tid = key
    else:
        tid = f'{collection}/{key}'
    if tid in links:
        if context == 'list':
            out = f'<a href="/vocab/{collection}/list#{key}" class="link">{text}</a>'
        else:
            out = f'<a href="/vocab/{collection}/term/{key}" class="link">{text}</a>'

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

    def linkify(self, links, collection, context):
        linkf = lambda x: linkify(x, links, collection, context)
        return re.sub(r'\[\[(.*?)\]\]', linkf, self.text)


def extend_term(term, tags, links, collection, context='list'):
    '''
    Add extra fields for display
    '''

    term._tags = tags
    term._links = { l['_id']:l['term'] for l in links }
    term._collection = collection
    
    term._definition_html = LinkedText(term.definition).linkify(term._links, term._collection,  context)

    notes_html = []
    for n in term.notes:
        notes_html.append(LinkedText(n).linkify(term._links, term._collection, context))
    term._notes_html = notes_html
        
    return term


class TermService:

    collection = None
    
    def __init__(self, db, vocab):
        self.db = db
        self.collection = vocab


    async def get_terms(self, filtr):

        query = """
        FOR t IN @@coll
          LET tags = (
            FOR v IN INBOUND t._id tagged
            RETURN {"_id":v._id, "name":v.name} 
            )
          LET links = (
            FOR v IN ANY t._id link
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
                T = Term(**t["term"])
                extend_term(T, t["tags"], t["links"], self.collection)
                terms.append(T)
                
        return terms
