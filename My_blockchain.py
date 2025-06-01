#!/usr/bin/env python3
import sys
import time
import logging
import hashlib
import json
import threading
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from cryptography.fernet import Fernet
import psycopg2
from psycopg2 import pool
import tensorflow as tf
from tensorflow.keras import layers
import numpy as np
from dotenv import load_dotenv
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Configuración inicial
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("blockchain.log"), logging.StreamHandler(sys.stdout)])

TOKEN_NAME = "5470"
TOKEN_SYMBOL = "547"
TOKEN_SUPPLY = 21000000
BLOCK_TIME = 10
BLOCK_REWARD_INITIAL = 50
COMMISSION_RATE = 0.002

# Conexión a la base de datos
db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=50, dbname="blockchain", user="postgres",
                                               password=os.getenv('DB_PASSWORD', 'YOUR_DB_PASSWORD'), host="localhost", port="5432")
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

# Modelo de Autoencoder para validación de transacciones
def create_autoencoder(input_dim=4):
    input_layer = layers.Input(shape=(input_dim,))
    encoded = layers.Dense(32, activation='relu')(input_layer)
    encoded = layers.Dense(16, activation='relu')(encoded)
    decoded = layers.Dense(32, activation='relu')(encoded)
    decoded = layers.Dense(input_dim, activation='sigmoid')(decoded)
    autoencoder = tf.keras.Model(input_layer, decoded)
    autoencoder.compile(optimizer='adam', loss='mse')
    return autoencoder

autoencoder = create_autoencoder()
normal_transactions = np.random.rand(1000, 4)  # Datos simulados
autoencoder.fit(normal_transactions, normal_transactions, epochs=50, batch_size=32, verbose=0)

def validate_with_hidden_model(autoencoder, transaction):
    try:
        feature1 = float(int(transaction.from_address[:8], 16)) if transaction.from_address != "genesis" else 0.0
    except Exception:
        feature1 = 0.0
    try:
        feature2 = float(int(transaction.to_address[:8], 16)) if transaction.to_address != "genesis" else 0.0
    except Exception:
        feature2 = 0.0
    feature3 = float(transaction.amount)
    feature4 = float(transaction.timestamp)
    input_data = np.array([[feature1, feature2, feature3, feature4]])
    reconstructed = autoencoder.predict(input_data, verbose=0)
    mse = np.mean(np.square(input_data - reconstructed))
    return mse < 0.1  # Umbral ajustable

# Función para generar par de claves (movida fuera de Block)
def generate_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_pem, public_pem
# Clase Transaction
class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp=None, metadata=None):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp if timestamp else datetime.now().timestamp()
        self.metadata = metadata or {}
        self.signature = None
        self.zk_proof = None

    def to_dict(self):
        encrypted_metadata = cipher.encrypt(json.dumps(self.metadata).encode()).decode()
        return {"from": self.from_address, "to": self.to_address, "amount": self.amount,
                "timestamp": self.timestamp, "metadata": encrypted_metadata, "signature": self.signature, "zk_proof": self.zk_proof}

    def sign(self, private_key):
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        self.signature = sk.sign(tx_data.encode()).hex()

    def generate_zk_proof(self):
        self.zk_proof = "simulated_proof"  # Placeholder para ZKP real

    def verify_signature(self):
        if not self.signature:
            return False
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"
        vk = VerifyingKey.from_string(bytes.fromhex(self.from_address), curve=SECP256k1)
        try:
            return vk.verify(bytes.fromhex(self.signature), tx_data.encode())
        except Exception:
            return False

# Clase Block
class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, nonce=0):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = timestamp if timestamp else time.time()
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_data = {"index": self.index, "transactions": [t.to_dict() for t in self.transactions],
                      "timestamp": self.timestamp, "previous_hash": self.previous_hash, "nonce": self.nonce}
        block_string = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha3_256(block_string).hexdigest()

    def to_dict(self):
        return {"index": self.index, "transactions": [t.to_dict() for t in self.transactions],
                "timestamp": self.timestamp, "previous_hash": self.previous_hash, "nonce": self.nonce, "hash": self.hash}

