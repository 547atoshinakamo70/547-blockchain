import asyncio, json, time, socket, struct, random, contextlib
from typing import Dict, List, Tuple, Optional
import websockets
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx

P2P_PORT = 15470           # puerto P2P (como 8333 de Bitcoin)
RPC_PORT = 15471           # HTTP local para la PWA
SEEDS = [
    # DNS-like seeds o IPs de arranque (mete aquí nodos públicos si quieres)
    # ("seed1.5470blockchain.es", P2P_PORT),
]
ADDNODES = [
    # ("1.2.3.4", P2P_PORT),
]
NODE_VERSION = 1

# ---- estado
peers: List[Tuple[str,int]] = []
peer_conns: Dict[Tuple[str,int], asyncio.Task] = {}
subscribers: List[WebSocket] = []  # chat ws locales (PWA)
chat_bus: asyncio.Queue[str] = asyncio.Queue()

# ---- UPnP/NAT-PMP (best effort)
def try_upnp(port=P2P_PORT):
    try:
        import miniupnpc
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        upnp.addportmapping(port, 'TCP', upnp.lanaddr, port, '547 P2P', '')
        return True
    except Exception:
        return False

# ---- mensajes P2P simples
def pkt(cmd:str, payload:dict)->bytes:
    data = json.dumps({"cmd":cmd, "payload":payload}).encode()
    length = struct.pack("!I", len(data))
    return length + data

async def send_pkt(writer:asyncio.StreamWriter, cmd:str, **payload):
    writer.write(pkt(cmd, payload)); await writer.drain()

async def read_pkt(reader:asyncio.StreamReader)->dict:
    hdr = await reader.readexactly(4)
    ln = struct.unpack("!I", hdr)[0]
    data = await reader.readexactly(ln)
    return json.loads(data.decode())

# ---- manejo de un peer
async def handle_peer(host:str, port:int, reader:asyncio.StreamReader, writer:asyncio.StreamWriter):
    try:
        # handshake
        await send_pkt(writer, "version", version=NODE_VERSION, time=int(time.time()))
        msg = await read_pkt(reader)
        if msg.get("cmd") != "version":
            return
        await send_pkt(writer, "verack")
        # ciclo principal
        last_ping = time.time()
        while True:
            if time.time() - last_ping > 20:
                await send_pkt(writer, "ping", t=int(time.time()))
                last_ping = time.time()
            # lectura con timeout corto
            try:
                msg = await asyncio.wait_for(read_pkt(reader), timeout=5)
            except asyncio.TimeoutError:
                continue
            cmd = msg.get("cmd"); pl = msg.get("payload", {})
            if cmd == "verack":
                pass
            elif cmd == "ping":
                await send_pkt(writer, "pong", t=pl.get("t"))
            elif cmd == "addr":
                # descubrimiento
                for a in pl.get("addrs", []):
                    if isinstance(a, list) and len(a)==2:
                        ip, prt = a
                        if (ip, prt) not in peers and ip != "127.0.0.1":
                            peers.append((ip, prt))
            elif cmd == "chat":
                # retransmitir localmente y a otros peers
                await chat_bus.put(pl.get("msg",""))
                # no re-gossip infinito aquí por simplicidad
            elif cmd == "cj":  # coinjoin stub
                # TODO: coordinar sesiones minimalistas
                pass
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close(); await writer.wait_closed()
        peer_conns.pop((host,port), None)

# ---- dailer/acceptor
async def dial_peer(ip:str, port:int):
    if (ip,port) in peer_conns: return
    try:
        reader, writer = await asyncio.open_connection(ip, port)
    except Exception:
        return
    task = asyncio.create_task(handle_peer(ip, port, reader, writer))
    peer_conns[(ip,port)] = task

async def listen_peers():
    server = await asyncio.start_server(lambda r,w: handle_peer(w.get_extra_info('peername')[0], w.get_extra_info('peername')[1], r,w), "0.0.0.0", P2P_PORT)
    async with server:
        await server.serve_forever()

async def seed_bootstrap():
    # mete IPs fijas
    for ip, prt in ADDNODES:
        await dial_peer(ip, prt)

# ---- Chat broadcaster local
async def chat_local_broadcaster():
    while True:
        msg = await chat_bus.get()
        # a PWA
        dead=[]
        for ws in subscribers:
            try: await ws.send_text(msg)
            except Exception: dead.append(ws)
        for d in dead:
            with contextlib.suppress(ValueError): subscribers.remove(d)
        # gossip a peers abiertos
        for (ip,prt), task in list(peer_conns.items()):
            # para simplificar, reenviar chat como ping no implementamos aquí
            # (lo normal: guardar writer y enviar pkt("chat", msg=...))
            pass

# ---- HTTP local para PWA
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False,
)

@app.get("/peers")
def _peers():
    return [{"ip": ip, "port": prt} for (ip,prt) in peers] + [{"ip": ip, "port": prt} for (ip,prt) in peer_conns.keys()]

@app.websocket("/chat")
async def _chat(ws:WebSocket):
    await ws.accept()
    subscribers.append(ws)
    try:
        while True:
            msg = await ws.receive_text()
            await chat_bus.put(msg)
    except Exception:
        with contextlib.suppress(ValueError):
            subscribers.remove(ws)

# Pasarela a tu nodo local (RPC ya existente)
RPC_ORIGIN = "http://127.0.0.1:5000"  # tu My_blockchain.py
@app.get("/balance")
async def _balance(address:str):
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.get(RPC_ORIGIN+"/balance", params={"address": address})
        return r.json()
@app.post("/send")
async def _send(payload:dict):
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(RPC_ORIGIN+"/send", json=payload)
        return r.json()
@app.post("/mine")
async def _mine():
    async with httpx.AsyncClient(timeout=60) as cli:
        try:
            r = await cli.post(RPC_ORIGIN+"/mine", json={})
        except Exception:
            r = await cli.get(RPC_ORIGIN+"/mine")
        try:
            return r.json()
        except Exception:
            return {"text": r.text}

async def main():
    try_upnp(P2P_PORT)
    await seed_bootstrap()
    await asyncio.gather(
        listen_peers(),
        chat_local_broadcaster(),
    )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="127.0.0.1", port=RPC_PORT)
