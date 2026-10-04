import { useEffect, useRef, useState } from 'react';

export function useRun(onResult:(data:any)=>void, onReady:()=>void) {
 const [id,setId]=useState<string|null>(()=>new URLSearchParams(location.search).get('run'));
 const [run,setRun]=useState<any>(null);
 const [error,setError]=useState('');
 const handlers=useRef({onResult,onReady});handlers.current={onResult,onReady};
 const loaded=useRef<string|null>(null);
 const [submitting,setSubmitting]=useState(false);
 const terminal=['complete','completed','awaiting_review','failed','cancelled'];
 function activate(next:string|null){
  const url=new URL(location.href);
  if(next)url.searchParams.set('run',next);else url.searchParams.delete('run');
  url.searchParams.delete('view');url.searchParams.delete('field');
  history.replaceState({},'',url.pathname+url.search+url.hash);
  setId(next);setRun(null);setError('');loaded.current=null;
 }
 useEffect(()=>{
  if(!id)return;let disposed=false;let timer:ReturnType<typeof setTimeout>;
  async function poll(){
   try{
    const response=await fetch(`/api/runs/${encodeURIComponent(id!)}`);
    const body=await response.json();
    if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'Could not check this run.');
    if(disposed)return;setRun(body);setError('');
    if(['complete','completed','awaiting_review'].includes(body.state)&&loaded.current!==id){
     const result=await fetch(`/api/runs/${encodeURIComponent(id!)}/results`);
     if(!result.ok)throw Error('The result is not ready to open. Retrying…');
     const data=await result.json();if(disposed)return;
     loaded.current=id;handlers.current.onResult(data);
     if(location.hash.startsWith('#/progress'))handlers.current.onReady();
    }
    if(body.state==='failed')setError(body.error?.message||body.error||'The engine could not analyse these files.');
    if(!terminal.includes(body.state))timer=setTimeout(poll,1500);
   }catch(e){if(!disposed){setError(`Connection interrupted. The analysis may still be running. ${(e as Error).message}`);timer=setTimeout(poll,2500);}}
  }
  void poll();return()=>{disposed=true;clearTimeout(timer);};
 },[id]);
 async function start(uploadId:string,criteria:any,metadata:any){
  setSubmitting(true);setError('');
  try{const r=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uploadId,criteria,metadata})});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Analysis could not be started.');activate(d.id);setRun(d);return d.id;}
  catch(e){setError((e as Error).message);throw e;}finally{setSubmitting(false);}
 }
 async function cancel(){if(!id)return;const r=await fetch(`/api/runs/${encodeURIComponent(id)}/cancel`,{method:'POST'});if(r.ok)setRun(await r.json());else setError('Cancellation could not be confirmed. The analysis may still be running.');}
 return {id,run,error,start,cancel,clear:()=>activate(null),submitting,busy:submitting||!!(id&&run&&!terminal.includes(run.state))};
}
