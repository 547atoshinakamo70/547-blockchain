#!/usr/bin/env python3
from datetime import datetime
from typing import Union
import time
from http.server import HTTPServer
import threading
import os
import sys
from eth_keys import keys
from eth_utils import to_checksum_address
from urllib import parse
import sys
import time
import json
import socket
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
from datetime import datetime
import os

# --- Crypto & Signatures ---
try:
    from ecdsa import SigningKey, SECP256k1
    from eth_keys import keys
    from eth_utils import to_checksum_address
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
except ImportError:  # Provide minimal stubs if crypto libs are unavailable
    SigningKey = None
    SECP256k1 = None
    keys = None
    def to_checksum_address(val: bytes) -> str:
        return "0x" + val.hex()[-40:]
    class Fernet:
        @staticmethod
        def generate_key():
            return os.urandom(32)
        def __init__(self, key):
            self.key = key
        def encrypt(self, data: bytes) -> bytes:
            return data
        def decrypt(self, data: bytes) -> bytes:
            return data
    rsa = None
    serialization = None

# --- ZK Proofs (stub if unavailable) ---
try:
    from pysnark.runtime import snark, PrivVal
except ImportError:
    class DummySnark:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        @staticmethod
        def prove(): return b''
        @staticmethod
        def verify(proof, vk): return True
        @staticmethod
        def verkey(): return b''
    snark = DummySnark()
    class PrivVal:
        def __init__(self, val): self.val = val

# --- Ethereum / Web3 (optional stub) ---
from web3 import Web3
import os

# --- Configuración Ethereum (Infura + Clave Privada) ---
INFURA_URL = 'https://sepolia.infura.io/v3/'
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Verifica conexión
if not w3.is_connected():
    raise ConnectionError("❌ No se pudo conectar a Infura/Sepolia")

# Clave privada y cuenta
PRIVATE_KEY = ""
account = w3.eth.account.from_key(PRIVATE_KEY)
print(f"✅ Conectado como {account.address}")

# Dirección de tu contrato desplegado (¡reemplaza con la tuya real!)
CONTRACT_ADDRESS = ""

