import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
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

  getMedicamentOptions(): Observable<any> {
    return this.http.get<any>('/api/medicament-options');
  }

  // CRUD Médicament : chaque appel exécute une requête SPARQL Update côté serveur
  createMedicament(data: any): Observable<any> {
    return this.http.post<any>('/api/medicaments', data);
  }

  updateMedicament(id: string, data: any): Observable<any> {
    return this.http.put<any>(`/api/medicaments/${encodeURIComponent(id)}`, data);
  }

  deleteMedicament(id: string): Observable<any> {
    return this.http.delete<any>(`/api/medicaments/${encodeURIComponent(id)}`);
  }

  resetMedicaments(): Observable<any> {
    return this.http.post<any>('/api/medicaments/reset', {});
  }

  // ── SPARQL ────────────────────────────────────────────
  runSparql(query: string): Observable<any> {
    return this.http.post<any>('/api/sparql', { query });
  }

  // ── Reload OWL ────────────────────────────────────────
  private ontologyChangedSource = new Subject<void>();
  public ontologyChanged$ = this.ontologyChangedSource.asObservable();

  notifyOntologyChanged(): void {
    this.ontologyChangedSource.next();
  }

  reloadOntologie(): Observable<any> {
    return this.http.post<any>('/api/reload', {});
  }

  uploadOntology(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<any>('/api/ontology/upload', formData);
  }

  getOntologyFiles(): Observable<any> {
    return this.http.get<any>('/api/ontology/files');
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

  // ── Explorateur Dynamique Ontologie ────────────────────
  getOntologySchema(): Observable<any> {
    return this.http.get<any>('/api/ontology/schema');
  }

  getIndividualDetail(name: string): Observable<any> {
    return this.http.get<any>(`/api/ontology/individual/${encodeURIComponent(name)}`);
  }

  reloadOntology(): Observable<any> {
    return this.http.post<any>('/api/ontology/reload', {});
  }
}
