import { useEffect, useState } from 'react'
import { Wallet, Pickaxe, Send, Link2, Link as LinkIcon, Shield } from 'lucide-react'
import { getBalance, sendTx, mineOne, setNodeUrl, getNodeUrl, isMixedContent } from './lib/api'
import { cjCreateSession, cjRegister, cjGetTx, cjSubmitSig, cjBroadcast } from './lib/coinjoin'
import InstallPrompt from './components/InstallPrompt'

export default function App(){
  const [address,setAddress]=useState(''); const [balance,setBalance]=useState(null)
  const [to,setTo]=useState(''); const [amount,setAmount]=useState('0'); const [pk,setPk]=useState('')
  const [node,setNode]=useState(getNodeUrl()); const [busy,setBusy]=useState(false); const [msg,setMsg]=useState('')

  // CoinJoin (beta)
  const [cjAmount,setCjAmount]=useState('0'); const [cjParts,setCjParts]=useState(3)
  const [cjSession,setCjSession]=useState(''); const [cjUtxos,setCjUtxos]=useState('[]')
  const [cjChange,setCjChange]=useState(''); const [cjOutput,setCjOutput]=useState(''); const [cjMsg,setCjMsg]=useState('')

  useEffect(()=>{ setNodeUrl(node) },[node])

  const blocked = isMixedContent(node)

  return (
    <div className="min-h-screen px-4 py-8 max-w-3xl mx-auto text-white">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold flex items-center gap-3">
          <Wallet size={28}/> 547 Wallet
        </h1>
        <InstallPrompt/>
      </header>

      <div className="rounded-2xl p-4 mb-6 bg-white/5 border border-white/10">
        <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Link2 size={16}/> Nodo</div>
        <div className="flex gap-2">
          <input className="flex-1 px-3 py-2 rounded-xl bg-white/10 outline-none" value={node} onChange={e=>setNode(e.target.value)} placeholder="https://<tu-worker>.workers.dev" />
          <button className="px-3 py-2 rounded-xl bg-white/10" onClick={()=>navigator.clipboard.writeText(node)} title="Copiar URL"><LinkIcon size={18}/></button>
        </div>
        {blocked && (
          <div className="mt-3 rounded-xl p-3 bg-red-500/20 border border-red-400/40 text-sm">
            La PWA está en <b>HTTPS</b> y tu nodo es <b>HTTP</b>, el navegador bloquea las peticiones.
            Usa el <b>proxy HTTPS</b> (Cloudflare Worker) como URL de nodo.
          </div>
        )}
      </div>

      <section className="grid gap-6">
        {/* Balance */}
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Wallet size={16}/> Balance</div>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 rounded-xl bg-white/10" value={address} onChange={e=>setAddress(e.target.value)} placeholder="Dirección" />
            <button disabled={busy||blocked} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await getBalance(address); setBalance(r.balance ?? r) }catch(e){ setMsg(String(e)) } finally{ setBusy(false) } }} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Consultar</button>
          </div>
          {balance!==null && <div className="mt-3 text-lg">Balance: <b>{balance}</b></div>}
          {msg && <div className="mt-2 text-red-300 text-sm">{msg}</div>}
        </div>

        {/* Enviar */}
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Send size={16}/> Enviar</div>
          <div className="grid gap-2">
            <input className="px-3 py-2 rounded-xl bg-white/10" value={pk} type="password" onChange={e=>setPk(e.target.value)} placeholder="Clave privada (hex) — temporal" />
            <input className="px-3 py-2 rounded-xl bg-white/10" value={to} onChange={e=>setTo(e.target.value)} placeholder="Dirección destino" />
            <input className="px-3 py-2 rounded-xl bg-white/10" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="Monto" />
            <button disabled={busy||blocked} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await sendTx({ fromPrivateKey: pk, to, amount: Number(amount) }); setMsg(JSON.stringify(r)) }catch(e){ setMsg(String(e)) } finally{ setBusy(false) }}} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Enviar transacción</button>
          </div>
          {msg && <div className="mt-2 text-sm opacity-80 break-all">{msg}</div>}
        </div>

        {/* Minar */}
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Pickaxe size={16}/> Minar</div>
          <button disabled={busy||blocked} onClick={async()=>{ setBusy(true); setMsg(''); try{ const r=await mineOne(); setMsg(JSON.stringify(r)) }catch(e){ setMsg(String(e)) } finally{ setBusy(false) }}} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">Minar 1 bloque</button>
          {msg && <div className="mt-2 text-sm opacity-80 break-all">{msg}</div>}
        </div>

        {/* CoinJoin (beta) */}
        <div className="rounded-2xl p-4 bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2 text-sm opacity-80"><Shield size={16}/> CoinJoin (beta)</div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="grid gap-2">
              <input className="px-3 py-2 rounded-xl bg-white/10" value={cjAmount} onChange={e=>setCjAmount(e.target.value)} placeholder="Monto por participante" />
              <input className="px-3 py-2 rounded-xl bg-white/10" type="number" value={cjParts} onChange={e=>setCjParts(Number(e.target.value)||2)} placeholder="Participantes" />
              <button disabled={busy||blocked} className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50"
                onClick={async()=>{ setBusy(true); setCjMsg(''); try{ const r=await cjCreateSession({ amount:Number(cjAmount), participants:cjParts }); setCjSession(r.sessionId||''); setCjMsg(JSON.stringify(r)) }catch(e){ setCjMsg(String(e)) } finally{ setBusy(false) } }}>
                Crear sesión
              </button>
            </div>
            <div className="grid gap-2">
              <input className="px-3 py-2 rounded-xl bg-white/10" value={cjSession} onChange={e=>setCjSession(e.target.value)} placeholder="Session ID" />
              <input className="px-3 py-2 rounded-xl bg-white/10" value={cjUtxos} onChange={e=>setCjUtxos(e.target.value)} placeholder='UTXOs JSON ej: [{"txid":"..","vout":0}]' />
              <input className="px-3 py-2 rounded-xl bg-white/10" value={cjChange} onChange={e=>setCjChange(e.target.value)} placeholder="Dirección de cambio" />
              <input className="px-3 py-2 rounded-xl bg-white/10" value={cjOutput} onChange={e=>setCjOutput(e.target.value)} placeholder="Dirección de salida" />
              <button disabled={busy||blocked} className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-50"
                onClick={async()=>{ setBusy(true); setCjMsg(''); try{ const r=await cjRegister({ sessionId:cjSession, utxos:JSON.parse(cjUtxos||'[]'), changeAddress:cjChange, outputAddress:cjOutput }); setCjMsg(JSON.stringify(r)) }catch(e){ setCjMsg(String(e)) } finally{ setBusy(false) } }}>
                Unirme
              </button>
            </div>
          </div>
          <div className="mt-3 flex gap-2 flex-wrap">
            <button disabled={busy||blocked} className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20" onClick={async()=>{ setBusy(true); setCjMsg(''); try{ const r=await cjGetTx(cjSession); setCjMsg(JSON.stringify(r)) }catch(e){ setCjMsg(String(e)) } finally{ setBusy(false) } }}>Obtener TX</button>
            <button disabled={busy||blocked} className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20" onClick={async()=>{ setBusy(true); setCjMsg(''); try{ const r=await cjSubmitSig({ sessionId:cjSession, signatures:[] }); setCjMsg(JSON.stringify(r)) }catch(e){ setCjMsg(String(e)) } finally{ setBusy(false) } }}>Enviar firmas</button>
            <button disabled={busy||blocked} className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20" onClick={async()=>{ setBusy(true); setCjMsg(''); try{ const r=await cjBroadcast(cjSession); setCjMsg(JSON.stringify(r)) }catch(e){ setCjMsg(String(e)) } finally{ setBusy(false) } }}>Emitir</button>
          </div>
          {cjMsg && <div className="mt-2 text-sm opacity-80 break-all">{cjMsg}</div>}
        </div>
      </section>

      <footer className="mt-10 opacity-60 text-sm">PWA instalable • HTTPS proxy • CoinJoin beta • 547 ©</footer>
    </div>
  )
}
