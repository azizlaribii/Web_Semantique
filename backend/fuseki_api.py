# -*- coding: utf-8 -*-
"""
Couche API Fuseki (SPARQL Endpoint)
Compatible avec le standard Apache Jena Fuseki.
Permet d'exécuter des requêtes SPARQL directement via HTTP GET/POST,
avec redirection vers un serveur Fuseki externe si présent ou exécution locale via RDFLib.
"""

from typing import Dict, Any
import requests

class FusekiAPIService:
    def __init__(self, rdflib_service, fuseki_url: str = "http://localhost:3030/personne/sparql"):
        self.rdflib_service = rdflib_service
        self.fuseki_url = fuseki_url

    def is_fuseki_alive(self) -> bool:
        """Vérifie si un serveur Apache Jena Fuseki distant est joignable."""
        try:
            r = requests.get(self.fuseki_url.replace("/sparql", "/ping"), timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def query(self, sparql_query: str) -> Dict[str, Any]:
        """
        Exécute la requête SPARQL soit via Apache Jena Fuseki s'il est lancé,
        soit via le moteur RDFLib local.
        """
        # Tentative Fuseki externe si actif
        if self.is_fuseki_alive():
            try:
                headers = {"Accept": "application/sparql-results+json"}
                r = requests.post(self.fuseki_url, data={"query": sparql_query}, headers=headers, timeout=5.0)
                if r.status_code == 200:
                    res = r.json()
                    res["source"] = "Apache Jena Fuseki (Distant)"
                    return res
            except Exception as e:
                print(f"[Fuseki API] Fallback sur RDFLib : {e}")

        # Exécution locale via RDFLib
        res = self.rdflib_service.execute_sparql(sparql_query)
        res["source"] = "Moteur RDFLib (Local - Emulation Fuseki)"
        return res
