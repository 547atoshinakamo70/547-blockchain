import { useEffect, useState } from 'react'
import { Wallet, Pickaxe, Send, Link2, Link as LinkIcon } from 'lucide-react'
import { getBalance, sendTx, mineOne, setNodeUrl, getNodeUrl } from './lib/api'
import InstallPrompt from './components/InstallPrompt'
export default function App(){
  const [address,setAddress]=useState(''); const [balance,setBalance]=useState(null)
  const [to,setTo]=useState(''); const [amount,setAmount]=useState('0'); const [pk,setPk]=useState('')
  const [node,setNode]=useState(getNodeUrl()); const [busy,setBusy]=useState(false); const [msg,setMsg]=useState('')
  useEffect(()=>{ setNodeUrl(node) },[node])
  return (
    <div className="min-h-screen px-4 py-8 max-w-3xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold flex items-center gap-3"><Wallet size={28}/> 547 Wallet</h1>
        <InstallPrompt/>
      </header>
      <section className="grid gap-6">
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Link2 size={16}/> Nodo</div>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 rounded-xl bg-white/10 outline-none" value={node} onChange={e=>setNode(e.target.value)} placeholder="http://localhost:5000"/>
            <button className="px-3 py-2 rounded-xl bg-white/10" onClick={()=>navigator.clipboard.writeText(node)} title="Copiar URL"><LinkIcon size={18}/></button>
          </div>
        </div>
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Wallet size={16}/> Balance</div>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 rounded-xl bg-white/10" value={address} onChange={e=>setAddress(e.target.value)} placeholder="Dirección"/>
            <button disabled={busy} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await getBalance(address); setBalance(r.balance ?? r) }catch(e){ setMsg(e.message) } finally{ setBusy(false) }}} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Consultar</button>
          </div>
          {balance!==null && <div className="mt-3 text-lg">Balance: <b>{balance}</b></div>}
          {msg && <div className="mt-2 text-red-300 text-sm">{msg}</div>}
        </div>
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Send size={16}/> Enviar</div>
          <div className="grid gap-2">
            <input className="px-3 py-2 rounded-xl bg-white/10" value={pk} type="password" onChange={e=>setPk(e.target.value)} placeholder="Clave privada (hex) — temporal"/>
            <input className="px-3 py-2 rounded-xl bg-white/10" value={to} onChange={e=>setTo(e.target.value)} placeholder="Dirección destino"/>
            <input className="px-3 py-2 rounded-xl bg-white/10" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="Monto"/>
            <button disabled={busy} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await sendTx({ fromPrivateKey: pk, to, amount: Number(amount) }); setMsg(JSON.stringify(r)) }catch(e){ setMsg(e.message) } finally{ setBusy(false) }}} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Enviar transacción</button>
          </div>
          {msg && <div className="mt-2 text-sm opacity-80 break-all">{msg}</div>}
        </div>
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Pickaxe size={16}/> Minar</div>
          <button disabled={busy} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await mineOne(); setMsg(JSON.stringify(r)) }catch(e){ setMsg(e.message) } finally{ setBusy(false) }}} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Minar 1 bloque</button>
          {msg && <div className="mt-2 text-sm opacity-80 break-all">{msg}</div>}
        </div>
      </section>
      <footer className="mt-10 opacity-60 text-sm">PWA instalable • Funciona offline (caché) • 547 ©</footer>
    </div>
  )
}
