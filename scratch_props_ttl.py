import sys
sys.stdout.reconfigure(encoding='utf-8')
from rdflib import Graph, RDF, RDFS, OWL

g = Graph()
g.parse(r'c:\Users\ounis\Downloads\Web_S-mantique-main\Web_S-mantique-main\ontologie_medicale (1).ttl', format='turtle')

print('=== OBJECT PROPERTIES DANS TTL ===')
for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
    domain = [str(d).split('#')[-1] for _, _, d in g.triples((s, RDFS.domain, None))]
    rng = [str(r).split('#')[-1] for _, _, r in g.triples((s, RDFS.range, None))]
    print(f"  {str(s).split('#')[-1]} (domain: {domain}, range: {rng})")

print('\n=== DATATYPE PROPERTIES DANS TTL ===')
for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
    domain = [str(d).split('#')[-1] for _, _, d in g.triples((s, RDFS.domain, None))]
    rng = [str(r).split('#')[-1] for _, _, r in g.triples((s, RDFS.range, None))]
    print(f"  {str(s).split('#')[-1]} (domain: {domain}, range: {rng})")
