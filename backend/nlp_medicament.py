# -*- coding: utf-8 -*-
"""
Pipeline NLP / TALN du module Médicament (sans LLM).

Outils utilisés :
  - spaCy (modèle français fr_core_news_sm) : tokenisation, étiquetage morpho-syntaxique (POS),
    lemmatisation, et reconnaissance d'entités métier par PhraseMatcher.
  - scikit-learn : classification de l'intention (TF-IDF mots + caractères, régression logistique).
  - difflib (bibliothèque standard Python) : tolérance aux fautes de frappe sur les noms d'entités.

Étapes pour une question :
  1. Analyse spaCy : tokens, lemmes, POS. Chaque token reçoit une forme normalisée
     (lemme en minuscules, sans accents) stockée dans token.norm_.
  2. Reconnaissance d'entités (NER métier) : un PhraseMatcher construit à partir des individus
     de l'ontologie (médicaments, molécules, maladies, effets, conditions, classes) repère les entités.
     Les mots non reconnus mais proches d'une entité (ex. « brufin ») sont corrigés par difflib.
  3. Délexicalisation : chaque entité est remplacée par son type (ent_med, ent_mal...),
     pour que le classifieur apprenne la structure de la question et non les noms propres.
  4. Classification d'intention : TF-IDF + régression logistique, entraînée au démarrage sur
     nlp_data/intents_medicament.json (le corpus est enrichi avec les vraies entités de l'ontologie).
  5. Extraction de paramètres (slots) : négation, gravité, ordre de tri, superlatif.
"""

import json
import os
import random
import unicodedata
from difflib import get_close_matches
from typing import Dict, Any, List, Tuple

try:
    import spacy
    from spacy.matcher import PhraseMatcher
    from spacy.util import filter_spans
    HAVE_SPACY = True
except ImportError:
    HAVE_SPACY = False
    spacy = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

class SimpleToken:
    def __init__(self, text, i=0):
        self.text = text
        self.lemma_ = text
        self.norm_ = "".join(c for c in unicodedata.normalize("NFD", text.replace("œ", "oe").replace("Œ", "OE")) if unicodedata.category(c) != "Mn").lower()
        self.pos_ = "NOUN"
        self.is_space = False
        self.is_punct = text in ".,;:!?()[]\"'-"
        self.is_stop = False
        self.i = i

class SimpleSpan:
    def __init__(self, tokens, start, end, label=""):
        self.tokens = tokens
        self.start = start
        self.end = end
        self.text = " ".join(t.text for t in tokens)
        self.label_ = label

class SimpleDoc(list):
    def __init__(self, text):
        words = text.split()
        tokens = [SimpleToken(w, i) for i, w in enumerate(words)]
        super().__init__(tokens)
        self.text = text

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start or 0
            end = item.stop if item.stop is not None else len(self)
            return SimpleSpan(super().__getitem__(item), start, end)
        return super().__getitem__(item)

BASE = os.path.dirname(os.path.abspath(__file__))
INTENTS_PATH = os.path.join(BASE, "nlp_data", "intents_medicament.json")
SPACY_MODEL = "fr_core_news_sm"

# Type d'entité -> jeton de masquage et balise du corpus
ENTITY_TYPES = {
    "MEDICAMENT": "ent_med",
    "MOLECULE": "ent_mol",
    "MALADIE": "ent_mal",
    "CONDITION": "ent_cond",
    "EFFET": "ent_effet",
    "FAMILLE_EFFET": "ent_fam",
    "CLASSE": "ent_classe",
}
PLACEHOLDERS = {
    "{MED}": "MEDICAMENT", "{MED2}": "MEDICAMENT", "{MOL}": "MOLECULE", "{MAL}": "MALADIE",
    "{COND}": "CONDITION", "{EFFET}": "EFFET", "{FAM}": "FAMILLE_EFFET", "{CLASSE}": "CLASSE",
}

