import axios from 'axios'

let NODE_URL = 'http://localhost:5000' // dev por defecto

export async function initApi(){
  try {
    const saved = (typeof window!=='undefined') ? localStorage.getItem('NODE_URL') : null
    if (saved) {
      NODE_URL = saved
      return
    }
    if (typeof window!=='undefined' && window.location.protocol==='https:' ) {
      // Estamos en Pages/HTTPS → intenta leer worker_url
      const r = await fetch('./node-config.json', { cache:'no-store' }).catch(()=>null)
      if (r && r.ok) {
        const cfg = await r.json()
        if (cfg?.worker_url) NODE_URL = cfg.worker_url
      }
    }
  } catch {}
}

export function setNodeUrl(url){ NODE_URL=url; try{ localStorage.setItem('NODE_URL', url) }catch{} }
export function getNodeUrl(){ return NODE_URL }
export function isMixedContent(url){ try{ return window.location.protocol==='https:' && /^http:\/\//i.test(url) }catch{ return false } }
function norm(err){ if (err?.response?.data) return new Error(typeof err.response.data==='string'? err.response.data: JSON.stringify(err.response.data)); return new Error(err?.message||'Network error') }

export async function getBalance(address){
  try{ const r=await axios.get(`${NODE_URL}/balance`, { params:{ address } }); return r.data }catch(e){ throw norm(e) }
}
export async function sendTx({ fromPrivateKey, to, amount }){
  try{ const r=await axios.post(`${NODE_URL}/send`, { from_private_key: fromPrivateKey, to, amount }); return r.data }catch(e){ throw norm(e) }
}
export async function mineOne(){
  try{ const r=await axios.post(`${NODE_URL}/mine`); return r.data }catch(e1){
    try{ const r2=await axios.get(`${NODE_URL}/mine`); return r2.data }catch(e2){ throw norm(e2) }
  }
}
export async function getPeers(){
  try{ const r=await axios.get(`${NODE_URL}/peers`); return r.data }catch(e){ throw norm(e) }
}
