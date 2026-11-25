'use client';
import {useState} from 'react';
export function Confirm({id,done}:{id:number,done:()=>void}){
 const [open,setOpen]=useState(false),[notice,report]=useState('');
 if(!open)return <button onClick={()=>setOpen(true)}>Revisar</button>;
 return <form onSubmit={async e=>{
  e.preventDefault();const f=new FormData(e.currentTarget);
  try{const r=await fetch('/api/v1/pasos/'+id+'/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({placa:String(f.get('placa')).trim().toUpperCase(),categoria:f.get('categoria'),ejes:Number(f.get('ejes')),motivo:f.get('motivo')})});const v=await r.json();if(!r.ok)throw Error(v.detail);setOpen(false);done()}catch(err){report(String(err))}
 }}>
 <input aria-label="Placa confirmada" name="placa" placeholder="Placa" pattern="[0-9]{3,4}[A-Za-z]{3}" required/>
 <select aria-label="Categoría" name="categoria">{['auto','moto','minibus','camion','bus'].map(x=><option key={x}>{x}</option>)}</select>
 <input aria-label="Número de ejes" type="number" name="ejes" min="2" max="8" required placeholder="Ejes"/>
 <input aria-label="Motivo" name="motivo" minLength={4} placeholder="Motivo de la corrección" required/>
 <button>Confirmar y aplicar tarifa</button> <button type="button" onClick={()=>setOpen(false)}>Cancelar</button><output>{notice}</output></form>
}
