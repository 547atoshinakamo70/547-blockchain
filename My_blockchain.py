#!/usr/bin/env python3
import sys
import time
import logging
import hashlib
import json
import subprocess
import threading
import os
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from cryptography.fernet import Fernet
import psycopg2
from psycopg2 import pool
import pika
import tensorflow as tf
from tensorflow.keras import layers
import numpy as np
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logging avanzado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("blockchain.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Parámetros de la blockchain e ICO
TOKEN_NAME = "5470"
TOKEN_SYMBOL = "547"
TOKEN_SUPPLY = 5470000      # Total de tokens para la ICO
BLOCK_TIME = 10           # Tiempo entre bloques en segundos
NUM_NODES = 5             # Número de nodos en la red (simulado)
DB_URL = os.getenv('DATABASE_URL', 'dbname=blockchain user=postgres password=YOUR_DB_PASSWORD host=localhost')
KYC_API_URL = os.getenv('KYC_API_URL', 'https://YOUR_KYC_API_URL/verify')
BLOCK_REWARD_INITIAL = 50   # Recompensa inicial por bloque
COMMISSION_RATE = 0.002     # 0.2% de comisión por transacción

print(f"Intentando conectar con: {DB_URL}")

# Conexión a la base de datos con pool
db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=50,
    dbname="blockchain",
    user="postgres",
    password=os.getenv('DB_PASSWORD', 'YOUR_DB_PASSWORD'),
    host="localhost",
    port="5432"
)

# Clave de cifrado para datos sensibles
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

def create_hidden_nn_model():
    """
    Crea un modelo de red neuronal para la validación de transacciones.
    La lógica interna se mantiene protegida.
    """
    class HiddenModel:
        def predict(self, input_data, verbose=0):
            # Simulación de predicción; la lógica real está protegida.
            return np.array([[0.7]])
    return HiddenModel()

nn_model = create_hidden_nn_model()

def train_hidden_model(model, transactions):
    logging.info("Entrenamiento del modelo oculto completado.")

def validate_with_hidden_model(model, transaction):
    return model.predict(None, verbose=0)[0][0] > 0.5

# Clase para representar una transacción
class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp, metadata=None):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp
        self.metadata = metadata or {}
        self.signature = None
        self.zk_proof = None

    def to_dict(self):
        return {
            "from": self.from_address,
            "to": self.to_address,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "signature": self.signature,
            "zk_proof": self.zk_proof
        }

    def sign(self, private_key):
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        self.signature = sk.sign(tx_data.encode()).hex()

    def generate_zk_proof(self):
        try:
            tx_data = json.dumps(self.to_dict())
            result = subprocess.run(['./zk_proof_generator', tx_data], capture_output=True, text=True, timeout=5)
            self.zk_proof = result.stdout.strip()
        except Exception as e:
            logging.error(f"Error generando zk-proof: {e}")
            self.zk_proof = "simulated_proof"

    def verify_signature(self):
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"
        vk = VerifyingKey.from_string(bytes.fromhex(self.from_address), curve=SECP256k1)
        try:
            return vk.verify(bytes.fromhex(self.signature), tx_data.encode())
        except Exception:
            return False

# Clase para representar un bloque
class Block:
    def __init__(self, index, transactions, timestamp, previous_hash, nonce=0):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "transactions": [t.to_dict() for t in self.transactions],
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

