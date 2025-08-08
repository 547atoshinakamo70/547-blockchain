import axios from 'axios'
const DEFAULT_NODE = (typeof window !== 'undefined' && localStorage.getItem('NODE_URL')) || 'http://localhost:5000'
let NODE_URL = DEFAULT_NODE
export function setNodeUrl(url){ NODE_URL = url; try{ localStorage.setItem('NODE_URL', url) }catch{} }
export function getNodeUrl(){ return NODE_URL }
export async function getBalance(address){ const r = await axios.get(`${NODE_URL}/balance`, { params: { address } }); return r.data }
export async function sendTx({ fromPrivateKey, to, amount }){ const r = await axios.post(`${NODE_URL}/send`, { from_private_key: fromPrivateKey, to, amount }); return r.data }
export async function mineOne(){ const r = await axios.post(`${NODE_URL}/mine`); return r.data }
