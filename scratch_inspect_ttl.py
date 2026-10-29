import sys
sys.stdout.reconfigure(encoding='utf-8')
from rdflib import Graph, RDF, RDFS, OWL, Namespace

g = Graph()
g.parse(r'c:\Users\ounis\Downloads\Web_S-mantique-main\Web_S-mantique-main\ontologie_medicale (1).ttl', format='turtle')
print('Total triplets in ttl:', len(g))

MED = Namespace('http://example.org/ontologie-medicale#')

print('\n=== HIERARCHIE DES CLASSES MALADIE ===')
for s, p, o in g.triples((None, RDFS.subClassOf, None)):
    s_name = str(s).split('#')[-1]
    o_name = str(o).split('#')[-1]
    if 'Maladie' in o_name or 'Maladie' in s_name or o_name in ['Grippe', 'Angine', 'Diabete', 'Hypertension', 'UlcereGastrique']:
        print(f"  {s_name} subClassOf {o_name}")

print('\n=== INDIVIDUS DE MALADIE ACTUELS DANS TTL ===')
maladie_types = set()
for s, p, o in g.triples((None, RDFS.subClassOf, None)):
    if 'Maladie' in str(o) or 'Maladie' in str(s):
        maladie_types.add(s)
        maladie_types.add(o)
maladie_types.add(MED.Maladie)

found_ind = False
for ind, p, t in g.triples((None, RDF.type, None)):
    if t in maladie_types or any(k in str(ind).lower() for k in ['grippe', 'angine', 'diabete', 'hypertension', 'ulcere']):
        if t != OWL.Class:
            print(f"  Individu: {str(ind).split('#')[-1]} | Type: {str(t).split('#')[-1]}")
            # print properties
            for _, p2, o2 in g.triples((ind, None, None)):
                print(f"     -> {str(p2).split('#')[-1]} : {str(o2).split('#')[-1]}")
            found_ind = True

if not found_ind:
    print("  Aucun individu de maladie trouvé !")