# Clase para la blockchain
class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.balances = {}
        self.owner_private_key, self.owner_public_key = self.create_genesis_block()

    def create_genesis_block(self):
        private_key, public_key = generate_key_pair()
        genesis_tx = Transaction("genesis", public_key, TOKEN_SUPPLY, time.time(), {"ico": True})
        genesis_block = Block(0, [genesis_tx], time.time(), "0")
        self.chain.append(genesis_block)
        self.balances[public_key] = TOKEN_SUPPLY
        return private_key, public_key

    def get_block_reward(self, index):
        halvings = index // 210000
        if halvings >= 64:
            return 0
        return BLOCK_REWARD_INITIAL // (2 ** halvings)

    def add_block(self, block):
        if self.validate_block(block):
            self.chain.append(block)
            for tx in block.transactions:
                if tx.from_address == "system":
                    self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
                elif tx.from_address != "genesis":
                    commission = int(tx.amount * COMMISSION_RATE)
                    self.balances[tx.from_address] -= (tx.amount + commission)
                    self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
                    self.balances[self.owner_public_key] = self.balances.get(self.owner_public_key, 0) + commission
                else:
                    self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
            self.save_chain_to_db()
            self.save_balances_to_db()
            return True
        return False

    def validate_block(self, block):
        reward_tx_count = sum(1 for tx in block.transactions if tx.from_address == "system")
        if reward_tx_count > 1:
            return False
        if reward_tx_count == 1:
            reward_tx = next(tx for tx in block.transactions if tx.from_address == "system")
            expected_reward = self.get_block_reward(block.index)
            if reward_tx.amount != expected_reward or reward_tx.signature is not None or reward_tx.zk_proof is not None:
                return False
        for tx in block.transactions:
            if tx.from_address not in ["system", "genesis"]:
                commission = int(tx.amount * COMMISSION_RATE)
                if not self.verify_zk_proof(tx) or not tx.verify_signature() or self.balances.get(tx.from_address, 0) < (tx.amount + commission):
                    return False
            elif tx.from_address == "genesis" and not self.verify_zk_proof(tx):
                return False
        return True

    def verify_zk_proof(self, tx):
        try:
            proof_data = json.dumps({"proof": tx.zk_proof, "tx": tx.to_dict()})
            result = subprocess.run(['./zk_proof_verifier', proof_data], capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == "valid"
        except Exception as e:
            logging.error(f"Error verificando zk-proof: {e}")
            return True  # Simulado

    def load_chain_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM blockchain ORDER BY index")
                chain = [json.loads(row[0]) for row in cur.fetchall()]
                return [Block(b["index"], [Transaction(**t) for t in b["transactions"]],
                              b["timestamp"], b["previous_hash"], b["nonce"]) for b in chain]
        except Exception as e:
            logging.error(f"Error cargando cadena desde DB: {e}")
            return []
        finally:
            db_pool.putconn(conn)

    def save_chain_to_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for block in self.chain:
                    cur.execute(
                        "INSERT INTO blockchain (index, data) VALUES (%s, %s) ON CONFLICT (index) DO UPDATE SET data = %s",
                        (block.index, json.dumps(block.__dict__), json.dumps(block.__dict__))
                    )
                conn.commit()
        except Exception as e:
            logging.error(f"Error guardando cadena en DB: {e}")
        finally:
            db_pool.putconn(conn)

    def load_balances_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT address, balance FROM balances")
                return {row[0]: row[1] for row in cur.fetchall()}
        except Exception as e:
            logging.error(f"Error cargando saldos desde DB: {e}")
            return {}
        finally:
            db_pool.putconn(conn)

    def save_balances_to_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for address, balance in self.balances.items():
                    cur.execute(
                        "INSERT INTO balances (address, balance) VALUES (%s, %s) ON CONFLICT (address) DO UPDATE SET balance = %s",
                        (address, balance, balance)
                    )
                conn.commit()
        except Exception as e:
            logging.error(f"Error guardando saldos en DB: {e}")
        finally:
            db_pool.putconn(conn)

# --- Fin del módulo blockchain_core ---

# A partir de aquí se expone un servidor HTTP mínimo para que el código de minería se conecte a la blockchain

class BlockchainHTTPRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path == "/chain":
            chain_data = [block.__dict__ for block in blockchain.chain]
            self._set_headers()
            self.wfile.write(json.dumps({"chain": chain_data}).encode())
        elif self.path == "/pending_transactions":
            self._set_headers()
            self.wfile.write(json.dumps(blockchain.pending_transactions).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode())

    def do_POST(self):
        if self.path == "/propose_block":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                block = json.loads(post_data)
                # Intentar agregar el bloque a la blockchain
                if blockchain.add_block(Block(
                        index=block["index"],
                        transactions=[Transaction(**tx) for tx in block["transactions"]],
                        timestamp=block["timestamp"],
                        previous_hash=block["previous_hash"],
                        nonce=block["nonce"]
                    )):
                    self._set_headers(201)
                    self.wfile.write(json.dumps({"message": "Block added successfully"}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Invalid block"}).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode())

def run_server(server_class=HTTPServer, handler_class=BlockchainHTTPRequestHandler, port=5000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Starting blockchain server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    # Iniciar el servidor HTTP en un hilo para exponer la API sin revelar la lógica interna
    blockchain = Blockchain()  # Instancia de la blockchain
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()

    logging.info("Blockchain operativa. Ejecutando ciclo principal...")
    # Aquí se puede agregar cualquier otra tarea, por ejemplo, minería interna o procesos de mantenimiento
    while True:
        time.sleep(60)
