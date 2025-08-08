import asyncio, json, time, socket, struct, contextlib
from typing import Dict, List, Tuple
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, httpx, asyncio, struct, json, time

P2P_PORT=15470; RPC_PORT=15471; RPC_ORIGIN="http://127.0.0.1:5000"
peers=[]; subscribers=[]

def try_upnp():
    try:
        import miniupnpc
        up = miniupnpc.UPnP(); up.discoverdelay=200; up.discover(); up.selectigd()
        up.addportmapping(P2P_PORT,'TCP',up.lanaddr,P2P_PORT,'547 P2P','')
    except Exception: pass

async def p2p_listener():
    server = await asyncio.start_server(lambda r,w: None, "0.0.0.0", P2P_PORT)
    async with server: await server.serve_forever()

app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/peers")
def _peers():
    return peers

@app.websocket("/chat")
async def _chat(ws:WebSocket):
    await ws.accept(); subscribers.append(ws)
    try:
        while True:
            msg = await ws.receive_text()
            for c in list(subscribers):
                try: await c.send_text(msg)
                except Exception: pass
    finally:
        with contextlib.suppress(ValueError): subscribers.remove(ws)

@app.get("/balance")
async def _balance(address:str):
    async with httpx.AsyncClient(timeout=30) as c: r=await c.get(RPC_ORIGIN+"/balance",params={"address":address}); return r.json()

@app.post("/send")
async def _send(payload:dict):
    async with httpx.AsyncClient(timeout=60) as c: r=await c.post(RPC_ORIGIN+"/send",json=payload); return r.json()

@app.post("/mine")
async def _mine():
    async with httpx.AsyncClient(timeout=60) as c:
        try: r=await c.post(RPC_ORIGIN+"/mine",json={})
        except Exception: r=await c.get(RPC_ORIGIN+"/mine")
        try: return r.json()
        except Exception: return {"text": r.text}

if __name__=="__main__":
    try_upnp()
    loop=asyncio.get_event_loop()
    loop.create_task(p2p_listener())
    uvicorn.run(app,host="127.0.0.1",port=RPC_PORT)
