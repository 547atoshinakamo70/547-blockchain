#!/usr/bin/env python3
import sys
import time
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
from datetime import datetime
import os

# --- Crypto & Signatures ---
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from eth_keys import keys
from eth_utils import to_checksum_address
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# --- ZK Proofs ---
from pysnark.runtime import snark, PrivVal

# --- Smart Contracts / EVM ---
from eth.chains.base import MiningChain
from eth.vm.forks.berlin import BerlinVM
from web3 import Web3

# --- DB & Environment ---
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# --- ML Anomaly & ZK Hybrid Validation ---
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers

# --- Constants ---
BLOCK_TIME = 10
BLOCK_REWARD_INITIAL = 50
COMMISSION_RATE = 0.002
BASE_UNIT = 10 ** 8        # smallest unit (like satoshi)
CHAIN_ID = 60              # Ethereum-style chain ID

# --- Load .env & Initialize ---
load_dotenv()
FERNET_KEY = os.getenv('FERNET_KEY', Fernet.generate_key().decode()).encode()
cipher = Fernet(FERNET_KEY)

# DB pool
DB_POOL = psycopg2.pool.ThreadedConnectionPool(
    1, 50,
    dbname=os.getenv('DB_NAME', 'blockchain'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', '5432')
)

# Ethereum provider
w3 = Web3(Web3.HTTPProvider(os.getenv('ETH_RPC', 'https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID')))
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '0xYourDeployedContractAddress')
CONTRACT_ABI = json.loads(os.getenv('CONTRACT_ABI', '[]'))

# --- Utility Functions ---
def keccak(x: bytes) -> bytes:
    return hashlib.new('sha3_256', x).digest()


def derive_address_from_pubkey(pubkey_bytes: bytes) -> str:
    addr = keccak(pubkey_bytes)[-20:]
    return to_checksum_address(addr)

# --- HD Wallet (fallback, no bip_utils) ---
class HDWallet:
    """Simple HDWallet fallback: generates a random secp256k1 keypair"""
    def __init__(self, mnemonic: str = None, passphrase: str = ""):
        pass  # mnemonic ignored in fallback

    def derive_account(self, account_index: int = 0) -> dict:
        priv_bytes = os.urandom(32)
        priv_hex = priv_bytes.hex()
        priv_key = keys.PrivateKey(priv_bytes)
        addr = priv_key.public_key.to_checksum_address()
        return {"private_key": priv_hex, "address": addr}

# --- Autoencoder + ZK-based Validation ---
autoencoder = tf.keras.Sequential([
    layers.Dense(32, activation='relu', input_shape=(4,)),
    layers.Dense(16, activation='relu'),
    layers.Dense(32, activation='relu'),
    layers.Dense(4, activation='sigmoid')
])
autoencoder.compile(optimizer='adam', loss='mse')
normal_data = np.random.rand(1000, 4)
autoencoder.fit(normal_data, normal_data, epochs=10, batch_size=32, verbose=0)

def validate_with_hidden_model(tx, zk_vk: bytes = None) -> bool:
    # 1) Autoencoder anomaly detection
    try:
        f1 = float(int(tx.from_address[:8], 16))
        f2 = float(int(tx.to_address[:8], 16))
    except:
        f1 = f2 = 0.0
    f3 = float(tx.amount)
    f4 = float(tx.timestamp)
    inp = np.array([[f1, f2, f3, f4]])
    rec = autoencoder.predict(inp, verbose=0)
    mse = np.mean(np.square(inp - rec))
    if mse >= 0.1:
        return False
    # 2) If there's a ZK proof, verify it
    if hasattr(tx, 'proof') and tx.proof is not None:
        if not zk_vk:
            print("ZK VK not set, failing proof validation")
            return False
        if not tx.verify(zk_vk):
            return False
    return True

# --- Key Generation ---
def generate_rsa_key_pair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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

# --- Transaction Classes ---
class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp=None, nonce=0, data=b"", chain_id=CHAIN_ID):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp or datetime.now().timestamp()
        self.nonce = nonce
        self.data = data
        self.chain_id = chain_id
        self.signature = None

    def to_dict(self):
        return {
            "from": self.from_address,
            "to": self.to_address,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "data": self.data.hex() if isinstance(self.data, bytes) else None,
            "chain_id": self.chain_id,
            "signature": self.signature
        }

    def sign(self, private_key_hex: str):
        msg = self._hash()
        sk = keys.PrivateKey(bytes.fromhex(private_key_hex))
        sig = sk.sign_msg(msg)
        self.signature = sig.to_bytes().hex()

    def _hash(self) -> bytes:
        payload = (
            self.from_address.encode() +
            self.to_address.encode() +
            int(self.amount).to_bytes(8, 'big') +
            int(self.nonce).to_bytes(8, 'big') +
            int(self.chain_id).to_bytes(2, 'big') +
            (self.data if isinstance(self.data, bytes) else b"")
        )
        return keccak(payload)

    def verify_signature(self) -> bool:
        if not self.signature:
            return False
        sig = keys.Signature(bytes.fromhex(self.signature))
        pub = sig.recover_public_key_from_msg(self._hash())
        addr = derive_address_from_pubkey(pub.to_bytes())
        return addr == self.from_address and pub.verify_msg(self._hash(), sig)

