import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MedicalApi } from './medical.api';
@Component({
 selector:'app-medical-crud',standalone:true,imports:[CommonModule,FormsModule],
 template:`
 <div class="kpis">@for(k of kpis;track k.key){<div class="kpi glass-panel"><span class="kpi-val">{{summary()[k.key]||0}}</span><span class="kpi-lbl">{{k.label}}</span></div>}</div>
 <div class="crud-layout">
  <form class="glass-panel crud-form" (ngSubmit)="submit()" autocomplete="off">
   <h2>{{editId()?'Modifier un élément':'Ajouter un élément médical'}}</h2>
   <p class="crud-sub">Les actions mettent à jour <code>ontologie_medicale.owl</code>.</p>
   <label class="field">Type *
    <select class="input-glass" name="type" [(ngModel)]="form.type" (ngModelChange)="typeChanged()">
     <option>Consultation</option><option>Opération</option><option>Ordonnance</option>
    </select>
   </label>
   <label class="field">Sous-type
    <select class="input-glass" name="sousType" [(ngModel)]="form.sousType"><option value="">— Aucun —</option>
     @for(s of options().sousTypes?.[form.type]||[];track s){<option [value]="s">{{s}}</option>}
    </select>
   </label>
   <label class="field">Libellé *<input class="input-glass" name="label" [(ngModel)]="form.label" required placeholder="Nom de l'acte médical"></label>
   <label class="field">Date<input class="input-glass" type="date" name="date" [(ngModel)]="form.date"></label>
   @if(form.type==='Consultation'){<label class="field">Tarif (TND)<input class="input-glass" type="number" min="0" name="tarif" [(ngModel)]="form.tarif"></label>}
   @if(form.type==='Opération'){<label class="field">Durée (minutes)<input class="input-glass" type="number" min="1" name="duree" [(ngModel)]="form.duree"></label><label><input type="checkbox" name="urgent" [(ngModel)]="form.urgent"> Opération urgente</label>}
   @if(form.type==='Ordonnance'){<label class="field">Durée de validité (jours)<input class="input-glass" type="number" min="1" name="validite" [(ngModel)]="form.validite"></label>}
   <label class="field">Patient
    <select class="input-glass" name="patient" [(ngModel)]="form.patient"><option value="">— Aucun —</option>@for(p of options().patients;track p.id){<option [value]="p.id">{{p.nom}}</option>}</select>
   </label>
   <label class="field">Médecin
    <select class="input-glass" name="medecin" [(ngModel)]="form.medecin"><option value="">— Aucun —</option>@for(m of options().medecins;track m.id){<option [value]="m.id">{{m.nom}}</option>}</select>
   </label>
   <div class="actions"><button class="btn-primary" type="submit" [disabled]="saving()">{{saving()?'Enregistrement…':editId()?'Enregistrer les modifications':'Ajouter (INSERT DATA)'}}</button>
    @if(editId()){<button class="btn-secondary" type="button" (click)="cancelEdit()">Annuler</button>}</div>
   @if(status().text){<p class="status" [class.ok]="status().ok" [class.error]="!status().ok">{{status().text}}</p>}
  </form>
  <div class="glass-panel list-panel">
   <div class="head"><div><h2>Éléments médicaux</h2><p class="crud-sub">{{records().length}} individus dans l'ontologie.</p></div>
    <select class="input-glass" [(ngModel)]="filter" (ngModelChange)="load()" aria-label="Filtrer"><option value="">Tous</option><option>Consultation</option><option>Opération</option><option>Ordonnance</option></select>
   </div>
   @for(r of records();track r.id){<article class="record" [class.editing]="editId()===r.id">
    <div class="main"><b>{{r.label}}</b><div class="meta">{{r.type}} · {{r.sousType||r.uri}}</div>
     @for(k of objectKeys(r.properties);track k){<small>{{k}} : {{r.properties[k]}}</small>}
    </div><div class="actions-col"><button type="button" class="mini" (click)="startEdit(r)">Modifier</button><button type="button" class="mini danger" (click)="remove(r.id)">Supprimer</button></div>
   </article>}@empty{<p class="muted">Aucun élément trouvé pour ce filtre.</p>}
   @if(records().length){<button class="btn-secondary" type="button" (click)="reset()">Réinitialiser l'ontologie</button>}
  </div>
 </div>`,
 styles:[`
 :host{display:block}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}
 .kpi{display:flex;flex-direction:column;padding:12px 16px}.kpi-val{font-size:1.35rem;font-weight:700;color:var(--accent-purple)}.kpi-lbl{font-size:.74rem;color:var(--text-dim);text-transform:uppercase}
 .crud-layout{display:grid;grid-template-columns:minmax(290px,370px) minmax(0,1fr);gap:18px;align-items:start}
 .crud-form,.list-panel{padding:18px;display:flex;flex-direction:column;gap:11px;min-width:0}.crud-sub{font-size:.8rem;color:var(--text-dim);margin:0}
 .field{display:flex;flex-direction:column;gap:4px;font-size:.8rem;font-weight:600}.field input,.field select{width:100%;box-sizing:border-box}
 .actions,.head{display:flex;gap:8px;justify-content:space-between;align-items:center;flex-wrap:wrap}.record{display:flex;justify-content:space-between;gap:12px;padding:12px;border:1px solid var(--border-subtle);border-radius:var(--radius-md);background:#fff}
 .record.editing{border-color:var(--accent-purple)}.main{display:flex;flex-direction:column;gap:4px;min-width:0}.meta,small,.muted{color:var(--text-dim);font-size:.78rem}
 .actions-col{display:flex;flex-direction:column;gap:6px}.mini{padding:5px 10px;border:1px solid var(--border-subtle);border-radius:8px;background:#f8fafc;cursor:pointer}.danger{color:#be123c}
 .status{font-size:.82rem}.status.ok{color:#047857}.status.error{color:#be123c}
 @media(max-width:950px){.crud-layout{grid-template-columns:1fr}}
 `]
})
export class MedicalCrudComponent implements OnInit{
 private api=inject(MedicalApi);records=signal<any[]>([]);options=signal<any>({patients:[],medecins:[],sousTypes:{}});
 summary=signal<any>({});saving=signal(false);editId=signal('');status=signal<any>({text:'',ok:true});
 filter='';form:any=this.emptyForm();kpis=[{key:'Consultation',label:'Consultations'},{key:'Opération',label:'Opérations'},{key:'Ordonnance',label:'Ordonnances'}];
 ngOnInit(){this.api.options().subscribe(o=>this.options.set(o));this.load();}
 emptyForm(){return {type:'Consultation',sousType:'',label:'',date:'',tarif:'',duree:'',validite:'',urgent:false,patient:'',medecin:''};}
 typeChanged(){this.form.sousType='';}
 load(){this.api.records(this.filter||undefined).subscribe({next:r=>this.records.set(r),error:e=>this.setError(e)});this.api.summary().subscribe(s=>this.summary.set(s));}
 submit(){if(!this.form.label.trim()){this.status.set({text:'Le libellé est obligatoire.',ok:false});return;}this.saving.set(true);
  const req=this.editId()?this.api.update(this.editId(),this.form):this.api.create(this.form);
  req.subscribe({next:()=>{this.saving.set(false);this.status.set({text:'Élément enregistré dans l’ontologie médicale.',ok:true});this.cancelEdit();this.load();},
   error:e=>{this.saving.set(false);this.setError(e);}});}
 startEdit(r:any){this.editId.set(r.id);this.form={...this.emptyForm(),type:r.type,sousType:r.sousType,label:r.label,
  date:r.properties?.dateConsultation||r.properties?.['date_de_l’opération']||r.properties?.dateOrdonnance||''};}
 cancelEdit(){this.editId.set('');this.form=this.emptyForm();}
 remove(id:string){if(!confirm('Supprimer cet élément médical ?'))return;this.api.delete(id).subscribe({next:()=>{this.status.set({text:'Élément supprimé.',ok:true});this.load();},error:e=>this.setError(e)});}
 reset(){if(!confirm('Restaurer l’ontologie médicale originale ? Les modifications seront perdues.'))return;this.api.reset().subscribe({next:()=>{this.cancelEdit();this.load();this.status.set({text:'Ontologie restaurée.',ok:true});},error:e=>this.setError(e)});}
 setError(e:any){this.status.set({text:e.error?.error||'Erreur serveur.',ok:false});}
 objectKeys(o:any){return Object.keys(o||{});}
}
