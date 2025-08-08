import { useEffect, useState } from 'react'
export default function InstallPrompt(){
  const [deferred, setDeferred] = useState(null)
  const [supported, setSupported] = useState(false)
  useEffect(()=>{ const h = (e)=>{ e.preventDefault(); setDeferred(e); setSupported(true) }; window.addEventListener('beforeinstallprompt', h); return ()=>window.removeEventListener('beforeinstallprompt', h)},[])
  if(!supported) return null
  return <button className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 transition" onClick={async()=>{ if(!deferred) return; deferred.prompt(); const { outcome } = await deferred.userChoice; if(outcome==='accepted') setDeferred(null) }}>Instalar app</button>
}
