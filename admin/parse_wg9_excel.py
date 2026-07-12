import openpyxl
import re
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename", type=str, help="Path to excel file")
args = parser.parse_args()


workbook = openpyxl.load_workbook(args.filename)
sheet = workbook['20260705-Defns']

def term2key(term):
    """
    Convert term to canonical key
    valid characters: [a-z0-9_]
    term -> lowercase -> non (letters or numbers) to _
    """
    return re.sub(r"[^a-z0-9]","_",term.lower())


def NN(value, default=""):
    if value is not None:
        return value
    else:
        return default


TAGS = {
    'Q phys.':{
        'name':'cluster.q_physics',
        'description':'General quantum physics cluster.',
        'targets':[],
    },
    'Q dyn.':{
        'name':'cluster.dynamics',
        'description':'Quantum dynamics cluster.',
        'targets':[],
    },
    'Q proc.': {
        'name':'cluster.processes',
        'description':'Quantum processes cluster.',
        'targets':[],
    },
    'Q info.': {
        'name':'cluster.information',
        'description':'Quantum information cluster.',
        'targets':[],
    },
    'Q char.': {
        'name':'cluster.characterisation',
        'description':'Quantum characterisation cluster.',
        'targets':[],
    },
    'Q part.': {
        # TODO What is this?
        'name':'cluster.part',
        'description':'?',
        'targets':[],
    },
    'Q HO': {
        'name':'cluster.ho',
        'description':'Quantum harmonic oscillator cluster.',
        'targets':[],
    },
    'Q ent.': {
        'name':'cluster.entanglement',
        'description':'Quantum entanglement cluster.',
        'targets':[],
    },
    'Q impl.': {
        'name':'cluster.implementation',
        'description':'Quantum computing implementations cluster.',
        'targets':[],
    },
    'Q appl.': {
        'name':'cluster.application',
        'description':'Quantum information applications cluster.',
        'targets':[],
    },
    'misc': {
        'name':'cluster.other',
        'description':'Other categorisation cluster for terms not fitting elsewhere.',
        'targets':[],
    },
    # State
    'Todo': {
        'name':'state.todo',
        'description':'Todo',
        'targets':[],
    },
    'Ext. ref. DO NOT CHANGE': {
        'name':'state.external',
        'description':'External reference, do not change.',
        'targets':[],
    },
    # People
    'Timothy Burt': {
        'name':'responsible.tb',
        'description':'Timothy Burt',
        'targets':[],
    },
    'Alexei Gilchrist': {
        'name':'responsible.ag',
        'description':'Alexei Gilchrist',
        'targets':[],
    },
    'Jacquiline Romero': {
        'name':'responsible.jr',
        'description':'Jacquiline Romero',
        'targets':[],
    },
    'John Devaney': {
        'name':'responsible.jd',
        'description':'John Devaney',
        'targets':[],
    },
}

TASKS = {
    'AG': {
        'name': 'potentially related',
        'description': 'For the cluster terms, consider potentially related terms',
        'works': [],
        'order': 1,
    },
    'AH': {
        'name': 'defining and differentiating',
        'description': 'For the cluster terms, consider key defining and differentiating characteristics ',
        'works': [],
        'order': 2,
    },
    'AI': {
        'name': 'potential links',
        'description': 'From the list of terms, identify which appear to be key for the cluster',
        'works': [],
        'order': 3,
    },
    'AJ': {
        'name': 'free comments',
        'description': '',
        'works': [],
        'order': 4,
    },
}

terms = []
keys_seen = set()

for row in sheet[4:2000]:
    try:
        # Convert to dict based on column letters
        r = {c.column_letter:c.value for c in row}
        if r['T'] is None:
            # Skip lines that do not define a term
            continue

        key = term2key(r['T'])
        if key in keys_seen:
            print (f'==== Key "{key}" multiply defined')
            continue
            #raise Exception()
        keys_seen.add(key)
        
        # Collect base info
        term = {
            'key': key,
            'term': r['T'],
            'definition': NN(r['AD']),
            'source': NN(r['AR']),
            'section':'',
            'context':'',
        }
        if r['V'] is not None:
            term['synonyms'] = [r['V']]
        else:
            term['synonyms'] = []
            
        # TODO 'concept_system': r['AC'],
        # TODO 'priority': r['U']
        # TODO 'reference': r['W'],
        # TODO 'reference_id': r['X'],
       
        # Parse Notes AK..AQ
        notes = []
        for c in ['AK','AI','AJ','AK','AL','AM','AN','AO','AP','AQ']:
            if r[c] is not None:
                notes.append(r[c])
        term['notes'] = notes
        
        # Parse clusters in columns I..S as tags
        # TODO distinguish x and R?
        for c in ['I','J','K','L','M','N','O','P','Q','R','S']:
            # Name of tag in row 3
            TAGS[sheet[c+'3'].value]['targets'].append(key)

        # Parse wg9 state as a tag
        if r['AA'] is not None:
            TAGS[r['AA']]['targets'].append(key)
            
        # Parse responsible person as a tag
        if r['Z'] is not None:
            TAGS[r['Z']]['targets'].append(key)

        # Parse tasks
        for c in ['AG','AH','AI','AJ']:
            if r[c] is not None:
                work = {
                    'content': r[c],
                    'target': key,
                }
                TASKS[c]['works'].append(work)
            
        terms.append(term)
    except AttributeError:
        continue

for t in TAGS.values():
    t['targets'].sort()

for t in TASKS.values():
    t['works'].sort(key=lambda x:x['target'])
    
#print(terms)
#print(TAGS)
#print(TASKS)

tasks = list(TASKS.values())
tasks.sort(key=lambda x:x['name'])

tags = list(TAGS.values())
tags.sort(key=lambda x:x['name'])

vocab = {
    'info': {
        'key': 'vgq',
        'name':'ISO/IEC General Quantum Vocabulary',
        'editable': True,
        'description': "General Quantum vocabulary being developed by WG 9.",
    },
    'tags': tags,
    'tasks': tasks,
    'terms': terms,
    }

#print(vocab)
with open('vgq.json', 'w') as f:
    json.dump(vocab, f, sort_keys=True, indent=2)

    

