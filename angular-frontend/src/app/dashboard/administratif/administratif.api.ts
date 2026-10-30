import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** Appels HTTP du module Service administratif (aucune modification de ApiService necessaire). */
@Injectable({ providedIn: 'root' })
export class AdministratifApi {
  private http = inject(HttpClient);
  private base = '/api/administratif';

  summary(): Observable<any> { return this.http.get<any>('/api/summary-administratif'); }
  options(): Observable<any> { return this.http.get<any>(`${this.base}/options`); }
  rendezVous(): Observable<any[]> { return this.http.get<any[]>(`${this.base}/rendez-vous`); }
  factures(): Observable<any[]> { return this.http.get<any[]>(`${this.base}/factures`); }
  createRdv(d: any): Observable<any> { return this.http.post<any>(`${this.base}/rendez-vous`, d); }
  updateRdv(id: string, d: any): Observable<any> { return this.http.put<any>(`${this.base}/rendez-vous/${encodeURIComponent(id)}`, d); }
  deleteRdv(id: string): Observable<any> { return this.http.delete<any>(`${this.base}/rendez-vous/${encodeURIComponent(id)}`); }
  createFacture(d: any): Observable<any> { return this.http.post<any>(`${this.base}/factures`, d); }
  createPaiement(d: any): Observable<any> { return this.http.post<any>(`${this.base}/paiements`, d); }
  reset(): Observable<any> { return this.http.post<any>(`${this.base}/reset`, {}); }
  ask(question: string): Observable<any> { return this.http.post<any>('/api/ia-administratif/ask', { question }); }
}