# Synonymes ajoutés aux libellés lus dans l'ontologie : (texte, type, [ids OWL])
SYNONYMES = [
    # Molécules (noms courants)
    ("aspirine", "MOLECULE", ["Mol_Acide_Acetylsalicylique"]),
    ("paracétamol", "MOLECULE", ["Mol_Paracetamol"]),
    # Maladies du module Maladie
    ("grippe", "MALADIE", ["Grippe_Saisonniere"]),
    ("angine", "MALADIE", ["Angine_Streptocoque"]),
    ("diabète", "MALADIE", ["Diabete_Type2"]),
    ("diabétique", "MALADIE", ["Diabete_Type2"]),
    ("hypertension", "MALADIE", ["Hypertension_Arterielle"]),
    ("hypertendu", "MALADIE", ["Hypertension_Arterielle"]),
    ("tension artérielle", "MALADIE", ["Hypertension_Arterielle"]),
    ("ulcère", "MALADIE", ["Ulcere_Gastrique_Sami"]),
    ("ulcère gastrique", "MALADIE", ["Ulcere_Gastrique_Sami"]),
    # Conditions cliniques
    ("enceinte", "CONDITION", ["Grossesse"]),
    ("grossesse", "CONDITION", ["Grossesse"]),
    ("allergie", "CONDITION", ["Allergie_Penicilline"]),
    ("allergique", "CONDITION", ["Allergie_Penicilline"]),
    ("pénicilline", "CONDITION", ["Allergie_Penicilline"]),
    ("insuffisance rénale", "CONDITION", ["Insuffisance_Renale_Severe"]),
    ("rein", "CONDITION", ["Insuffisance_Renale_Severe"]),
    ("insuffisance hépatique", "CONDITION", ["Insuffisance_Hepatique_Severe"]),
    ("foie", "CONDITION", ["Insuffisance_Hepatique_Severe"]),
    ("enfant", "CONDITION", ["Enfant_Infection_Virale"]),
    ("hypotension", "CONDITION", ["Hypotension_Severe"]),
    # Effets secondaires
    ("saignement", "EFFET", ["Saignement", "Hemorragie_Digestive"]),
    ("hémorragie", "EFFET", ["Saignement", "Hemorragie_Digestive"]),
    ("diarrhée", "EFFET", ["Diarrhee"]),
    ("nausée", "EFFET", ["Nausee_Effet"]),
    ("vomissement", "EFFET", ["Nausee_Effet"]),
    ("vertige", "EFFET", ["Vertige_Effet"]),
    ("mal de tête", "EFFET", ["Cephalee_Effet"]),
    ("maux de tête", "EFFET", ["Cephalee_Effet"]),
    ("céphalée", "EFFET", ["Cephalee_Effet"]),
    ("œdème", "EFFET", ["Oedeme_Chevilles"]),
    ("oedème", "EFFET", ["Oedeme_Chevilles"]),
    ("éruption", "EFFET", ["Eruption_Cutanee"]),
    ("urticaire", "EFFET", ["Eruption_Cutanee"]),
    ("bouton", "EFFET", ["Eruption_Cutanee"]),
    ("acidose", "EFFET", ["Acidose_Lactique"]),
    ("hépatotoxicité", "EFFET", ["Hepatotoxicite"]),
    # Familles d'effets
    ("digestif", "FAMILLE_EFFET", ["EffetDigestif"]),
    ("digestive", "FAMILLE_EFFET", ["EffetDigestif"]),
    ("neurologique", "FAMILLE_EFFET", ["EffetNeurologique"]),
    ("cutané", "FAMILLE_EFFET", ["EffetCutane"]),
    ("cardiovasculaire", "FAMILLE_EFFET", ["EffetCardiovasculaire"]),
    ("hépatique", "FAMILLE_EFFET", ["EffetHepatique"]),
    ("hématologique", "FAMILLE_EFFET", ["EffetHematologique"]),
    ("métabolique", "FAMILLE_EFFET", ["EffetMetabolique"]),
    # Classes thérapeutiques
    ("antibiotique", "CLASSE", ["Antibiotique"]),
    ("anti-inflammatoire", "CLASSE", ["AntiInflammatoire"]),
    ("anti inflammatoire", "CLASSE", ["AntiInflammatoire"]),
    ("AINS", "CLASSE", ["AntiInflammatoire"]),
    ("antalgique", "CLASSE", ["Antalgique"]),
    ("antidouleur", "CLASSE", ["Antalgique"]),
    ("analgésique", "CLASSE", ["Antalgique"]),
    ("antidiabétique", "CLASSE", ["Antidiabetique"]),
    ("antihypertenseur", "CLASSE", ["Antihypertenseur"]),
    ("anti-ulcéreux", "CLASSE", ["AntiUlcereux"]),
    ("antiulcéreux", "CLASSE", ["AntiUlcereux"]),
    ("IPP", "CLASSE", ["AntiUlcereux"]),
    ("anticoagulant", "CLASSE", ["Anticoagulant"]),
]

