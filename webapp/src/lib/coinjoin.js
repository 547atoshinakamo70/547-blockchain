import axios from 'axios'
import { getNodeUrl } from './api'
export async function cjCreateSession({ amount, participants }){ return (await axios.post(`${getNodeUrl()}/coinjoin/session`, { amount, participants })).data }
export async function cjRegister({ sessionId, utxos, changeAddress, outputAddress }){ return (await axios.post(`${getNodeUrl()}/coinjoin/register`, { sessionId, utxos, changeAddress, outputAddress })).data }
export async function cjGetTx(sessionId){ return (await axios.get(`${getNodeUrl()}/coinjoin/psbt`, { params:{ sessionId } })).data }
export async function cjSubmitSig({ sessionId, signatures }){ return (await axios.post(`${getNodeUrl()}/coinjoin/sign`, { sessionId, signatures })).data }
export async function cjBroadcast(sessionId){ return (await axios.post(`${getNodeUrl()}/coinjoin/broadcast`, { sessionId })).data }
