'''
Load data into an Arango DB
'''
import re, json, sys, io, csv, time, glob
from pathlib import Path
import argparse
from getpass import getpass

from arango import ArangoClient

sys.path.append("..")
from app.db import schema

DB_NAME = 'TFDB'
DB_USER = 'tfuser'
GRAPH_NAME = 'TFG'
DB_URL = "http://127.0.0.1:8529"

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

def term2key(term):
    '''
    Convert term to canonical key
    valid characters: [a-z0-9_]
    term -> lowercase -> non (letters or numbers) to _
    '''
    return re.sub(r"[^a-z0-9]","_",term.lower())


def ensure_vertex_collection(G, name, reset=False):
    '''
    Ensure graph "G" has vertex collection "name". Reset if requested.
    '''
    if G.has_vertex_collection(name):
        collection = G.vertex_collection(name)
        if reset:
            collection.truncate()
    else:
        collection = G.create_vertex_collection(name)

def ensure_edge_collection(G, name, fromlist, tolist, reset=False):
    '''
    Ensure graph "G" has edge collection "name". Reset if requested.
    '''
    if not G.has_edge_definition(name):
        G.create_edge_definition(
            edge_collection=name,
            from_vertex_collections=fromlist,
            to_vertex_collections=tolist
        )
    edge = G.edge_collection(name)
    if reset:
        edge.truncate()


def get_db(dbname, dbuser, dbpass):
    client = ArangoClient(hosts=DB_URL)
    db = client.db(dbname, username=dbuser, password=dbpass)
    return db

def delete_database(sysdb):
    # Delete the database if it exists
    if sysdb.has_database(DB_NAME):
        sysdb.delete_database(DB_NAME)
    
def create_database(sysdb, dbpass):
    if sysdb.has_database(DB_NAME):
        raise Exception("Database already exists, delete first.")
    
    # Create the database
    users = [{'username': DB_USER, 'password': dbpass, 'active': True}]
    sysdb.create_database(DB_NAME, users=users)

    # If user existed previously the password is not reset by the above
    # Explicitly reset password here
    sysdb.update_user(username=DB_USER, password=dbpass)
    
def add_user_collection(userjsonpath, db):

    with open(userjsonpath) as fp:
        userlist = json.load(fp)
            
    # Create users collection and add users
    users = db.create_collection('users')
    users.import_bulk(userlist)


def vocab_get_info(vocab_file):

    with open(vocab_file) as fp:
        data = json.load(fp)

    info = schema.Vocabulary(**data['info'])
    return info
    
def reset_database():

    # Get list of vocabulary json files
    vocab_files = glob.glob('vocabs/*.json')

    # Delete and recreate the database
    rootpass = getpass('Arango root password:')
    dbpass = getpass('Set DB password:')

    sysdb = get_db('_system', 'root', rootpass)
    delete_database(sysdb)
    create_database(sysdb, dbpass)

    # Fetch the new DB
    db = get_db(DB_NAME, DB_USER, dbpass)

    # Add users collection
    add_user_collection("users.json", db)

    # Get summary info from vocabulary json files
    vertex_collections = []
    vocabularies = []
    for vocab_file in vocab_files:
        info = vocab_get_info(vocab_file)
        vocabularies.append(info.model_dump())
        vertex_collections.append(info.key)

    # Create a collection with vocabulary metadata
    vs = db.create_collection('vocabularies')
    vs.import_bulk(vocabularies)

    # Create graph DB
    edge_definitions = [
        {# term -> term links 
            'edge_collection': 'link',
            'from_vertex_collections':  vertex_collections,
            'to_vertex_collections':  vertex_collections,
        },
        {# vocab1/term -> vocab2/term
            'edge_collection': 'related',
            'from_vertex_collections':  vertex_collections,
            'to_vertex_collections':  vertex_collections,
        },
        {# tag -> term
            'edge_collection': 'tagged',
            'from_vertex_collections': ['tag'],
            'to_vertex_collections':  vertex_collections,
        }
    ]

    G = db.create_graph(GRAPH_NAME, edge_definitions=edge_definitions)

    # Load and link the vocabularies
    for vocab_file in vocab_files:
        load_data(G, vocab_file)

        
def relink(G, t1):
    '''
    Recreate the links from this item's definition and notes out.
    '''
    vcol = t1['_id'].split('/')[0]
    TERM = G.vertex_collection(vcol)
    LINK = G.edge_collection('link')
    
    # Delete existing links
    existing_links = LINK.edges(t1['_id'], direction='out')['edges']
    for link in existing_links:
        LINK.delete(link['_id'])

    # Reform links from definition and notes
    targets = set()
    targets.update(LinkedText(t1['definition']).links())
    for n in t1['notes']:
        targets.update(LinkedText(n).links())
    for target in targets:
        t2 = TERM.get(target)
        if t2 is not None:
            LINK.insert({'_from':t1['_id'], '_to':t2['_id']})

class Tag:
    def __init__(self, **data):
        self.targets = set()
        self.data = schema.Tag(**data)
    def add_target(self, t):
        self.targets.add(t)
    def model_dump(self):
        return self.data.model_dump(exclude_unset=True)
    
            
def load_data(G, vocab_file):

    with open(vocab_file) as fp:
        data = json.load(fp)

    vocab = schema.Vocabulary(**data['info'])
    terms = data['terms']
    name = vocab.key
    
    TERM = G.vertex_collection(name)
    TAG = G.vertex_collection('tag')
    LINK = G.edge_collection('link')
    TAGGED = G.edge_collection('tagged')

    if vocab.editable:
        tags = {}
        for t in data.get('tags',[]):
            tags[t['name']] = Tag(**t)

    dbterms = []
    for term in terms:
        dbterm = schema.Term(**term)
        
        if vocab.editable:
            dbterm.log = term.get('log', [])
            dbterm.rev = term.get('rev', 1)

            # TODO temporary renaming may remove cluster and status in future
            for cat in ['cluster', 'status']:
                if len(term.get(cat,''))>0:
                    name = cat+'.'+term[cat]
                    if name not in tags:
                        tags[name] = Tag(name=name)
                    tags[name].add_target(dbterm.key)
                
        dbterms.append(dbterm.model_dump())

    TERM.insert_many(dbterms)

    if vocab.editable:
        # Attach tags 
        for t in tags.values():
            c = TAG.insert(t.model_dump())
            for target in t.targets:
                t2 = TERM.get(target)
                TAGGED.insert({'_from':c['_id'], '_to':t2['_id']})

    # Link terms
    for t1 in TERM.all():
        relink(G, t1)

            
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action="store_true", help="Reset database removing previous items")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    
    else:
         pass   
