# -*- coding: utf-8 -*-
"""Interface IA NL -> sélection d'intention -> SPARQL -> RDFLib."""
class IAMedicalService:
    def __init__(self, service): self.service=service
    def refresh(self): return None
    def answer_question(self, question): return self.service.ask(question)
