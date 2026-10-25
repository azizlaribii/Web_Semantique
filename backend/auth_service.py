# -*- coding: utf-8 -*-
"""
Service d'authentification — Système de Connexion / Inscription
Gère les mots de passe hashés et les sessions via JWT simple (token en base64).
Stocke les credentials dans l'ontologie OWL (propriété :motDePasse et :email).
"""

import os
import re
import json
import base64
import hashlib
import secrets
import datetime

import bcrypt
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWL_PATH = os.path.join(BASE_DIR, "ontologie_personne.owl")
TTL_PATH = os.path.join(BASE_DIR, "ontologie_medicale (1).ttl")

ONTO_NS = Namespace("http://example.org/ontologie-medicale#")

# Fichier JSON léger pour stocker les sessions actives (tokens)
SESSIONS_PATH = os.path.join(BASE_DIR, "backend", "sessions.json")


def _load_sessions():
    if os.path.exists(SESSIONS_PATH):
        try:
            with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_sessions(sessions: dict):
    with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


class AuthService:
    """
    Service d'authentification intégré à l'ontologie OWL.
    - register : crée un individu + stocke email/password hashé dans l'OWL
    - login    : vérifie email + password hashé, retourne un token de session
    - verify   : valide un token de session
    """

    def __init__(self, rdflib_service=None):
        self.rdflib_service = rdflib_service
        # Charge le graphe local pour la lecture des credentials
        self._graph = Graph()
        self._load_graph()

    def _load_graph(self):
        """Charge l'ontologie OWL locale pour lire les données d'authentification."""
        self._graph = Graph()
        sources = [
            (OWL_PATH, "xml"),
            (TTL_PATH, "turtle"),
        ]
        for path, fmt in sources:
            if os.path.exists(path):
                try:
                    self._graph.parse(path, format=fmt)
                except Exception as e:
                    print(f"[AuthService] Avertissement chargement {path}: {e}")
        self._graph.bind("med", ONTO_NS)

    def reload(self):
        """Recharge le graphe après modifications."""
        self._load_graph()

    # ------------------------------------------------------------------
    # Inscription
    # ------------------------------------------------------------------
    def register(self, data: dict) -> dict:
        """
        Inscrit un nouvel utilisateur dans l'ontologie.
        Champs attendus : nom, prenom, email, motDePasse, role (type OWL),
                          + optionnel : age, cin, telephone, adresse, groupeSanguin, specialite
        """
        nom = data.get("nom", "").strip()
        prenom = data.get("prenom", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("motDePasse", "").strip()
        role = data.get("role", "Patient").strip()

        # Validations
        if not nom:
            raise ValueError("Le nom est obligatoire.")
        if not email or "@" not in email:
            raise ValueError("L'adresse email est invalide.")
        if len(password) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")

        # Vérifier si l'email existe déjà
        if self._email_exists(email):
            raise ValueError(f"L'email '{email}' est déjà utilisé.")

        # Hashage du mot de passe avec bcrypt
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Construire l'URI de l'individu
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', f"{prenom}_{nom}".strip("_"))
        prefix_map = {
            "Medecin": "Dr_", "MedecinGeneraliste": "Dr_", "MedecinSpecialiste": "Dr_",
            "Cardiologue": "Dr_", "Radiologue": "Dr_",
            "Patient": "Pat_", "Stagiaire": "Stag_",
        }
        prefix = next((v for k, v in prefix_map.items() if k.lower() in role.lower()), "Ind_")
        id_suffix = f"{prefix}{clean_name}"

        ind_uri = ONTO_NS[id_suffix]
        cls_uri = ONTO_NS[role]

        # Ajouter au graphe RDFLib local
        self._graph.add((ind_uri, RDF.type, OWL.NamedIndividual))
        self._graph.add((ind_uri, RDF.type, cls_uri))
        full_name = f"{prenom} {nom}".strip()
        self._graph.add((ind_uri, RDFS.label, Literal(full_name, datatype=rdflib.XSD.string)))
        self._graph.add((ind_uri, ONTO_NS.nom, Literal(nom, datatype=rdflib.XSD.string)))
        self._graph.add((ind_uri, ONTO_NS.prenom, Literal(prenom, datatype=rdflib.XSD.string)))
        self._graph.add((ind_uri, ONTO_NS.email, Literal(email, datatype=rdflib.XSD.string)))
        self._graph.add((ind_uri, ONTO_NS.motDePasse, Literal(hashed, datatype=rdflib.XSD.string)))

        # Champs optionnels
        if data.get("age"):
            try:
                self._graph.add((ind_uri, ONTO_NS.age, Literal(int(data["age"]), datatype=rdflib.XSD.integer)))
            except (ValueError, TypeError):
                pass
        if data.get("telephone"):
            self._graph.add((ind_uri, ONTO_NS.telephone, Literal(str(data["telephone"]), datatype=rdflib.XSD.string)))
        if data.get("cin"):
            self._graph.add((ind_uri, ONTO_NS.numeroCIN, Literal(str(data["cin"]), datatype=rdflib.XSD.string)))
        if data.get("adresse"):
            self._graph.add((ind_uri, ONTO_NS.adresse, Literal(str(data["adresse"]), datatype=rdflib.XSD.string)))
        if data.get("groupeSanguin"):
            self._graph.add((ind_uri, ONTO_NS.groupeSanguin, Literal(str(data["groupeSanguin"]), datatype=rdflib.XSD.string)))
        if data.get("specialite"):
            self._graph.add((ind_uri, ONTO_NS.specialite, Literal(str(data["specialite"]), datatype=rdflib.XSD.string)))

        # Persister dans ontologie_personne.owl
        self._save_owl()

        # Persister dans le TTL (pour Protégé)
        self._append_to_ttl(id_suffix, role, full_name, nom, prenom, email, hashed, data)

        # Recharger le service principal si disponible
        if self.rdflib_service:
            try:
                self.rdflib_service.load_ontology()
            except Exception as e:
                print(f"[AuthService] Avertissement reload service: {e}")

        return {
            "success": True,
            "id": id_suffix,
            "uri": str(ind_uri),
            "nom": full_name,
            "email": email,
            "role": role,
        }

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    def login(self, identifier: str, password: str) -> dict:
        """
        Authentifie l'utilisateur par email, nom ou ID + mot de passe.
        Supporte les mots de passe hashés (bcrypt) ET les mots de passe en clair saisis dans Protégé.
        Si un mot de passe en clair est détecté et valide, il est automatiquement converti en hash bcrypt.
        """
        identifier = identifier.strip()
        if not identifier or not password:
            raise ValueError("Identifiant (ou Email) et mot de passe sont obligatoires.")

        # Recharger le graphe pour avoir les données fraîches depuis les fichiers OWL
        self._load_graph()

        # Chercher l'utilisateur par email, nom ou ID dans l'ontologie
        user_data = self._find_user(identifier)
        if not user_data:
            raise ValueError("Identifiant ou mot de passe incorrect.")

        stored_pass = user_data.get("motDePasse", "").strip()
        if not stored_pass:
            raise ValueError(f"Le compte '{user_data['nom']}' n'a pas de mot de passe configuré dans l'ontologie. Ajoutez la propriété :motDePasse dans Protégé.")

        # Vérifier si c'est un hash bcrypt ($2b$, $2a$, $2y$) ou un mot de passe en clair
        is_bcrypt = stored_pass.startswith("$2b$") or stored_pass.startswith("$2a$") or stored_pass.startswith("$2y$")
        match = False

        if is_bcrypt:
            try:
                match = bcrypt.checkpw(password.encode("utf-8"), stored_pass.encode("utf-8"))
            except Exception:
                match = False
        else:
            # Mot de passe en clair directement saisi dans Protégé !
            match = (password == stored_pass)
            if match:
                # Mise à niveau automatique vers bcrypt pour la sécurité
                try:
                    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    user_uri = URIRef(user_data["uri"])
                    self._graph.set((user_uri, ONTO_NS.motDePasse, Literal(hashed, datatype=rdflib.XSD.string)))
                    self._save_owl()
                    print(f"[AuthService] Mot de passe en clair de {user_data['nom']} automatiquement hashé avec bcrypt dans l'OWL.")
                except Exception as e:
                    print(f"[AuthService] Avertissement auto-hash : {e}")

        if not match:
            raise ValueError("Identifiant ou mot de passe incorrect.")

        # Générer un token de session
        token = secrets.token_urlsafe(48)
        sessions = _load_sessions()
        email = user_data.get("email") or f"{user_data['id'].lower()}@hopital.local"
        sessions[token] = {
            "email": email,
            "id": user_data["id"],
            "nom": user_data["nom"],
            "prenom": user_data.get("prenom", ""),
            "role": user_data.get("role", "Personne"),
            "uri": user_data["uri"],
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        _save_sessions(sessions)

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user_data["id"],
                "nom": user_data["nom"],
                "prenom": user_data.get("prenom", ""),
                "email": email,
                "role": user_data.get("role", "Personne"),
            }
        }

    # ------------------------------------------------------------------
    # Vérification de session
    # ------------------------------------------------------------------
    def verify_token(self, token: str) -> dict | None:
        """Retourne les données utilisateur si le token est valide, None sinon."""
        if not token:
            return None
        sessions = _load_sessions()
        return sessions.get(token)

    def logout(self, token: str) -> bool:
        """Invalide un token de session."""
        sessions = _load_sessions()
        if token in sessions:
            del sessions[token]
            _save_sessions(sessions)
            return True
        return False

    # ------------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------------
    def _email_exists(self, email: str) -> bool:
        """Vérifie si un email est déjà présent dans le graphe."""
        for _, _, obj in self._graph.triples((None, ONTO_NS.email, None)):
            if str(obj).lower() == email.lower():
                return True
        return False

    def _find_user(self, identifier: str) -> dict | None:
        """
        Cherche un individu dans le graphe par:
        1. Son email (:email)
        2. Son ID suffixe (ex: Ind_Jihene_Ounis ou Jihene_Ounis)
        3. Son nom (:nom ou rdfs:label, ex: 'Jihene Ounis')
        """
        ident_lower = identifier.lower().strip()

        # Parcourir tous les individus du graphe
        for subj, _, _ in self._graph.triples((None, RDF.type, OWL.NamedIndividual)):
            uri = str(subj)
            id_suffix = uri.split("#")[-1]

            # Récupérer les propriétés
            nom = str(next(self._graph.objects(subj, ONTO_NS.nom), Literal(""))).strip()
            prenom = str(next(self._graph.objects(subj, ONTO_NS.prenom), Literal(""))).strip()
            label = str(next(self._graph.objects(subj, RDFS.label), Literal(""))).strip()
            email = str(next(self._graph.objects(subj, ONTO_NS.email), Literal(""))).strip()
            motDePasse = str(next(self._graph.objects(subj, ONTO_NS.motDePasse), Literal(""))).strip()

            # Rôle / types
            types = [str(o).split("#")[-1] for _, _, o in self._graph.triples((subj, RDF.type, None))]
            role = next((t for t in types if t not in ["NamedIndividual", "Thing"]), "Personne")

            # Conditions de correspondance
            matches_email = email and email.lower() == ident_lower
            clean_id = id_suffix.lower().replace("ind_", "").replace("dr_", "").replace("pat_", "").replace("stag_", "")
            clean_ident = ident_lower.replace(" ", "_").replace("ind_", "").replace("dr_", "").replace("pat_", "").replace("stag_", "")
            matches_id = (id_suffix.lower() == ident_lower) or (clean_id == clean_ident)
            matches_nom = nom and (nom.lower() == ident_lower or f"{prenom} {nom}".strip().lower() == ident_lower)
            matches_label = label and label.lower() == ident_lower

            if matches_email or matches_id or matches_nom or matches_label:
                return {
                    "uri": uri,
                    "id": id_suffix,
                    "nom": nom or label or id_suffix,
                    "prenom": prenom,
                    "email": email or f"{id_suffix.lower()}@hopital.local",
                    "motDePasse": motDePasse,
                    "role": role,
                }
        return None

    def _find_user_by_email(self, email: str) -> dict | None:
        """Alias pour compatibilité descendante."""
        return self._find_user(email)

    def _save_owl(self):
        """Sérialise le graphe courant dans ontologie_personne.owl."""
        if os.path.exists(OWL_PATH):
            try:
                self._graph.serialize(destination=OWL_PATH, format="xml")
                print("[AuthService] ontologie_personne.owl mis à jour.")
            except Exception as e:
                print(f"[AuthService] Erreur save OWL : {e}")

    def _append_to_ttl(self, id_suffix, role, full_name, nom, prenom, email, hashed, data):
        """Ajoute l'individu au fichier TTL pour Protégé."""
        if not os.path.exists(TTL_PATH):
            return
        try:
            with open(TTL_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n\n###  http://example.org/ontologie-medicale#{id_suffix}\n")
                f.write(f":{id_suffix} rdf:type owl:NamedIndividual ,\n")
                f.write(f"                     :{role} ;\n")
                f.write(f'            rdfs:label "{full_name}" ;\n')
                f.write(f'            :nom "{nom}" ;\n')
                f.write(f'            :prenom "{prenom}" ;\n')
                f.write(f'            :email "{email}" ;\n')
                f.write(f'            :motDePasse "{hashed}"')
                if data.get("age"):
                    f.write(f" ;\n            :age {data['age']}")
                if data.get("telephone"):
                    f.write(f' ;\n            :telephone "{data["telephone"]}"')
                if data.get("cin"):
                    f.write(f' ;\n            :numeroCIN "{data["cin"]}"')
                if data.get("adresse"):
                    f.write(f' ;\n            :adresse "{data["adresse"]}"')
                if data.get("groupeSanguin"):
                    f.write(f' ;\n            :groupeSanguin "{data["groupeSanguin"]}"')
                if data.get("specialite"):
                    f.write(f' ;\n            :specialite "{data["specialite"]}"')
                f.write(" .\n")
        except Exception as e:
            print(f"[AuthService] Erreur append TTL : {e}")
