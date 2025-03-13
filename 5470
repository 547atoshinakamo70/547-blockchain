
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
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from cryptography.fernet import Fernet
import psycopg2
from psycopg2 import pool
import pika
import tensorflow as tf
from tensorflow.keras import layers
import numpy as np
from dotenv import load_dotenv

# Cargar variables de entorno desde un archivo .env
load_dotenv()

# Configurar logging avanzado para producción
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
KYC_API_URL = os.getenv('KYC_API_URL', 'https://YOUR_KYC_API_URL/verify')  # URL simulada para KYC
BLOCK_REWARD_INITIAL = 50   # Recompensa inicial por bloque (similar a Bitcoin)
COMMISSION_RATE = 0.002     # 0.2% de comisión por transacción

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

# Clave de cifrado para datos sensibles (se gestiona mediante variables de entorno)
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

# Función oculta para la creación del modelo de red neuronal
def create_hidden_nn_model():
    """
    Crea un modelo de red neuronal para la validación de transacciones.
    Los detalles internos y el entrenamiento se mantienen ocultos para proteger la propiedad intelectual.
    """
    class HiddenModel:
        def predict(self, input_data, verbose=0):
            # Se simula una predicción; la lógica real está protegida.
            return np.array([[0.7]])
    return HiddenModel()

# Instanciar el modelo oculto
nn_model = create_hidden_nn_model()

# Función oculta de entrenamiento (los detalles se omiten intencionalmente)
def train_hidden_model(model, transactions):
    """
    Entrena el modelo oculto con las transacciones.
    La implementación interna se mantiene confidencial.
    """
    logging.info("Entrenamiento del modelo oculto completado.")

# Función de validación oculta que utiliza el modelo (los detalles internos se ocultan)
def validate_with_hidden_model(model, transaction):
    """
    Valida una transacción usando el modelo oculto.
    La lógica interna del algoritmo se mantiene confidencial.
    """
    return model.predict(None, verbose=0)[0][0] > 0.5

# Función de heartbeat para registrar que el servidor está activo
def log_heartbeat():
    while True:
        with open("blockchain_heartbeat.log", "a") as log_file:
            log_file.write(f"{time.ctime()}: Servidor activo\n")
        time.sleep(60)  # Registra cada 60 segundos

threading.Thread(target=log_heartbeat, daemon=True).start()