# Exemples de valeurs utilisées pour remplir les balises du corpus d'entraînement
EXEMPLES_BALISES = {
    "CONDITION": ["enceinte", "grossesse", "insuffisance rénale", "allergie"],
    "MALADIE": ["la grippe", "un ulcère", "l'hypertension", "le diabète"],
    "EFFET": ["saignements", "diarrhée", "vertiges", "nausées"],
    "FAMILLE_EFFET": ["digestifs", "neurologiques", "cutanés", "hépatiques"],
    "CLASSE": ["antibiotiques", "anticoagulants", "antalgiques", "AINS"],
}

NEGATIONS = {"sans", "aucun", "aucune", "pas", "non", "jamais"}
GRAVITE = {"grave", "severe", "serieux", "dangereux", "important"}


def strip_accents(text: str) -> str:
    text = text.replace("œ", "oe").replace("Œ", "OE")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


class NLPMedicamentPipeline:
    """Analyse une question en français : entités, intention et paramètres."""

    def __init__(self, medicament_service):
        self.service = medicament_service
        self.nlp = None
        if HAVE_SPACY:
            try:
                self.nlp = spacy.load(SPACY_MODEL, disable=["ner"])
            except Exception:
                self.nlp = None
        if self.nlp:
            self.matcher = PhraseMatcher(self.nlp.vocab, attr="NORM")
        else:
            self.matcher = None
        self.entities: Dict[str, Tuple[str, List[str]]] = {}
        self.single_words: Dict[str, str] = {}
        self._build_entity_matcher()
        self.classifier = None
        self.intent_labels: List[str] = []
        self.training_size = 0
        self._train_intent_classifier()

    # ------------------------------------------------------------------
    # 1. Analyse spaCy / Fallback
    # ------------------------------------------------------------------
    def _parse(self, text: str):
        if self.nlp:
            doc = self.nlp(text)
            for tok in doc:
                lemma = tok.lemma_ if tok.pos_ != "PROPN" else tok.text
                tok.norm_ = strip_accents(lemma.lower())
            return doc
        else:
            return SimpleDoc(text)

    # ------------------------------------------------------------------
    # 2. NER métier (PhraseMatcher alimenté par l'ontologie)
    # ------------------------------------------------------------------
    def _vocabulaire(self) -> List[Tuple[str, str, List[str]]]:
        termes: List[Tuple[str, str, List[str]]] = []
        if getattr(self.service, "loaded", False):
            rows = self.service._rows
            for r in rows("SELECT ?m ?n WHERE { ?m mdc:nomCommercial ?n }"):
                termes.append((r["n"], "MEDICAMENT", [r["m"].split("#")[-1]]))
            for r in rows("SELECT ?x ?n WHERE { ?x mdc:nomMolecule ?n }"):
                termes.append((r["n"], "MOLECULE", [r["x"].split("#")[-1]]))
            for r in rows("SELECT ?x ?n WHERE { ?x mdc:nomCondition ?n }"):
                termes.append((r["n"], "CONDITION", [r["x"].split("#")[-1]]))
            for r in rows("SELECT ?x ?n WHERE { ?x mal:nom ?n }"):
                termes.append((r["n"], "MALADIE", [r["x"].split("#")[-1]]))
        return termes + SYNONYMES

    def _build_entity_matcher(self):
        if self.nlp:
            self.matcher = PhraseMatcher(self.nlp.vocab, attr="NORM")
        self.entities.clear()
        self.single_words.clear()
        for texte, etype, ids in self._vocabulaire():
            variantes = {texte, texte + "s"}
            for v in variantes:
                pattern = self._parse(v)
                key = f"{etype}|{'|'.join(ids)}|{v}"
                if self.matcher:
                    self.matcher.add(key, [pattern])
                self.entities[key] = (etype, ids)
                if len(pattern) == 1:
                    self.single_words.setdefault(pattern[0].norm_, key)

    def refresh_entities(self):
        """À appeler après un ajout ou une suppression (CRUD) pour mettre à jour le vocabulaire."""
        self._build_entity_matcher()

    def _find_entities(self, doc) -> List[Dict[str, Any]]:
        if self.matcher:
            spans = []
            for match_id, start, end in self.matcher(doc):
                key = self.nlp.vocab.strings[match_id]
                span = doc[start:end]
                span.label_ = key
                spans.append(span)
            spans = filter_spans(spans)
            couverts = {i for s in spans for i in range(s.start, s.end)}

            corrections = []
            for tok in doc:
                if tok.i in couverts or tok.is_punct or tok.is_stop or len(tok.norm_) < 5:
                    continue
                if tok.pos_ not in ("PROPN", "NOUN", "ADJ", "X", "VERB"):
                    continue
                proches = get_close_matches(tok.norm_, list(self.single_words), n=1, cutoff=0.8)
                if proches and proches[0] != tok.norm_:
                    span = doc[tok.i:tok.i + 1]
                    span.label_ = self.single_words[proches[0]]
                    spans.append(span)
                    corrections.append(span.start)

            entites = []
            for span in sorted(spans, key=lambda s: s.start):
                etype, ids = self.entities[span.label_]
                entites.append({
                    "texte": span.text, "type": etype, "ids": ids,
                    "debut": span.start, "fin": span.end,
                    "corrige": span.start in corrections,
                })
            return entites
        else:
            entites = []
            doc_norm = " " + " ".join(t.norm_ for t in doc) + " "
            for key, (etype, ids) in self.entities.items():
                parts = key.split("|")
                term = parts[-1]
                term_norm = " " + strip_accents(term.lower()) + " "
                if term_norm in doc_norm:
                    entites.append({
                        "texte": term, "type": etype, "ids": ids,
                        "debut": 0, "fin": len(doc), "corrige": False
                    })
            return entites

    # ------------------------------------------------------------------
    # 3. Délexicalisation
    # ------------------------------------------------------------------
    @staticmethod
    def _masked_text(doc, entites) -> str:
        by_start = {e["debut"]: e for e in entites}
        out, i = [], 0
        while i < len(doc):
            if i in by_start:
                e = by_start[i]
                out.append(ENTITY_TYPES[e["type"]])
                i = e["fin"]
                continue
            tok = doc[i]
            if not tok.is_punct and not tok.is_space:
                out.append(tok.norm_)
            i += 1
        return " ".join(out)

    # ------------------------------------------------------------------
    # 4. Classifieur d'intention (scikit-learn)
    # ------------------------------------------------------------------
    def _exemples_balise(self) -> Dict[str, List[str]]:
        ex = {k: list(v) for k, v in EXEMPLES_BALISES.items()}
        meds = [t for t, ty, _ in self._vocabulaire() if ty == "MEDICAMENT"] or ["Doliprane"]
        mols = [t for t, ty, _ in self._vocabulaire() if ty == "MOLECULE"] or ["ibuprofène"]
        ex["MEDICAMENT"] = meds
        ex["MOLECULE"] = mols
        return ex

    def _train_intent_classifier(self):
        with open(INTENTS_PATH, encoding="utf-8") as f:
            corpus = json.load(f)["intents"]
        valeurs = self._exemples_balise()
        rng = random.Random(42)

        textes, labels, groupes = [], [], []
        for intent, phrases in corpus.items():
            for num, phrase in enumerate(phrases):
                variantes = 3 if "{" in phrase else 1    # augmentation : plusieurs valeurs d'entités
                for _ in range(variantes):
                    s = phrase
                    for balise, etype in PLACEHOLDERS.items():
                        while balise in s:
                            s = s.replace(balise, rng.choice(valeurs[etype]), 1)
                    doc = self._parse(s)
                    textes.append(self._masked_text(doc, self._find_entities(doc)))
                    labels.append(intent)
                    groupes.append(f"{intent}#{num}")        # même phrase modèle = même groupe

        features = make_union(
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        )
        self.classifier = make_pipeline(features, LogisticRegression(C=10, max_iter=3000))
        self.classifier.fit(textes, labels)
        self.training_data = (textes, labels, groupes)
        self.intent_labels = list(self.classifier.classes_)
        self.training_size = len(textes)
        nlp_info = f"spaCy {spacy.__version__} ({SPACY_MODEL})" if spacy else "SimpleTokenizer (pure Python)"
        print(f"[NLP Médicament] {nlp_info} + classifieur entraîné "
              f"sur {self.training_size} phrases, {len(self.intent_labels)} intentions.")

    # ------------------------------------------------------------------
    # 5. Paramètres (slots)
    # ------------------------------------------------------------------
    @staticmethod
    def _slots(doc, masked: str) -> Dict[str, Any]:
        norms = [t.norm_ for t in doc]
        texte = " ".join(norms)
        ordre = None
        if "moins cher" in texte or "pas cher" in texte or "croissant" in texte:
            ordre = "ASC"
        elif "cher" in norms or ("couter" in norms and "plus" in norms):
            ordre = "DESC"
        return {
            "negation": any(n in NEGATIONS for n in norms),
            "grave": any(n in GRAVITE for n in norms),
            "libre": "libre" in norms or "librement" in norms,
            "ordre": ordre,
            "superlatif": ("plus" in norms and "efficace" in norms) or "meilleur" in norms or "mieux" in norms,
        }

    # ------------------------------------------------------------------
    def analyse(self, question: str) -> Dict[str, Any]:
        doc = self._parse(question)
        entites = self._find_entities(doc)
        masked = self._masked_text(doc, entites)
        probas = self.classifier.predict_proba([masked])[0]
        classement = sorted(zip(self.intent_labels, probas), key=lambda x: -x[1])
        return {
            "tokens": [{"texte": t.text, "lemme": t.lemma_, "pos": t.pos_, "norme": t.norm_}
                       for t in doc if not t.is_space],
            "entites": entites,
            "texte_masque": masked,
            "intentions": [{"intention": i, "confiance": round(float(p), 3)} for i, p in classement],
            "slots": self._slots(doc, masked),
        }

    def outils(self) -> Dict[str, str]:
        import sklearn
        spacy_label = f"{spacy.__version__} — modèle {SPACY_MODEL}" if spacy else "SimpleTokenizer (fallback Python 3.14)"
        return {
            "spaCy": spacy_label,
            "scikit-learn": f"{sklearn.__version__} — TF-IDF + LogisticRegression ({self.training_size} phrases)",
            "difflib": "correction des fautes de frappe sur les entités",
        }