# --- ABI del contrato ---
CONTRACT_ABI = [

# --- DB & Env ---
try:
    import psycopg2
    from psycopg2 import pool
except ImportError:
    psycopg2 = None
    pool = None
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return None

# --- ML Anomaly & ZK Hybrid Validation ---
try:
    import numpy as np
except ImportError:
    np = None
try:
    import tensorflow as tf
    from tensorflow.keras import layers
except ImportError:
    tf = None
    layers = None

# --- Constants ---
BASE_UNIT = 10 ** 8        # smallest unit (like satoshi)
BLOCK_TIME = 10            # seconds per block
BLOCK_REWARD_INITIAL = int(0.0289 * BASE_UNIT)  # ~0.029 tokens per block
HALVING_INTERVAL = 210_000 # blocks per halving
COMMISSION_RATE = 0.002    # 0.2% per transaction
CHAIN_ID = 60              # Ethereum-style chain ID

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


from cryptography.fernet import Fernet

# — Carga y validación de FERNET_KEY con autocorrección —
FERNET_KEY = os.getenv("FERNET_KEY", "").strip()

# Si no existe o tiene longitud distinta de 44, lo regeneramos y guardamos en .env
if len(FERNET_KEY) != 44:
    print("¡¡ FERNET_KEY inválida o no configurada. Generando una nueva automáticamente... !!")
    # Genera una clave válida
    FERNET_KEY = Fernet.generate_key().decode()
    # Ruta al .env (se asume en el mismo directorio que este script)
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        # Leemos y reescribimos .env actualizando o añadiendo FERNET_KEY
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        with open(env_path, "w") as f:
            found = False
            for line in lines:
                if line.startswith("FERNET_KEY="):
                    f.write(f"FERNET_KEY={FERNET_KEY}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"\nFERNET_KEY={FERNET_KEY}\n")
        print(f"[AUTO] Nueva FERNET_KEY guardada en {env_path}")
    except Exception as e:
        print(f"⚠️ No he podido actualizar {env_path}: {e}")
    print(f"[AUTO] Usando FERNET_KEY: {FERNET_KEY}")

# Ahora sí intentamos crear el cipher
try:
    cipher = Fernet(FERNET_KEY.encode())
except Exception:
    print("Error crítico: la FERNET_KEY sigue siendo inválida.")
    sys.exit(1)
    # Eliminamos posibles comillas que hayas puesto en .env
FERNET_KEY = FERNET_KEY.strip()
if (FERNET_KEY.startswith('"') and FERNET_KEY.endswith('"')) or \
   (FERNET_KEY.startswith("'") and FERNET_KEY.endswith("'")):
    FERNET_KEY = FERNET_KEY[1:-1]

# Debug: muestro lo que realmente se cargó
print(f"[DEBUG] FERNET_KEY cargada (len={len(FERNET_KEY)}): {FERNET_KEY}")

# Intentamos crear el cipher con la clave limpia
try:
    cipher = Fernet(FERNET_KEY.encode())
except Exception:
    print("Error: FERNET_KEY inválida. Debe ser 32 bytes base64 url-safe.")
    print("Genera una clave válida así:")
    print("  python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    sys.exit(1)

import json
from pathlib import Path

# ─── Almacenamiento “file-based” ────────────────────────────────────
DATA_DIR      = Path(__file__).parent
CHAIN_FILE    = DATA_DIR / "chain_data.json"
BALANCES_FILE = DATA_DIR / "balances.json"
# Ya no usamos psycopg2 ni pool de Postgres
DB_POOL = None

# --- Utility ---
def keccak(x: bytes) -> bytes:
    return hashlib.new('sha3_256', x).digest()

def derive_address_from_pubkey(pubkey_bytes: bytes) -> str:
    return to_checksum_address(keccak(pubkey_bytes)[-20:])

# --- HD Wallet fallback ---
class HDWallet:
    def __init__(self, mnemonic=None, passphrase=""):
        pass
    def derive_account(self, idx=0):
        priv = os.urandom(32)
        priv_hex = priv.hex()
        if keys:
            addr = keys.PrivateKey(priv).public_key.to_checksum_address()
        else:
            addr = derive_address_from_pubkey(hashlib.sha256(priv).digest())
        return {"private_key": priv_hex, "address": addr}
# --- Autoencoder persistence ---
AUTOENCODER_FILE = "autoencoder.weights.h5"
if tf and layers:
    autoencoder = tf.keras.Sequential([
        layers.Dense(32, activation='relu', input_shape=(4,)),
        layers.Dense(16, activation='relu'),
        layers.Dense(32, activation='relu'),
        layers.Dense(4, activation='sigmoid'),
    ])
    autoencoder.compile(optimizer='adam', loss='mse')
else:
    class DummyAE:
        def predict(self, x, verbose=0):
            return x
        def fit(self, *a, **k):
            pass
        def save_weights(self, f):
            pass
        def load_weights(self, f):
            pass
    autoencoder = DummyAE()

def load_or_train_autoencoder():
    if not tf or not np:
        return
    if os.path.exists(AUTOENCODER_FILE):
        autoencoder.load_weights(AUTOENCODER_FILE)
        logging.info("Loaded autoencoder weights.")
    else:
        data = np.random.rand(1000,4)
        autoencoder.fit(data, data, epochs=50, batch_size=32, verbose=0)
        autoencoder.save_weights(AUTOENCODER_FILE)
        logging.info("Trained and saved new autoencoder.")

def update_model(new_data):
    if tf and np:
        autoencoder.fit(new_data, new_data, epochs=20, batch_size=16)
        autoencoder.save_weights(AUTOENCODER_FILE)
        logging.info("Autoencoder updated with new data.")

load_or_train_autoencoder()

# --- Anomaly detection & zk proof ---
ANOMALY_LOG = "anomalies.log"
ANOMALY_THRESHOLD = 0.1

def validate_with_hidden_model(tx, zk_vk=None) -> bool:
    if not tf or not np:
        return True

    # Preparar características básicas
    f1 = f2 = 0.0
    try:
        f1 = float(int(tx.from_address[:8], 16))
        f2 = float(int(tx.to_address[:8], 16))
    except:
        pass

    # --- NORMALIZACIÓN AQUI ---
    # Convertimos satoshis a “número de monedas” y escalamos
    f3 = float(tx.amount) / BASE_UNIT           # ahora en unidades de moneda
    # Tomamos días desde el 13 Sep 2020 (1600000000s), escalando a ~[0,10]
    f4 = (tx.timestamp - 1_600_000_000) / 86_400
    # -------------------------

    inp = np.array([[f1, f2, f3, f4]])
    rec = autoencoder.predict(inp, verbose=0)
    mse = float(np.mean((inp - rec) ** 2))

    if mse >= ANOMALY_THRESHOLD:
        with open(ANOMALY_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} ANOMALY tx={tx.to_dict()} mse={mse}\n")
        return False

    # ZK‑SNARK proof (si aplica)
    if getattr(tx, "proof", None) is not None:
        if not zk_vk or not tx.verify(zk_vk):
            return False

    return True

# --- Key gen ---
def generate_rsa_key_pair():
    if rsa and serialization:
        priv = rsa.generate_private_key(65537,2048)
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        pub_pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        return priv_pem, pub_pem
    # fallback simple keys
    priv = os.urandom(32).hex()
    pub = hashlib.sha256(bytes.fromhex(priv)).hexdigest()
    return priv, pub

# --- Transaction classes ---

# Constantes
CHAIN_ID   = 60
BASE_UNIT  = 10 ** 8

class Transaction:
    def __init__(
        self,
        from_address: str,
        to_address: str,
        amount: int,
        timestamp: float = None,
        nonce: int = 0,
        data: Union[bytes,str] = b"",
        chain_id: int = CHAIN_ID,
        signature: str = None
    ):
        self.from_address = from_address
        self.to_address   = to_address
        self.amount       = int(amount)
        # si no pasas timestamp, usa la hora actual
        self.timestamp    = timestamp if timestamp is not None else datetime.now().timestamp()
        self.nonce        = nonce
        # data puede venir como bytes o como hex-string
        if isinstance(data, bytes):
            self.data = data
        elif isinstance(data, str) and data:
            # si es hex, conviértelo
            self.data = bytes.fromhex(data)
        else:
            self.data = b""
        self.chain_id    = chain_id
        self.signature   = signature

    def to_dict(self) -> dict:
        return {
            "from": self.from_address,
            "to": self.to_address,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "data": self.data.hex(),
            "chain_id": self.chain_id,
            "signature": self.signature
        }
        def _hash(self) -> bytes:
        return keccak(
            self.from_address.encode()
            + self.to_address.encode()
            + self.amount.to_bytes(8, "big")
            + self.nonce.to_bytes(8, "big")
            + self.chain_id.to_bytes(2, "big")
            + self.data
        )

    def sign(self, private_key_hex: str):
        """
        Sign the transaction by prefixing+hashing internally.
        """
        msg = self._hash()
        priv = keys.PrivateKey(bytes.fromhex(private_key_hex))
        sig = priv.sign_msg(msg)
        self.signature = sig.to_bytes().hex()

    def verify_signature(self) -> bool:
        """
        Verify the signature against the same prefix+hash flow.
        """
        if not self.signature:
            return False

        msg = self._hash()
        sig = keys.Signature(bytes.fromhex(self.signature))

        # Recover using the same sign_msg prefix logic
        pub = sig.recover_public_key_from_msg(msg)
        derived = pub.to_checksum_address()

        # Finally verify with the matching verify_msg call
        return derived == self.from_address and pub.verify_msg(msg, sig)
class ShieldedTransaction:
    def __init__(self, commitment, proof):
        self.commitment, self.proof = commitment, proof
    @staticmethod
    def create(amount,priv_val,pub_key,vk):
        with snark: assert amount>=0
        return ShieldedTransaction(b"...", snark.prove())
    def verify(self,vk): return snark.verify(self.proof,vk)

# ─── 1. Cargar la clave de wallet para minería ────────────────────────
KEY_FILE = os.path.expanduser("~/.mywallet_key")
if not os.path.exists(KEY_FILE):
    print(f"ERROR: no existe tu keyfile de wallet en {KEY_FILE}")
    sys.exit(1)

with open(KEY_FILE, "r") as f:
    miner_priv_hex = f.read().strip()
miner_priv = keys.PrivateKey(bytes.fromhex(miner_priv_hex))
MINER_ADDRESS = to_checksum_address(miner_priv.public_key.to_bytes()[-20:])

# … luego sigue la definición de tus constantes y utilidades …
# --- Blockchain & P2P ---
class Blockchain:
    def __init__(self):
        self.chain = []
        self.balances = {}
        self.nonces = {}
        self.pending_transactions = []
        self.zk_vk = None

        # ← Inicializamos aquí la dirección del minero
        from eth_keys import keys
        from eth_utils import to_checksum_address
        # MINER_PRIV_HEX debe venir de ~/.mywallet_key, igual que en wallet.py
        from pathlib import Path
        key_file = Path.home() / ".mywallet_key"
        miner_priv_hex = key_file.read_text().strip()
        miner_priv = keys.PrivateKey(bytes.fromhex(miner_priv_hex))
        self.miner_address = to_checksum_address(miner_priv.public_key.to_bytes()[-20:])

        # Carga desde los archivos JSON
        self._load_state()

    def _load_state(self):
        # 1) Cargo la cadena desde disco (si existe) o creo el génesis
        if CHAIN_FILE.exists():
            with open(CHAIN_FILE, "r") as f:
                raw = json.load(f)
            self.chain = [Block(**blk) for blk in raw]
        else:
            self.create_genesis_block()

        # 2) Reinicio balances y nonces
        self.balances = {}
        self.nonces   = {}

        # 3) Reproduzco TODAS las transacciones históricas
        for block in self.chain:
            for tx in block.transactions:
                # A) Si viene de "system" o "genesis", es reward o génesis
                if tx.from_address in ("system", "genesis"):
                    self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
                else:
                    # comisión al minero
                    fee = int(tx.amount * COMMISSION_RATE)
                    # débito al emisor
                    self.balances[tx.from_address] = self.balances.get(tx.from_address, 0) - (tx.amount + fee)
                    # abono al receptor
                    self.balances[tx.to_address]   = self.balances.get(tx.to_address, 0) + tx.amount
                    # abono de la comisión
                    self.balances[self.miner_address] = self.balances.get(self.miner_address, 0) + fee
                # B) actualizo nonce por dirección
                self.nonces[tx.from_address] = self.nonces.get(tx.from_address, 0) + 1
                 4) (Opcional) persisto balances si quieres
        # self._save_state()

    def _save_state(self):
        # Guarda la cadena
        with open(CHAIN_FILE, "w") as f:
            json.dump([blk.to_dict() for blk in self.chain], f, indent=2)
        # Guarda los balances
        with open(BALANCES_FILE, "w") as f:
            json.dump(self.balances, f, indent=2)

    def create_genesis_block(self):
        tx = Transaction("system", self.miner_address, 0, nonce=0)
        blk = Block(0, [tx], "0")
        self.chain    = [blk]
        self.balances = {self.miner_address: 0}
        self.nonces   = {self.miner_address: 0}
        self._save_state()

    def get_block_reward(self,idx):
        h=idx//210000
        return BLOCK_REWARD_INITIAL//(2**h) if h<64 else 0

    def proof_of_work(self,block,difficulty=4):
        target='0'*difficulty
        while not block.hash.startswith(target):
            block.nonce+=1
            block.hash=block.calculate_hash()
        return block

def is_valid_transaction(self, tx):
        # Allow system & genesis transactions
        if tx.from_address in ("system", "genesis"):
            return True

        # 1) Signature check
        if not tx.verify_signature():
            return False

        # 2) Anomaly/ZK only for shielded transactions
        if isinstance(tx, ShieldedTransaction):
            if not validate_with_hidden_model(tx, self.zk_vk):
                return False

        # 3) Balance & nonce
        fee = int(tx.amount * COMMISSION_RATE)
        if self.balances.get(tx.from_address, 0) < tx.amount + fee:
            return False
        if tx.nonce != self.nonces.get(tx.from_address, 0):
            return False

        return True


    def is_valid_block(self,blk):
        if not self.chain: return True
        prev=self.chain[-1]
        return (blk.previous_hash==prev.hash and
                blk.hash==blk.calculate_hash() and
                blk.hash.startswith('0000'))

    def add_block(self, blk):
        # …validaciones…
        self.chain.append(blk)
        # actualizar balances y nonces…
        self._save_state()

    def mine_block(self):
        prev = self.chain[-1]
        idx  = prev.index + 1
        reward_tx = Transaction("system", self.miner_address, self.get_block_reward(idx), nonce=0)
        block_txs = [reward_tx] + self.pending_transactions
        self.pending_transactions = []
        new_block = Block(idx, block_txs, prev.hash)
        new_block = self.proof_of_work(new_block)
        self.add_block(new_block)
        logging.info(f"Mined block {new_block.index} → reward to {self.miner_address}")
# --- Block ---
class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, nonce=0, hash=None):
        self.index = index
        # Reconstruimos cada tx a mano
        mapped = []
        for t in transactions:
            if isinstance(t, dict):
                # extraemos y renombramos campos
                from_addr = t["from"]
                to_addr   = t["to"]
                amount    = t["amount"]
                ts        = t.get("timestamp")
                nonce_tx  = t.get("nonce", 0)
                # data viene en hex; si es cadena vacía, lo dejamos b""
                data_hex  = t.get("data") or ""
                data_b    = bytes.fromhex(data_hex) if data_hex else b""
                chain_id  = t.get("chain_id", CHAIN_ID)
                # creamos la instancia
                tx = Transaction(
                    from_addr,
                    to_addr,
                    amount,
                    timestamp=ts,
                    nonce=nonce_tx,
                    data=data_b,
                    chain_id=chain_id
                )
                # restauramos la firma (hex string)
                sig_hex = t.get("signature")
                if sig_hex:
                    tx.signature = sig_hex
                mapped.append(tx)
            else:
                mapped.append(t)
        self.transactions   = mapped

        self.previous_hash  = previous_hash
        self.timestamp      = timestamp or time.time()
        self.nonce          = nonce
        self.hash           = hash or self.calculate_hash()

    def calculate_hash(self):
        data=json.dumps({
            'index':self.index,
            'transactions':[t.to_dict() for t in self.transactions],
            'timestamp':self.timestamp,
            'previous_hash':self.previous_hash,
            'nonce':self.nonce
        },sort_keys=True).encode()
        return hashlib.sha3_256(data).hexdigest()

 def to_dict(self):
        return {
            'index':self.index,
            'transactions':[t.to_dict() for t in self.transactions],
            'timestamp':self.timestamp,
            'previous_hash':self.previous_hash,
            'nonce':self.nonce,
            'hash':self.hash
        }

# --- En el handler HTTP que usas en run_node() ---

class BlockchainHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1) Balance
        if self.path.startswith("/balance"):
            qs   = parse.urlparse(self.path).query
            addr = parse.parse_qs(qs).get("address", [""])[0]
            bal  = blockchain.balances.get(addr, 0)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"address": addr, "balance": bal}).encode())
            return

        # 2) Chain
        if self.path == "/chain":
            chain_data = [b.to_dict() for b in blockchain.chain]
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"chain": chain_data}).encode())
            return

        self.send_response(404)
        self.end_headers()

