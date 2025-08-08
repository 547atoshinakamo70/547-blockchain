import { useEffect, useState } from 'react'
export default function InstallPrompt(){
  const [d,setD]=useState(null), [ok,setOk]=useState(false)
  useEffect(()=>{ const h=(e)=>{ e.preventDefault(); setD(e); setOk(true) }; window.addEventListener('beforeinstallprompt',h); return ()=>window.removeEventListener('beforeinstallprompt',h)},[])
  if(!ok) return null
  return <button className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300" onClick={async()=>{ if(!d) return; d.prompt(); const {outcome}=await d.userChoice; if(outcome==='accepted') setD(null) }}>Instalar app</button>
}