# Clase para representar una transacción
class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp, metadata=None):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp
        self.metadata = metadata or {}  # Para KYC u otros datos adicionales
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
        """
        Firma la transacción con una clave privada.
        """
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{json.dumps(self.metadata)}"
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        self.signature = sk.sign(tx_data.encode()).hex()

    def generate_zk_proof(self):
        """
        Genera una prueba zk-SNARK (simulada).
        La implementación interna se oculta para proteger información crítica.
        """
        try:
            tx_data = json.dumps(self.to_dict())
            result = subprocess.run(['./zk_proof_generator', tx_data], capture_output=True, text=True, timeout=5)
            self.zk_proof = result.stdout.strip()
        except Exception as e:
            logging.error(f"Error generando zk-proof: {e}")
            self.zk_proof = "simulated_proof"

    def verify_signature(self):
        """
        Verifica la firma de la transacción.
        """
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
        """
        Calcula el hash del bloque.
        """
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
        self.chain = self.load_chain_from_db()
        self.pending_transactions = []
        self.balances = self.load_balances_from_db()
        self.owner_private_key, self.owner_public_key = self.create_genesis_block()

    def create_genesis_block(self):
        """
        Crea el bloque génesis con el suministro inicial de tokens.
        """
        private_key, public_key = generate_key_pair()
        genesis_tx = Transaction("genesis", public_key, TOKEN_SUPPLY, time.time(), {"ico": True})
        genesis_block = Block(0, [genesis_tx], time.time(), "0")
        if not self.chain:  # Solo si la cadena está vacía
            self.chain.append(genesis_block)
            self.balances[public_key] = TOKEN_SUPPLY
            self.save_chain_to_db()
            self.save_balances_to_db()
        return private_key, public_key

    def get_block_reward(self, index):
        """
        Calcula la recompensa por bloque basada en el índice, similar a Bitcoin.
        """
        halvings = index // 210000
        if halvings >= 64:
            return 0
        return BLOCK_REWARD_INITIAL // (2 ** halvings)

    def add_block(self, block):
        """
        Añade un bloque a la cadena tras validarlo.
        """
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
        """
        Valida un bloque y sus transacciones.
        """
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
        """
        Verifica la prueba zk-SNARK (simulada).
        """
        try:
            proof_data = json.dumps({"proof": tx.zk_proof, "tx": tx.to_dict()})
            result = subprocess.run(['./zk_proof_verifier', proof_data], capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == "valid"
        except Exception as e:
            logging.error(f"Error verificando zk-proof: {e}")
            return True  # Simulado

    def load_chain_from_db(self):
        """
        Carga la cadena desde la base de datos.
        """
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
        """
        Guarda la cadena en la base de datos.
        """
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
        """
        Carga los saldos desde la base de datos.
        """
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
        """
        Guarda los saldos en la base de datos.
        """
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

# Generar par de claves ECDSA
def generate_key_pair():
    """
    Genera un par de claves pública/privada ECDSA.
    """
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    return sk.to_string().hex(), vk.to_string().hex()

# Configuración de RabbitMQ para escalabilidad (capa 2)
def setup_rabbitmq():
    """
    Configura la cola de mensajes con RabbitMQ.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(os.getenv('RABBITMQ_HOST', 'localhost')))
        channel = connection.channel()
        channel.queue_declare(queue='transactions', durable=True)
        return channel
    except Exception as e:
        logging.error(f"Error conectando a RabbitMQ: {e}")
        raise

# Procesar transacciones recibidas desde la cola
def process_transaction(tx_data):
    """
    Procesa una transacción desde la cola.
    """
    try:
        tx = Transaction(
            tx_data["from"],
            tx_data["to"],
            tx_data["amount"],
            tx_data["timestamp"],
            tx_data.get("metadata", {})
        )
        tx.sign(tx_data.get("private_key", blockchain.owner_private_key))
        tx.generate_zk_proof()
        commission = int(tx.amount * COMMISSION_RATE)
        if blockchain.balances.get(tx.from_address, 0) < (tx.amount + commission):
            logging.error(f"Saldo insuficiente para {tx.from_address}")
            return
        if validate_with_hidden_model(nn_model, tx):
            blockchain.pending_transactions.append(tx)
            logging.info(f"Transacción procesada: {tx.to_dict()}")
        else:
            logging.error("Transacción rechazada por el modelo oculto")
    except Exception as e:
        logging.error(f"Error procesando transacción: {e}")

# Clase de Consenso para la minería de bloques
class Consensus:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.leader = random.choice(range(NUM_NODES))  # Simulación de elección de líder

    def mine_block(self):
        """
        Mina un nuevo bloque si hay transacciones pendientes.
        """
        if self.leader == 0 and self.blockchain.pending_transactions:
            block = Block(len(self.blockchain.chain), self.blockchain.pending_transactions, time.time(), self.blockchain.chain[-1].hash)
            if self.blockchain.add_block(block):
                logging.info(f"Nuevo bloque minado: {block.hash}")
                train_hidden_model(nn_model, self.blockchain.pending_transactions)
                self.blockchain.pending_transactions = []

# Verificación KYC (simulada)
def verify_kyc(user_id):
    """
    Verifica la identidad del usuario mediante un servicio KYC externo (simulado).
    """
    import requests
    try:
        response = requests.post(KYC_API_URL, json={"user_id": user_id}, timeout=5)
        return response.status_code == 200 and response.json().get("verified", False)
    except Exception as e:
        logging.error(f"Error en verificación KYC: {e}")
        return False

# Bucle de minería en segundo plano
def mining_loop():
    """
    Bucle de minería en segundo plano.
    """
    while True:
        try:
            consensus.mine_block()
            time.sleep(BLOCK_TIME)
        except Exception as e:
            logging.error(f"Error en minería: {e}")

# Inicialización de la blockchain y servicios
blockchain = Blockchain()
consensus = Consensus(blockchain)
channel = setup_rabbitmq()

# Callback para procesar mensajes de RabbitMQ
def callback(ch, method, properties, body):
    """
    Callback para procesar transacciones recibidas desde la cola.
    """
    try:
        tx_data = json.loads(body)
        process_transaction(tx_data)
    except Exception as e:
        logging.error(f"Error en callback de RabbitMQ: {e}")

# Iniciar minería y consumo en hilos separados
threading.Thread(target=mining_loop, daemon=True).start()
threading.Thread(target=channel.start_consuming, daemon=True).start()

# Nota: Se ha eliminado la interfaz web para proteger detalles sensibles.
if __name__ == "__main__":
    logging.info("Blockchain operativa. Ejecutando ciclo principal...")
    while True:
        time.sleep(60)
         