def do_POST(self):
        # 3) Broadcast tx
        if self.path == "/tx":
            length = int(self.headers.get("Content-Length",0))
            data   = json.loads(self.rfile.read(length))
            # Asegúrate de que las claves del JSON coinciden con los parámetros de Transaction:
            #   from_address, to_address, amount, nonce, chain_id, data, signature
            tx = Transaction(
                from_address = data["from_address"],
                to_address   = data["to_address"],
                amount       = data["amount"],
                nonce        = data["nonce"],
                chain_id     = data.get("chain_id", CHAIN_ID),
                data         = bytes.fromhex(data.get("data","")) if data.get("data") else b""
            )
            tx.signature = data.get("signature")
            if blockchain.is_valid_transaction(tx):
                blockchain.pending_transactions.append(tx)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"status":"invalid tx"}')
            return

        self.send_response(404)
        self.end_headers()

# --- Tests ---
def run_tests():
    wallet=HDWallet()
    bc=Blockchain(DB_POOL)
    bc.create_genesis_block()
    # genesis
    assert len(bc.chain)==1
    assert bc.balances[bc.owner_pub]==0

    acct = wallet.derive_account()
    bc.balances[acct['address']] = 100 * BASE_UNIT

    tx = Transaction(acct['address'], bc.owner_pub, 10 * BASE_UNIT, nonce=0)
    tx.sign(acct['private_key'])
    assert tx.verify_signature()

    # insufficient balance
    poor=wallet.derive_account()
    bc.balances[poor['address']]=5*BASE_UNIT
    tx_bad=Transaction(poor['address'],bc.owner_pub,10*BASE_UNIT,nonce=0)
    tx_bad.sign(poor['private_key'])
    assert not bc.is_valid_transaction(tx_bad)

    # nonce enforcement
    rich=wallet.derive_account()
    bc.balances[rich['address']]=100*BASE_UNIT
    # correct nonce=0
    tx1=Transaction(rich['address'],bc.owner_pub,10*BASE_UNIT,nonce=0)
    tx1.sign(rich['private_key'])
    bc.pending_transactions=[tx1]
    bc.mine_block()
    # now nonce for rich is 1
    tx2=Transaction(rich['address'],bc.owner_pub,5*BASE_UNIT,nonce=0)
    tx2.sign(rich['private_key'])
    assert not bc.is_valid_transaction(tx2)
    tx3=Transaction(rich['address'],bc.owner_pub,5*BASE_UNIT,nonce=1)
    tx3.sign(rich['private_key'])
    assert bc.is_valid_transaction(tx3)

    # proof-of-work check
    blk=Block(5,[tx3],bc.chain[-1].hash)
    assert not blk.hash.startswith('0000')
    solved=bc.proof_of_work(blk)
    assert solved.hash.startswith('0000')
    assert bc.is_valid_block(solved)

    print("All tests passed.")

import time
from http.server import HTTPServer
import threading

if __name__ == "__main__":
    # 1) Inicializa la blockchain (carga de JSON o génesis)
    bc = Blockchain()
    if not bc.chain:
        bc.create_genesis_block()

    # 2) Ponemos la instancia global para el handler HTTP
    blockchain = bc

    # 3) Arrancamos el servidor HTTP en el puerto 5000
    server = HTTPServer(("", 5000), BlockchainHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("✅ HTTP RPC listening on port 5000")

    # 4) Arrancamos la minería continua
    print("🔨 Starting continuous mining (CTRL+C to stop)...")
    try:
        while True:
            bc.mine_block()
            time.sleep(BLOCK_TIME)
    except KeyboardInterrupt:
        print("\n⛔ Mining stopped by user")
        server.shutdown()