class ShieldedTransaction:
    def __init__(self, commitment: bytes, proof: bytes):
        self.commitment = commitment
        self.proof = proof

    @staticmethod
    def create(amount: int, priv_val: PrivVal, pub_key: bytes, vk: bytes):
        with snark:
            assert amount >= 0
        proof = snark.prove()
        commitment = b"..."
        return ShieldedTransaction(commitment, proof)

    def verify(self, vk: bytes) -> bool:
        return snark.verify(self.proof, vk)

# --- Blockchain with EVM & P2P ---
class Blockchain(MiningChain):
    def __init__(self, db_pool):
        super().__init__(genesis_params={}, genesis_state={})
        self.db_pool = db_pool
        self.chain = []
        self.balances = {}
        self.nonces = {}
        self.pending_transactions = []
        self.owner_priv, self.owner_pub = generate_rsa_key_pair()
        self.zk_vk = None
        self.network = None
        self.load_state()

    def load_state(self):
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT index, data FROM blockchain ORDER BY index")
                rows = cur.fetchall()
                if not rows:
                    return
                for idx, raw in rows:
                    blk = Block(**raw)
                    self.chain.append(blk)
                cur.execute("SELECT address, balance FROM balances")
                for addr, bal in cur.fetchall():
                    self.balances[addr] = bal
        finally:
            self.db_pool.putconn(conn)

    def save_state(self):
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for blk in self.chain:
                    cur.execute(
                        "INSERT INTO blockchain (index, data) VALUES (%s, %s) ON CONFLICT (index) DO UPDATE SET data = %s", 
                        (blk.index, json.dumps(blk.to_dict()), json.dumps(blk.to_dict()))
                    )
                for addr, bal in self.balances.items():
                    cur.execute(
                        "INSERT INTO balances (address, balance) VALUES (%s, %s) ON CONFLICT (address) DO UPDATE SET balance = %s",
                        (addr, bal, bal)
                    )
                conn.commit()
        finally:
            self.db_pool.putconn(conn)

    def create_genesis_block(self):
        tx = Transaction("genesis", self.owner_pub, 0)
        blk = Block(0, [tx], "0")
        self.chain = [blk]
        self.balances[self.owner_pub] = 0
        self.save_state()

    def get_block_reward(self, idx):
        halvings = idx // 210000
        return BLOCK_REWARD_INITIAL // (2 ** halvings) if halvings < 64 else 0

    def proof_of_work(self, block, difficulty=4):
        target = '0' * difficulty
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block

    def add_block(self, block):
        if not self.is_valid_block(block):
            return False
        self.chain.append(block)
        for tx in block.transactions:
            if tx.from_address == 'system':
                self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
            elif tx.from_address != 'genesis':
                fee = int(tx.amount * COMMISSION_RATE)
                self.balances[tx.from_address] -= (tx.amount + fee)
                self.balances[tx.to_address] = self.balances.get(tx.to_address, 0) + tx.amount
                self.balances[self.owner_pub] += fee
        self.save_state()
        return True

    def is_valid_block(self, block):
        prev = self.chain[-1]
        return (
            block.previous_hash == prev.hash and
            block.hash == block.calculate_hash() and
            block.hash.startswith('0000')
        )

    def is_valid_transaction(self, tx):
        return validate_with_hidden_model(tx, self.zk_vk)

    def mine_block(self):
        prev = self.chain[-1]
        idx = prev.index + 1
        reward = Transaction('system', self.owner_pub, self.get_block_reward(idx))
        txs = [reward] + self.pending_transactions
        self.pending_transactions = []
        blk = Block(idx, txs, prev.hash)
        blk = self.proof_of_work(blk)
        self.add_block(blk)
        print(f"Mined block {blk.index}: {blk.hash}")

# --- Block class for reconstruction and tests ---
class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, nonce=0, hash=None):
        self.index = index
        self.transactions = [Transaction(**t) if isinstance(t, dict) else t for t in transactions]
        self.previous_hash = previous_hash
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.hash = hash or self.calculate_hash()

    def calculate_hash(self):
        data = json.dumps({
            'index': self.index,
            'transactions': [t.to_dict() for t in self.transactions],
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha3_256(data).hexdigest()

    def to_dict(self):
        return {
            'index': self.index,
            'transactions': [t.to_dict() for t in self.transactions],
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash
        }

# --- Basic Tests ---
def run_tests():
    # Test genesis creation
    bc = Blockchain(DB_POOL)
    bc.create_genesis_block()
    assert len(bc.chain) == 1, "Genesis block not created"
    assert bc.balances[bc.owner_pub] == 0, "Owner balance not zero"

    # Test transaction signing and validation
    wallet = HDWallet()
    acct = wallet.derive_account()
    bc.balances[acct['address']] = 100 * BASE_UNIT
    tx = Transaction(acct['address'], bc.owner_pub, 10 * BASE_UNIT, nonce=0)
    tx.sign(acct['private_key'])
    assert tx.verify_signature(), "Signature verification failed"
    assert bc.is_valid_transaction(tx), "Valid transaction marked invalid"

    print("All tests passed.")

if __name__ == '__main__':
    run_tests()
    print("Tests completed successfully.")
