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
    """
    Helper class for text with links
    """
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
    """
    Convert term to canonical key
    valid characters: [a-z0-9_]
    term -> lowercase -> non (letters or numbers) to _
    """
    return re.sub(r"[^a-z0-9]","_",term.lower())


def ensure_vertex_collection(G, name, reset=False):
    """
    Ensure graph "G" has vertex collection "name". Reset if requested.
    """
    if G.has_vertex_collection(name):
        collection = G.vertex_collection(name)
        if reset:
            collection.truncate()
    else:
        collection = G.create_vertex_collection(name)

def ensure_edge_collection(G, name, fromlist, tolist, reset=False):
    """
    Ensure graph "G" has edge collection "name". Reset if requested.
    """
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
    """
    Convenience method to get database
    """
    client = ArangoClient(hosts=DB_URL)
    db = client.db(dbname, username=dbuser, password=dbpass)
    return db

def delete_database(sysdb):
    """
    Delete the database DB_NAME if it exists
    """
    if sysdb.has_database(DB_NAME):
        sysdb.delete_database(DB_NAME)
    
def create_database(sysdb, dbpass):
    """
    Create a database
    """
    if sysdb.has_database(DB_NAME):
        raise Exception("Database already exists, delete first.")
    
    # Create the database
    users = [{'username': DB_USER, 'password': dbpass, 'active': True}]
    sysdb.create_database(DB_NAME, users=users)

    # If user existed previously the password is not reset by the above
    # Explicitly reset password here
    sysdb.update_user(username=DB_USER, password=dbpass)
    
def add_user_collection(userjsonpath, db):
    """
    Add the collection of users
    """

    with open(userjsonpath) as fp:
        userlist = json.load(fp)
            
    # Create users collection and add users
    users = db.create_collection('users')
    # TODO Validate the user info with schema.User
    users.import_bulk(userlist)


def vocab_get_info(vocab_file):
    """
    Get the info structure from a json file
    """

    with open(vocab_file) as fp:
        data = json.load(fp)

    # Validate the info structure
    info = schema.Vocabulary(**data['info'])
    return info


def reset_database():
    """
    Reset the database and reload all data
    """

    # Get credentials
    rootpass = getpass('Arango root password:')
    dbpass = getpass('Set DB password:')
    sysdb = get_db('_system', 'root', rootpass)

    # Delete and recreate the database
    delete_database(sysdb)
    create_database(sysdb, dbpass)

    # Fetch the newly created DB
    db = get_db(DB_NAME, DB_USER, dbpass)

    # Add users collection
    add_user_collection("users.json", db)

    # Create a graph
    graph = db.create_graph(GRAPH_NAME)
    
    # Create a collection for vocabulary metadata
    vocabularies = db.create_collection('vocabularies')
    
    # Create a log collection
    db.create_collection('log')
    
    # Get list of vocabulary json files
    vocab_files = glob.glob('vocabs/*.json')

    # For the graph we will need the names of all the vocabularies
    # it is easier to traverse the files twice
    editable_vocabulary_names = []
    all_vocabulary_names = []
    for vocab_file in vocab_files:
        with open(vocab_file) as fp:
            data = json.load(fp)

        # Validate the vocab info
        vocab_info = schema.Vocabulary(**data['info'])
        all_vocabulary_names.append(vocab_info.key)
        if vocab_info.editable:
             editable_vocabulary_names.append(vocab_info.key)

    # A single 'tagged' link type for simplicity: tag --(tagged)-> term
    tagged = graph.create_edge_definition(
        edge_collection='tagged',
        from_vertex_collections=[n+'_tag' for n in editable_vocabulary_names],
        to_vertex_collections=editable_vocabulary_names
    )
    
    # A single 'work' link type for simplicity: task --(work)-> term
    work = graph.create_edge_definition(
        edge_collection='work',
        from_vertex_collections=[n+'_task' for n in editable_vocabulary_names],
        to_vertex_collections=editable_vocabulary_names
    )

    # A 'comment' link type: user --(comment)-> term
    comment = graph.create_edge_definition(
        edge_collection='comment',
        from_vertex_collections=['users'],
        to_vertex_collections=editable_vocabulary_names
    )
    
    # A single 'link' link type to connect terms: term --(link)-> term
    link = graph.create_edge_definition(
        edge_collection='link',
        from_vertex_collections=editable_vocabulary_names,
        to_vertex_collections=all_vocabulary_names
    )

    # Now traverse files again building up the database
    for vocab_file in vocab_files:
        with open(vocab_file) as fp:
            data = json.load(fp)

        # Validate the vocab info
        vocab_info = schema.Vocabulary(**data['info'])
        vocab_name = vocab_info.key

        # Add the info to vocabularies collection
        vocabularies.insert(vocab_info.model_dump())
        
        # Get terms collection for vocab
        terms = graph.vertex_collection(vocab_name)

        for t in data['terms']:
            # Validate term
            T = schema.Term(**t)
            # Add the term to the db
            terms.insert(T.model_dump())

        for t in terms.all():
            relink(graph,t)
        
        if vocab_info.editable:
            tags_name = vocab_name+'_tag'
            tags = graph.vertex_collection(tags_name)
            for t in data['tags']:
                # Validate tag
                T = schema.Tag(**t)
                tag = tags.insert(T.model_dump(exclude_unset=True))
                for key in t['targets']:
                    target = terms.get(key)
                    tagged.insert({'_from':tag['_id'], '_to':target['_id']})
                    
            tasks = graph.vertex_collection(vocab_info.key+'_task')
            # TODO load and link tasks

            # TODO load and link comments
            # TODO load log

def relink(G, t1):
    """
    Recreate the links from this item's definition and notes out.
    """
    vcol = t1['_id'].split('/')[0]
    TERM = G.vertex_collection(vcol)
    LINK = G.edge_collection('link')
    
    # Delete existing links
    existing_links = LINK.edges(t1['_id'], direction='out')['edges']
    for link in existing_links:
        LINK.delete(link['_id'])

    # Reform links from definition and notes
    def add_link(t1, target, context):
        t2 = TERM.get(target)
        if t2 is not None:
            LINK.insert({'_from':t1['_id'], '_to':t2['_id'], 'context': context})
    for target in LinkedText(t1['definition']).links():
        add_link(t1,target,'def')
    for n in t1['notes']:
        for target in LinkedText(n).links():
            add_link(t1,target,'note')
    
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action="store_true", help="Reset database removing previous items")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    
    else:
         pass   
