import axios from 'axios'
import { getNodeUrl } from './api'

export async function cjCreateSession({ amount, participants }){
  const r = await axios.post(`${getNodeUrl()}/coinjoin/session`, { amount, participants })
  return r.data
}
export async function cjRegister({ sessionId, utxos, changeAddress, outputAddress }){
  const r = await axios.post(`${getNodeUrl()}/coinjoin/register`, { sessionId, utxos, changeAddress, outputAddress })
  return r.data
}
export async function cjGetTx(sessionId){
  const r = await axios.get(`${getNodeUrl()}/coinjoin/psbt`, { params: { sessionId } })
  return r.data
}
export async function cjSubmitSig({ sessionId, signatures }){
  const r = await axios.post(`${getNodeUrl()}/coinjoin/sign`, { sessionId, signatures })
  return r.data
}
export async function cjBroadcast(sessionId){
  const r = await axios.post(`${getNodeUrl()}/coinjoin/broadcast`, { sessionId })
  return r.data
}
