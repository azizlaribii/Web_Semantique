import sys
sys.stdout.reconfigure(encoding='utf-8')
from rdflib import Graph, RDF, RDFS, OWL

g = Graph()
g.parse(r'c:\Users\ounis\Downloads\Web_S-mantique-main\Web_S-mantique-main\ontologie_medicale (1).ttl', format='turtle')

print('=== INDIVIDUS DANS TTL (par type) ===')
types_dict = {}
for s, p, o in g.triples((None, RDF.type, None)):
    if o not in [OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology, RDFS.Datatype]:
        t_name = str(o).split('#')[-1]
        s_name = str(s).split('#')[-1]
        if t_name not in types_dict: types_dict[t_name] = []
        if s_name not in types_dict[t_name]: types_dict[t_name].append(s_name)

for t, inds in sorted(types_dict.items()):
    print(f"  [{t}]: {', '.join(inds[:10])}")
