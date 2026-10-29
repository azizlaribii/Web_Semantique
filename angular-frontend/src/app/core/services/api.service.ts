import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Personne } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // ── Personnes ─────────────────────────────────────────
  getPersonnes(): Observable<Personne[]> {
    return this.http.get<Personne[]>('/api/personnes');
  }

  addPersonne(data: any): Observable<any> {
    return this.http.post<any>('/api/personnes/add', data);
  }

  // ── IA ────────────────────────────────────────────────
  askIA(question: string, module: string = 'auto'): Observable<any> {
    return this.http.post<any>('/api/ia/ask', { question, module });
  }

  // ── Status / Summary ──────────────────────────────────
  getStatus(): Observable<any> {
    return this.http.get<any>('/api/status');
  }

  getSummary(): Observable<any> {
    return this.http.get<any>('/api/summary');
  }

  // ── Maladies ──────────────────────────────────────────
  getMaladies(): Observable<any[]> {
    return this.http.get<any[]>('/api/maladies');
  }

  getMaladieOntologyStructure(): Observable<any> {
    return this.http.get<any>('/api/ontology/maladie-structure');
  }

  // ── Medicaments ───────────────────────────────────────
  getMedicaments(): Observable<any[]> {
    return this.http.get<any[]>('/api/medicaments');
  }

  // ── SPARQL ────────────────────────────────────────────
  runSparql(query: string): Observable<any> {
    return this.http.post<any>('/api/sparql', { query });
  }

  // ── Reload OWL ────────────────────────────────────────
  reloadOntologie(): Observable<any> {
    return this.http.post<any>('/api/reload', {});
  }

  // ── CRUD Ontologie Interactif ─────────────────────────
  getDynamicEntities(): Observable<any> {
    return this.http.get<any>('/api/ontology/dynamic-entities');
  }

  deleteOntologyRow(item: any): Observable<any> {
    return this.http.post<any>('/api/ontology/row/delete', { item });
  }

  updateOntologyRow(old_item: any, new_item: any): Observable<any> {
    return this.http.post<any>('/api/ontology/row/update', { old_item, new_item });
  }

  addOntologyRow(type: string, data: any): Observable<any> {
    return this.http.post<any>('/api/ontology/row/add', { type, data });
  }
}
