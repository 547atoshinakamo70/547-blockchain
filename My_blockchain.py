#!/usr/bin/env python3
import sys
import time
import logging
import hashlib
import json
import subprocess
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
import requests
import ssl
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Deshabilitar la GPU para evitar errores de CUDA
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

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
TOKEN_SUPPLY = 21000000       # Oferta total (se minará gradualmente)
BLOCK_TIME = 10              # Tiempo entre bloques en segundos
NUM_NODES = 5                # Número de nodos en la red (simulado)
DB_URL = os.getenv('DATABASE_URL', 'dbname=blockchain user=postgres password=YOUR_DB_PASSWORD host=localhost')
BLOCK_REWARD_INITIAL = 50    # Recompensa inicial por bloque
COMMISSION_RATE = 0.002      # 0.2% de comisión por transacción

print(f"Intentando conectar con: {DB_URL}")

# Conexión a la base de datos con pool para alta concurrencia
db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=50,
    dbname="blockchain",
    user="postgres",
    password=os.getenv('DB_PASSWORD', 'YOUR_DB_PASSWORD'),
    host="localhost",
    port="5432"
)

# Clave de cifrado para datos sensibles (usamos Fernet)
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

###############################################
# Función para generar par de claves (RSA)
###############################################
def generate_key_pair():
    """
    Genera un par de claves utilizando RSA.
    Retorna la clave privada y la clave pública en formato PEM (cadena de texto).
    """
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

###############################################
# Sección de IA: Modelo para validación de transacciones
###############################################
def create_nn_model():
    """
    Crea un modelo de red neuronal con TensorFlow para validar transacciones.
    Recibe un vector de 4 características y devuelve un valor entre 0 y 1.
    """
    model = tf.keras.Sequential([
        layers.Input(shape=(4,)),
        layers.Dense(64, activation='relu'),
        layers.Dense(32, activation='relu'),
        layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy')
    return model

# Instanciar el modelo de IA
nn_model = create_nn_model()

def validate_with_hidden_model(model, transaction):
    """
    Valida una transacción usando el modelo de IA.
    Características: from_address (8 primeros caracteres), to_address, amount, timestamp.
    Retorna True si la predicción es mayor a 0.5.
    """
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
    prediction = model.predict(input_data, verbose=0)
    return prediction[0][0] > 0.5

###############################################
# Clase para representar una transacción
###############################################
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
        return {
            "from": self.from_address,
            "to": self.to_address,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "metadata": encrypted_metadata,
            "signature": self.signature,
            "zk_proof": self.zk_proof
        }

    def sign(self, private_key):
        tx_data = self._get_tx_data()
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        self.signature = sk.sign(tx_data.encode()).hex()

    def generate_zk_proof(self):
        try:
            tx_data = json.dumps(self.to_dict())
            result = subprocess.run(['./zk_proof_verifier', tx_data], capture_output=True, text=True, timeout=5)
            self.zk_proof = result.stdout.strip()
        except subprocess.TimeoutExpired:
            logging.error("Timeout generando zk-proof")
            self.zk_proof = "timeout_error"
        except Exception as e:
            logging.error(f"Error generando zk-proof: {e}")
            self.zk_proof = "simulated_proof"

    def verify_signature(self):
        if not self.signature:
            return False
        tx_data = self._get_tx_data()
        vk = VerifyingKey.from_string(bytes.fromhex(self.from_address), curve=SECP256k1)
        try:
            return vk.verify(bytes.fromhex(self.signature), tx_data.encode())
        except Exception:
            return False

    def _get_tx_data(self):
        return f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"

###############################################
# Clase para representar un bloque
###############################################
class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, nonce=0):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = timestamp if timestamp else time.time()
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_data = {
            "index": self.index,
            "transactions": [t.to_dict() for t in self.transactions],
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }
        block_string = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "transactions": [t.to_dict() for t in self.transactions],
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }

###############################################
# Clase para la blockchain
###############################################
class Blockchain:
    def __init__(self):
        self.chain = self.load_chain_from_db()
        self.balances = self.load_balances_from_db()
        self.pending_transactions = []
        self.peers = []
        self.commissions_collected = 0

        if not self.chain:
            self.owner_private_key, self.owner_public_key = self.create_genesis_block()
        else:
            print("Blockchain ya inicializada. Dirección propietaria:", self.owner_public_key)

    def load_chain_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM blockchain ORDER BY index")
                chain = [json.loads(row[0]) for row in cur.fetchall()]
                return [Block(b["index"], [Transaction(**t) for t in b["transactions"]],
                              b["previous_hash"], b["timestamp"], b["nonce"]) for b in chain]
        except Exception as e:
            logging.error(f"Error cargando cadena desde DB: {e}")
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
            logging.errorgraphics(f"Error cargando saldos desde DB: {e}")
            return {}
        finally:
            db_pool.putconn(conn)

    def create_genesis_block(self):
        private_key, public_key = generate_key_pair()
        genesis_tx = Transaction("genesis", public_key, 0, time.time(), {"ico": False})
        genesis_block = Block(0, [genesis_tx], "0")
        self.chain.append(genesis_block)
        self.balances[public_key] = 0
        logging.info(f"Clave privada del propietario: {private_key}")
        logging.info(f"Clave pública del propietario: {public_key}")
        return private_key, public_key

    def proof_of_work(self, block, difficulty=4):
        target = '0' * difficulty
        while block.hash[:difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block

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
                    self.commissions_collected += commission
                else:
                    self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
            self.save_chain_to_db()
            self.save_balances_to_db()
            self.broadcast_block(block)
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

    def get_block_reward(self, index):
        halvings = index // 210000
        if halvings >= 64:
            return 0
        return BLOCK_REWARD_INITIAL // (2 ** halvings)

    def verify_zk_proof(self, tx):
        try:
            proof_data = json.dumps({"proof": tx.zk_proof, "tx": tx.to_dict()})
            result = subprocess.run(['./zk_proof_verifier', proof_data], capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == "valid"
        except Exception as e:
            logging.error(f"Error verificando zk-proof: {e}")
            return True  # Simulado

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
            logging.error(f"Error guardando cadena en DB: {e}")
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

    def broadcast_block(self, block):
        for peer in self.peers:
            try:
                url = f"{peer}/propose_block"
                headers = {'Content-Type': 'application/json'}
                data = json.dumps(block.to_dict())
                response = requests.post(url, headers=headers, data=data, timeout=5)
                if response.status_code == 201:
                    logging.info(f"Bloque difundido a {peer}")
                else:
                    logging.error(f"Error difundiendo bloque a {peer}: {response.text}")
            except Exception as e:
                logging.error(f"Excepción al difundir bloque a {peer}: {e}")

    def add_peer(self, peer_url):
        if peer_url not in self.peers:
            self.peers.append(peer_url)
            logging.info(f"Nuevo peer agregado: {peer_url}")

    def get_peers(self):
        return self.peers

###############################################
# Servidor HTTP para la blockchain
###############################################
class BlockchainHTTPRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path == "/chain":
            chain_data = [block.to_dict() for block in blockchain.chain]
            self._set_headers()
            self.wfile.write(json.dumps({"chain": chain_data}).encode())
        elif self.path == "/pending_transactions":
            self._set_headers()
            self.wfile.write(json.dumps(blockchain.pending_transactions).encode())
        elif self.path == "/peers":
            self._set_headers()
            self.wfile.write(json.dumps({"peers": blockchain.get_peers()}).encode())
        elif self.path.startswith("/balance"):
            try:
                address = self.path.split("?address=")[1]
                balance = blockchain.balances.get(address, 0)
                self._set_headers()
                self.wfile.write(json.dumps({"address": address, "balance": balance}).encode())
            except IndexError:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Address parameter missing"}).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode())

    def do_POST(self):
        if self.path == "/propose_block":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                block_data = json.loads(post_data)
                block = Block(
                    block_data["index"],
                    [Transaction(**tx) for tx in block_data["transactions"]],
                    block_data["previous_hash"],
                    block_data["timestamp"],
                    block_data["nonce"]
                )
                if blockchain.add_block(block):
                    self._set_headers(201)
                    self.wfile.write(json.dumps({"message": "Block added successfully"}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Invalid block"}).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/register_peer":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                peer_url = data.get("peer")
                if peer_url:
                    blockchain.add_peer(peer_url)
                    self._set_headers(201)
                    self.wfile.write(json.dumps({"message": "Peer registered successfully"}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Missing peer URL"}).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode())

def run_server(server_class=HTTPServer, handler_class=BlockchainHTTPRequestHandler, port=5000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    logging.info(f"Starting blockchain server on port {port} with HTTPS...")
    httpd.serve_forever()

###############################################
# Ejecución principal
###############################################
if __name__ == "__main__":
    blockchain = Blockchain()
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()

    logging.info("Blockchain operativa. Iniciando ciclo de minado...")

    while True:
        try:
            previous_block = blockchain.chain[-1]
            new_index = previous_block.index + 1
            new_timestamp = time.time()

            if not blockchain.owner_public_key:
                logging.error("Clave pública del propietario no definida.")
                time.sleep(BLOCK_TIME)
                continue

            reward_tx = Transaction(
                from_address="system",
                to_address=blockchain.owner_public_key,
                amount=blockchain.get_block_reward(new_index),
                timestamp=new_timestamp,
                metadata={"type": "mining_reward"}
            )

            transactions = [reward_tx]
            if blockchain.pending_transactions:
                transactions.extend(blockchain.pending_transactions)
                blockchain.pending_transactions.clear()

            new_block = Block(new_index, transactions, previous_block.hash, new_timestamp)
            new_block = blockchain.proof_of_work(new_block)  # Aplicar PoW

            if blockchain.add_block(new_block):
                num_user_txs = len(new_block.transactions) - 1
                formatted_time = datetime.fromtimestamp(new_block.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                logging.info(
                    f"Bloque minado en {formatted_time}: "
                    f"Índice={new_block.index}, Hash={new_block.hash}, "
                    f"Transacciones de Usuarios={num_user_txs}, Recompensa={reward_tx.amount} {TOKEN_SYMBOL}"
                )
            else:
                logging.warning(f"No se pudo añadir el bloque {new_index}.")

            time.sleep(BLOCK_TIME)

        except Exception as e:
            logging.error(f"Error en el ciclo de minado: {e}")
            time.sleep(BLOCK_TIME)
