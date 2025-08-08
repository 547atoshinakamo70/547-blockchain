import axios from 'axios'
let NODE_URL='http://127.0.0.1:15471'
export async function initApi(){ try{ const s=localStorage.getItem('NODE_URL'); if(s) NODE_URL=s }catch{} }
export function setNodeUrl(u){ NODE_URL=u; try{ localStorage.setItem('NODE_URL',u) }catch{} }
export function getNodeUrl(){ return NODE_URL }
export function isMixedContent(){ return false }
function norm(e){ if(e?.response?.data) return new Error(typeof e.response.data==='string'? e.response.data: JSON.stringify(e.response.data)); return new Error(e?.message||'Network') }
export async function getBalance(address){ try{ const r=await axios.get(`${NODE_URL}/balance`,{params:{address}}); return r.data }catch(e){ throw norm(e)}}
export async function sendTx({ fromPrivateKey,to,amount }){ try{ const r=await axios.post(`${NODE_URL}/send`,{ from_private_key: fromPrivateKey,to,amount}); return r.data }catch(e){ throw norm(e)}}
export async function mineOne(){ try{ const r=await axios.post(`${NODE_URL}/mine`); return r.data }catch(e1){ try{ const r2=await axios.get(`${NODE_URL}/mine`); return r2.data }catch(e2){ throw norm(e2)} } }
export async function getPeers(){ try{ const r=await axios.get(`${NODE_URL}/peers`); return r.data }catch(e){ throw norm(e)}}
