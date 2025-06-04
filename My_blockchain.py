#!/usr/bin/env python3
import sys
import time
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
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
load_dotenv()
BLOCK_TIME = 10
BLOCK_REWARD_INITIAL = 50
COMMISSION_RATE = 0.002

db_pool = psycopg2.pool.ThreadedConnectionPool(1, 50, dbname="blockchain", user="postgres",
                                               password=os.getenv('DB_PASSWORD'), host="localhost", port="5432")
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

# Autoencoder
autoencoder = tf.keras.Sequential([
    layers.Dense(32, activation='relu', input_shape=(4,)),
    layers.Dense(16, activation='relu'),
    layers.Dense(32, activation='relu'),
    layers.Dense(4, activation='sigmoid')
])
autoencoder.compile(optimizer='adam', loss='mse')
normal_transactions = np.random.rand(1000, 4)
autoencoder.fit(normal_transactions, normal_transactions, epochs=50, batch_size=32, verbose=0)

def validate_with_hidden_model(autoencoder, transaction):
    feature1 = float(int(transaction.from_address[:8], 16)) if transaction.from_address != "genesis" else 0.0
    feature2 = float(int(transaction.to_address[:8], 16)) if transaction.to_address != "genesis" else 0.0
    feature3 = float(transaction.amount)
    feature4 = float(transaction.timestamp)
    input_data = np.array([[feature1, feature2, feature3, feature4]])
    reconstructed = autoencoder.predict(input_data, verbose=0)
    mse = np.mean(np.square(input_data - reconstructed))
    return mse < 0.1

def generate_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,
                                            format=serialization.PrivateFormat.PKCS8,
                                            encryption_algorithm=serialization.NoEncryption()).decode('utf-8')
    public_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM,
                                         format=serialization.PublicFormat.SubjectPublicKeyInfo).decode('utf-8')
    return private_pem, public_pem

