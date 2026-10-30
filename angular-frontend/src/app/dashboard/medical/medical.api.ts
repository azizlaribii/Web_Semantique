import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
/** API autonome du module Service médical. */
@Injectable({ providedIn: 'root' })
export class MedicalApi {
 private http=inject(HttpClient); private base='/api/medical';
 summary():Observable<any>{return this.http.get<any>(`${this.base}/summary`);}
 options():Observable<any>{return this.http.get<any>(`${this.base}/options`);}
 records(type?:string):Observable<any[]>{return this.http.get<any[]>(`${this.base}/records`,{params:type?{type}:{}});}
 create(d:any):Observable<any>{return this.http.post<any>(`${this.base}/records`,d);}
 update(id:string,d:any):Observable<any>{return this.http.put<any>(`${this.base}/records/${encodeURIComponent(id)}`,d);}
 delete(id:string):Observable<any>{return this.http.delete<any>(`${this.base}/records/${encodeURIComponent(id)}`);}
 reset():Observable<any>{return this.http.post<any>(`${this.base}/reset`,{});}
 ask(question:string):Observable<any>{return this.http.post<any>('/api/ia-medical/ask',{question});}
}