# Clase Blockchain corregida
class Blockchain:
    def __init__(self):
        # Generamos las claves del propietario
        self.owner_private_key, self.owner_public_key = generate_key_pair()
        self.chain = self.load_chain_from_db()
        self.balances = self.load_balances_from_db()
        self.pending_transactions = []  # Inicializamos las transacciones pendientes
        if not self.chain:
            self.create_genesis_block()

    def create_genesis_block(self):
        genesis_tx = Transaction("genesis", self.owner_public_key, 0)
        genesis_block = Block(0, [genesis_tx], "0")
        self.chain.append(genesis_block)
        self.balances[self.owner_public_key] = 0
        self.save_chain_to_db()
        self.save_balances_to_db()

    def load_chain_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM blockchain ORDER BY index")
                rows = cur.fetchall()
                if not rows:
                    return []
                chain = []
                for row in rows:
                    block_data = row[0]
                    if isinstance(block_data, str):
                        block_data = json.loads(block_data)
                    transactions = [Transaction(**t) for t in block_data["transactions"]]
                    block = Block(
                        block_data["index"],
                        transactions,
                        block_data["previous_hash"],
                        block_data["timestamp"]
                    )
                    chain.append(block)
                print(f"Cargados {len(chain)} bloques desde la base de datos.")
                return chain
        except Exception as e:
            print(f"Error cargando cadena desde DB: {e}")
            return []
        finally:
            db_pool.putconn(conn)

    def load_balances_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT address, balance FROM balances")
                return {row[0]: row[1] for row in cur.fetchall()}
        except Exception as e:
            print(f"Error cargando saldos desde DB: {e}")
            return {}
        finally:
            db_pool.putconn(conn)

    def save_chain_to_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for block in self.chain:
                    cur.execute(
                        "INSERT INTO blockchain (index, data) VALUES (%s, %s) ON CONFLICT (index) DO UPDATE SET data = %s",
                        (block.index, json.dumps(block.to_dict()), json.dumps(block.to_dict()))
                    )
                conn.commit()
        except Exception as e:
            print(f"Error guardando cadena en DB: {e}")
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
            print(f"Error guardando saldos en DB: {e}")
        finally:
            db_pool.putconn(conn)

    def get_block_reward(self, index):
        # Recompensa inicial de 50, se reduce a la mitad cada 210,000 bloques
        halvings = index // 210000
        if halvings >= 64:
            return 0
        return BLOCK_REWARD_INITIAL // (2 ** halvings)

    def proof_of_work(self, block, difficulty=4):
        target = '0' * difficulty
        while block.hash[:difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block

    def add_block(self, block):
        # Por simplicidad, asumimos que el bloque es válido
        self.chain.append(block)
        for tx in block.transactions:
            if tx.from_address == "system":
                self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
            elif tx.from_address != "genesis":
                commission = int(tx.amount * COMMISSION_RATE)
                self.balances[tx.from_address] -= (tx.amount + commission)
                self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
                self.balances[self.owner_public_key] += commission
            else:
                self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
        self.save_chain_to_db()
        self.save_balances_to_db()

# Servidor HTTP
class BlockchainHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/chain":
            chain_data = [block.to_dict() for block in blockchain.chain]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"chain": chain_data}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, BlockchainHTTPRequestHandler)
    print(f"Iniciando servidor en el puerto {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    blockchain = Blockchain()
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    print("Servidor iniciado")

    while True:
        try:
            previous_block = blockchain.chain[-1]
            new_index = previous_block.index + 1
            new_timestamp = time.time()
            reward_tx = Transaction(
                "system",
                blockchain.owner_public_key,
                blockchain.get_block_reward(new_index),
                new_timestamp,
                {"type": "mining_reward"}
            )
            transactions = [reward_tx] + blockchain.pending_transactions
            blockchain.pending_transactions.clear()
            new_block = Block(new_index, transactions, previous_block.hash, new_timestamp)
            new_block = blockchain.proof_of_work(new_block)
            blockchain.add_block(new_block)
            print(f"Bloque minado: Índice={new_block.index}, Hash={new_block.hash}")
            time.sleep(BLOCK_TIME)
        except Exception as e:
            print(f"Error en el minado: {e}")
            time.sleep(BLOCK_TIME)
