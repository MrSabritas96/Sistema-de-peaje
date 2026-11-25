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
 const [topic,select]=useState('vehiculos'),[answer,say]=useState(''),[notice,report]=useState(''),[rows,list]=useState<Record<string,unknown>[]>([]);
 async function request(path:string,options?:RequestInit){
  const r=await fetch('/api/v1/'+path,options);const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'Revisa los campos');return v
 }
 async function refresh(){try{list(await request('admin/'+topic));report('')}catch(e){report(String(e))}}
 return <><section><h2>Agente de consultas</h2><form onSubmit={async e=>{e.preventDefault();const data=new FormData(e.currentTarget);const file=data.get('file') as File;
 try{const r=file?.size?await request('chat/imagen',{method:'POST',body:data}):await request('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:data.get('pregunta')})});say(r.respuesta)}catch(e){say(String(e))}}}>
 <input placeholder="¿Pasó la placa 1234ABC?" aria-label="Pregunta" name="pregunta"/><input type="file" name="file" accept="image/jpeg,image/png,image/webp"/><button>Preguntar</button></form><output>{answer}</output></section>
 <section><h2>Administración</h2><select value={topic} onChange={e=>{select(e.target.value);list([]);report('')}}>{Object.keys(forms).map(t=><option key={t}>{t}</option>)}</select> <button onClick={refresh}>Ver registros</button>
 <form key={topic} style={{marginTop:18}} onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);const body=Object.fromEntries(forms[topic].map(k=>[k.key,k.numeric?Number(f.get(k.key)):k.key==='activo'?f.get(k.key)==='Activo':f.get(k.key)]));
 try{await request(topic,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await refresh();report('Registro guardado')}catch(e){report(String(e))}}}>
 {forms[topic].map(k=><label key={k.key} style={{display:'inline-grid',margin:'4px 8px 8px 0'}}>{k.label}{k.values?<select name={k.key}>{k.values.map(v=><option key={v}>{v}</option>)}</select>:<input required type={k.numeric?'number':'text'} step="any" name={k.key}/>}</label>)}<button>Guardar</button></form>
 <output>{notice}</output>{rows.length>0&&<div className="scroll"><table><thead><tr>{Object.keys(rows[0]).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{Object.entries(r).map(([k,v])=><td key={k}>{String(v)}</td>)}</tr>)}</tbody></table></div>}</section></>
}
