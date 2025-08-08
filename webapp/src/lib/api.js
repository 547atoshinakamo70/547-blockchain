import axios from 'axios'

const DEFAULT_NODE =
  (typeof window !== 'undefined' && localStorage.getItem('NODE_URL')) ||
  'https://YOUR_WORKER_URL_HERE' // <- tras desplegar el Worker, pon aquí tu URL workers.dev o cámbialo en la UI

let NODE_URL = DEFAULT_NODE
export function setNodeUrl(url){ NODE_URL = url; try{ localStorage.setItem('NODE_URL', url) }catch{} }
export function getNodeUrl(){ return NODE_URL }
export function isMixedContent(url){ try{ return window.location.protocol === 'https:' && /^http:\/\//i.test(url) }catch{ return false } }
function normalizeAxios(err){ if (err?.response?.data) return new Error(typeof err.response.data==='string'? err.response.data : JSON.stringify(err.response.data)); return new Error(err?.message || 'Network error') }

export async function getBalance(address){
  try{
    const r = await axios.get(`${NODE_URL}/balance`, { params: { address } })
    return r.data
  }catch(e){ throw normalizeAxios(e) }
}

export async function sendTx({ fromPrivateKey, to, amount }){
  try{
    const r = await axios.post(`${NODE_URL}/send`, { from_private_key: fromPrivateKey, to, amount })
    return r.data
  }catch(e){ throw normalizeAxios(e) }
}

export async function mineOne(){
  try{
    const r = await axios.post(`${NODE_URL}/mine`)
    return r.data
  }catch(e1){
    try{
      const r2 = await axios.get(`${NODE_URL}/mine`)
      return r2.data
    }catch(e2){ throw normalizeAxios(e2) }
  }
}