class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp=None):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp if timestamp else datetime.now().timestamp()
        self.signature = None

    def to_dict(self):
        return {"from": self.from_address, "to": self.to_address, "amount": self.amount,
                "timestamp": self.timestamp, "signature": self.signature}

    def sign(self, private_key):
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}"
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        self.signature = sk.sign(tx_data.encode()).hex()

    def verify_signature(self):
        if not self.signature:
            return False
        tx_data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}"
        vk = VerifyingKey.from_string(bytes.fromhex(self.from_address), curve=SECP256k1)
        return vk.verify(bytes.fromhex(self.signature), tx_data.encode())

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
        return hashlib.sha3_256(json.dumps(block_data, sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return {"index": self.index, "transactions": [t.to_dict() for t in self.transactions],
                "timestamp": self.timestamp, "previous_hash": self.previous_hash, "nonce": self.nonce, "hash": self.hash}

class P2PNetwork:
    def __init__(self, host='localhost', port=6000):
        self.host = host
        self.port = port
        self.peers = []
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

    def start(self):
        threading.Thread(target=self.accept_connections, daemon=True).start()
        print(f"Escuchando conexiones P2P en {self.host}:{self.port}")

    def accept_connections(self):
        while self.running:
            client, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_peer, args=(client,), daemon=True).start()
            self.peers.append(client)
            print(f"Nuevo peer conectado: {addr}")

    def handle_peer(self, client):
        while self.running:
            try:
                data = client.recv(4096).decode()
                if data:
                    self.process_message(data, client)
            except:
                self.peers.remove(client)
                client.close()
                break

    def process_message(self, data, client):
        message = json.loads(data)
        if message["type"] == "GET_CHAIN":
            chain_data = [block.to_dict() for block in blockchain.chain]
            client.send(json.dumps({"type": "CHAIN", "data": chain_data}).encode())
        elif message["type"] == "NEW_BLOCK":
            block_data = message["data"]
            transactions = [Transaction(**tx) for tx in block_data["transactions"]]
            block = Block(block_data["index"], transactions, block_data["previous_hash"],
                          block_data["timestamp"], block_data["nonce"])
            if blockchain.is_valid_block(block):
                blockchain.add_block(block)
                self.broadcast({"type": "NEW_BLOCK", "data": block_data})
        elif message["type"] == "NEW_TX":
            tx = Transaction(**message["data"])
            if blockchain.is_valid_transaction(tx):
                blockchain.pending_transactions.append(tx)
                self.broadcast({"type": "NEW_TX", "data": message["data"]})

    def broadcast(self, message):
        for peer in self.peers:
            try:
                peer.send(json.dumps(message).encode())
            except:
                self.peers.remove(peer)

    def connect_to_peer(self, peer_host, peer_port):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((peer_host, peer_port))
        self.peers.append(client)
        threading.Thread(target=self.handle_peer, args=(client,), daemon=True).start()
        client.send(json.dumps({"type": "GET_CHAIN"}).encode())

class Blockchain:
    def __init__(self):
        self.owner_private_key, self.owner_public_key = generate_key_pair()
        self.chain = self.load_chain_from_db()
        self.balances = self.load_balances_from_db()
        self.pending_transactions = []
        self.network = P2PNetwork()
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
                    block_data = json.loads(row[0])
                    transactions = [Transaction(**t) for t in block_data["transactions"]]
                    block = Block(block_data["index"], transactions, block_data["previous_hash"],
                                  block_data["timestamp"], block_data["nonce"])
                    chain.append(block)
                return chain
        finally:
            db_pool.putconn(conn)

    def load_balances_from_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT address, balance FROM balances")
                return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            db_pool.putconn(conn)

    def save_chain_to_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for block in self.chain:
                    cur.execute("INSERT INTO blockchain (index, data) VALUES (%s, %s) ON CONFLICT (index) DO UPDATE SET data = %s",
                                (block.index, json.dumps(block.to_dict()), json.dumps(block.to_dict())))
                conn.commit()
        finally:
            db_pool.putconn(conn)

    def save_balances_to_db(self):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for address, balance in self.balances.items():
                    cur.execute("INSERT INTO balances (address, balance) VALUES (%s, %s) ON CONFLICT (address) DO UPDATE SET balance = %s",
                                (address, balance, balance))
                conn.commit()
        finally:
            db_pool.putconn(conn)

    def get_block_reward(self, index):
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

    def is_valid_block(self, block):
        prev_block = self.chain[-1]
        if block.previous_hash != prev_block.hash or block.hash != block.calculate_hash():
            return False
        if block.hash[:4] != '0000':
            return False
        return True

    def is_valid_transaction(self, tx):
        if not tx.verify_signature() or not validate_with_hidden_model(autoencoder, tx):
            return False
        if tx.from_address != "system" and tx.from_address != "genesis":
            if self.balances.get(tx.from_address, 0) < tx.amount * (1 + COMMISSION_RATE):
                return False
        return True

    def mine_block(self):
        previous_block = self.chain[-1]
        new_index = previous_block.index + 1
        reward_tx = Transaction("system", self.owner_public_key, self.get_block_reward(new_index))
        transactions = [reward_tx] + self.pending_transactions
        self.pending_transactions.clear()
        new_block = Block(new_index, transactions, previous_block.hash)
        new_block = self.proof_of_work(new_block)
        self.add_block(new_block)
        self.network.broadcast({"type": "NEW_BLOCK", "data": new_block.to_dict()})
        print(f"Bloque minado: Índice={new_block.index}, Hash={new_block.hash}")

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
    print(f"Iniciando servidor HTTP en el puerto {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    blockchain = Blockchain()
    blockchain.network.start()
    server_thread = threading.Thread(target=run_server, kwargs={"port": 5000}, daemon=True)
    server_thread.start()
    print("Servidor HTTP y P2P iniciados")

    # Conectar a otro nodo (ejemplo)
    blockchain.network.connect_to_peer("localhost", 6001)

    while True:
        try:
            blockchain.mine_block()
            time.sleep(BLOCK_TIME)
        except Exception as e:
            print(f"Error en el minado: {e}")
            time.sleep(BLOCK_TIME)
