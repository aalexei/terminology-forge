import re
from db.schema import Term


def linkify(so, context='list'):
    '''
    Transform link of form [[key][text]] or [[key]] to actual html links
    '''
    raw = so.group(1)
    pieces = raw.split('][')
    key = pieces[0].strip()
    if len(pieces)>1:
        text = pieces[1].strip()
    else:
        if key in ITEMS:
            text = ITEMS[key]['term']
        else:
            text = key

    if key in ITEMS:
        if context=='list':
            # link to term in terms-list
            out = f'<a href="/#{key}" class="link">{text}</a>'
        else:
            # link to term in term page
            out = f'<a href="/term/{key}" class="link">{text}</a>'
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

    def linkify(self, context='list'):
        linkf = lambda x: linkify(x, context)
        return re.sub(r'\[\[(.*?)\]\]', linkf, self.text)


def extend_item(item, context='list'):
    '''
    Add extra fields for display
    '''
    linkf = lambda x: linkify(x, context)

    item['_definition_html'] = LinkedText(item['definition']).linkify(context)

    notes_html = []
    for n in item['notes']:
        notes_html.append(LinkedText(n).linkify(context))
    item['_notes_html'] = notes_html
        
    return item


class TermService:

    collection = None
    
    def __init__(self, db, vocab):
        self.db = db
        self.collection = vocab

    async def get_terms(self, filtr):
        #terms_col = self.db.collection(self.collection)

        cursor = await self.db.aql.execute(
            "FOR doc IN vqc RETURN doc",
            #bind_vars={"col": self.collection},
        )
        terms = []
        async with cursor as ctx:
            async for t in ctx:
                T = Term(**t)
                T._tags = ''
                terms.append(T)
                
                
        
        return terms
        

