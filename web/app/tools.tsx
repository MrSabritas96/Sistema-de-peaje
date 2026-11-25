'use client';
import {useState} from 'react';
type Field={key:string,label:string,values?:string[],numeric?:boolean};
const forms:Record<string,Field[]>={
 vehiculos:[{key:'placa',label:'Placa'},{key:'categoria',label:'Categoría',values:['auto','moto','minibus','camion','bus']},{key:'saldo',label:'Saldo (Bs)',numeric:true}],
 tarifas:[{key:'categoria',label:'Categoría',values:['auto','moto','minibus','camion','bus']},{key:'ejes',label:'Ejes',numeric:true},{key:'monto',label:'Monto (Bs)',numeric:true}],
 casetas:[{key:'id',label:'Número',numeric:true},{key:'nombre',label:'Nombre'},{key:'origen',label:'Origen'},{key:'destino',label:'Destino'}],
 usuarios:[{key:'email',label:'Correo Google'},{key:'rol',label:'Rol',values:['OPERADOR','ADMIN']},{key:'activo',label:'Acceso',values:['Activo','Deshabilitado']}]
};
export function Tools(){
 const [observed,setObserved]=useState<Record<string,unknown>[]|null>(null);
 const [topic,select]=useState('vehiculos'),[answer,say]=useState(''),[notice,report]=useState(''),[rows,list]=useState<Record<string,unknown>[]>([]);
 async function request(path:string,options?:RequestInit){
  const r=await fetch('/api/v1/'+path,options);const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'Revisa los campos');return v
 }
 async function refresh(){try{const data=await request('admin/'+topic);list(data);report(data.length?'': 'Sin registros activos')}catch(e){report(String(e))}}
 return <><section><h2>Agente de consultas</h2><form onSubmit={async e=>{e.preventDefault();const data=new FormData(e.currentTarget);const file=data.get('file') as File;
 try{const r=file?.size?await request('chat/imagen',{method:'POST',body:data}):await request('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:data.get('pregunta')})});say(r.respuesta)}catch(e){say(String(e))}}}>
 <input placeholder="¿Pasó la placa 1234ABC?" aria-label="Pregunta" name="pregunta"/><input type="file" name="file" accept="image/jpeg,image/png,image/webp"/><button>Preguntar</button></form><output>{answer}</output></section>
 <section><h2>Administración</h2><button onClick={async()=>{try{setObserved(await request('admin/observados'))}catch(e){report(String(e))}}}>Ver placas detectadas por la cámara</button>{observed&&<div className="scroll"><h3>Última detección por placa</h3>{observed.length?<table><thead><tr><th>Placa leída</th><th>Categoría</th><th>Ejes</th><th>Último paso</th></tr></thead><tbody>{observed.map(r=><tr key={String(r.placa)}><td>{String(r.placa)}</td><td>{String(r.categoria??'Pendiente')}</td><td>{String(r.ejes??'—')}</td><td>{new Date(String(r.fecha)).toLocaleString('es-BO')}</td></tr>)}</tbody></table>:<p>Aún no hay placas legibles.</p>}</div>}<h3>Catálogos</h3><select value={topic} onChange={e=>{select(e.target.value);list([]);report('')}}>{Object.keys(forms).map(t=><option key={t}>{t}</option>)}</select> <button onClick={refresh}>Ver registros</button>
 <form key={topic} style={{marginTop:18}} onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);const body=Object.fromEntries(forms[topic].map(k=>[k.key,k.numeric?Number(f.get(k.key)):k.key==='activo'?f.get(k.key)==='Activo':f.get(k.key)]));
 try{await request(topic,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await refresh();report('Registro guardado')}catch(e){report(String(e))}}}>
 {forms[topic].map(k=><label key={k.key} style={{display:'inline-grid',margin:'4px 8px 8px 0'}}>{k.label}{k.values?<select name={k.key}>{k.values.map(v=><option key={v}>{v}</option>)}</select>:<input required type={k.numeric?'number':'text'} step="any" name={k.key}/>}</label>)}<button>Guardar</button></form>
 <output>{notice}</output>{rows.length>0&&<div className="scroll"><table><thead><tr>{Object.keys(rows[0]).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{Object.entries(r).map(([k,v])=><td key={k}>{String(v)}</td>)}</tr>)}</tbody></table></div>}</section></>
}
