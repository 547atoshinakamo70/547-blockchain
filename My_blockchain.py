#!/usr/bin/env python3
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
from ecdsa import SigningKey, SECP256k1
from eth_keys import keys
from eth_utils import to_checksum_address
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

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
try:
    from web3 import Web3
    _rpc = os.getenv('ETH_RPC')
    w3 = Web3(Web3.HTTPProvider(_rpc)) if _rpc else None
except ImportError:
    Web3 = None
    w3 = None

# --- DB & Env ---
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
BASE_UNIT = 10 ** 8        # satoshi-like
CHAIN_ID = 60              # Ethereum

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# --- Load .env & require FERNET_KEY ---
load_dotenv()
FERNET_KEY = os.getenv('FERNET_KEY')
if not FERNET_KEY:
    FERNET_KEY = Fernet.generate_key().decode()
    logging.warning(
        "FERNET_KEY not set in .env; generated ephemeral key")
cipher = Fernet(FERNET_KEY.encode())

# DB pool
try:
    DB_POOL = psycopg2.pool.ThreadedConnectionPool(
        1, 10,
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
    )
except Exception as e:
    logging.error(f"Error creating DB pool: {e}")
    sys.exit(1)

# --- Utility ---
def keccak(x: bytes) -> bytes:
    return hashlib.new('sha3_256', x).digest()

def derive_address_from_pubkey(pubkey_bytes: bytes) -> str:
    return to_checksum_address(keccak(pubkey_bytes)[-20:])

# --- HD Wallet fallback ---
class HDWallet:
    def __init__(self, mnemonic=None, passphrase=""): pass
    def derive_account(self, idx=0):
        priv = os.urandom(32)
        priv_hex = priv.hex()
        addr = keys.PrivateKey(priv).public_key.to_checksum_address()
        return {"private_key": priv_hex, "address": addr}

# --- Autoencoder persistence ---
AUTOENCODER_FILE = "autoencoder.h5"
autoencoder = tf.keras.Sequential([
    layers.Dense(32, activation='relu', input_shape=(4,)),
    layers.Dense(16, activation='relu'),
    layers.Dense(32, activation='relu'),
    layers.Dense(4, activation='sigmoid'),
])
autoencoder.compile(optimizer='adam', loss='mse')

def load_or_train_autoencoder():
    if os.path.exists(AUTOENCODER_FILE):
        autoencoder.load_weights(AUTOENCODER_FILE)
        logging.info("Loaded autoencoder weights.")
    else:
        # Placeholder: replace with real data loading
        data = np.random.rand(1000,4)
        autoencoder.fit(data, data, epochs=50, batch_size=32, verbose=0)
        autoencoder.save_weights(AUTOENCODER_FILE)
        logging.info("Trained and saved new autoencoder.")

def update_model(new_data: np.ndarray):
    autoencoder.fit(new_data, new_data, epochs=20, batch_size=16)
    autoencoder.save_weights(AUTOENCODER_FILE)
    logging.info("Autoencoder updated with new data.")

load_or_train_autoencoder()

# --- Anomaly detection & zk proof ---
ANOMALY_LOG = "anomalies.log"
ANOMALY_THRESHOLD = 0.1

def validate_with_hidden_model(tx, zk_vk=None):
    # signature and balance/nonce checks happen elsewhere
    f1 = f2 = 0.0
    try:
        f1 = float(int(tx.from_address[:8],16))
        f2 = float(int(tx.to_address[:8],16))
    except: pass
    f3, f4 = float(tx.amount), float(tx.timestamp)
    inp = np.array([[f1,f2,f3,f4]])
    rec = autoencoder.predict(inp, verbose=0)
    mse = float(np.mean((inp-rec)**2))
    if mse >= ANOMALY_THRESHOLD:
        with open(ANOMALY_LOG,"a") as f:
            f.write(f"{datetime.now().isoformat()} ANOMALY tx={tx.to_dict()} mse={mse}\n")
        return False
    # zk proof
    if getattr(tx,"proof",None) is not None:
        if not zk_vk or not tx.verify(zk_vk):
            return False
    return True

# --- Key gen ---
def generate_rsa_key_pair():
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

# --- Transaction classes ---
class Transaction:
    def __init__(self, from_address, to_address, amount, timestamp=None, nonce=0, data=b"", chain_id=CHAIN_ID, signature=None):
        self.from_address, self.to_address = from_address, to_address
        self.amount = int(amount)
        self.timestamp = timestamp or datetime.now().timestamp()
        self.nonce = nonce
        self.data = data if isinstance(data,bytes) else bytes.fromhex(data) if data else b""
        self.chain_id = chain_id
        self.signature = signature

    def to_dict(self):
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

    def _hash(self):
        return keccak(
            self.from_address.encode()+
            self.to_address.encode()+
            self.amount.to_bytes(8,'big')+
            self.nonce.to_bytes(8,'big')+
            self.chain_id.to_bytes(2,'big')+
            self.data
        )

    def sign(self, priv_hex):
        sig = keys.PrivateKey(bytes.fromhex(priv_hex)).sign_msg(self._hash())
        self.signature = sig.to_bytes().hex()

    def verify_signature(self):
        if not self.signature: return False
        sig = keys.Signature(bytes.fromhex(self.signature))
        pub = sig.recover_public_key_from_msg(self._hash())
        return derive_address_from_pubkey(pub.to_bytes())==self.from_address

class ShieldedTransaction:
    def __init__(self, commitment, proof):
        self.commitment, self.proof = commitment, proof
    @staticmethod
    def create(amount,priv_val,pub_key,vk):
        with snark: assert amount>=0
        return ShieldedTransaction(b"...", snark.prove())
    def verify(self,vk): return snark.verify(self.proof,vk)

# --- Blockchain & P2P ---
class Blockchain:
    def __init__(self,db_pool):
        self.db_pool, self.chain, self.balances, self.nonces = db_pool, [], {}, {}
        self.pending_transactions=[]
        self.owner_priv, self.owner_pub = generate_rsa_key_pair()
        self.zk_vk=None
        self.load_state()

    def load_state(self):
        try:
            conn=self.db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT index,data FROM blockchain ORDER BY index")
                for idx,raw in cur.fetchall():
                    blk=Block(**json.loads(raw))
                    self.chain.append(blk)
                cur.execute("SELECT address,balance FROM balances")
                for addr,bal in cur.fetchall(): self.balances[addr]=bal
        except Exception as e:
            logging.error(f"load_state error: {e}")
        finally:
            self.db_pool.putconn(conn)

    def save_state(self):
        try:
            conn=self.db_pool.getconn()
            with conn.cursor() as cur:
                for blk in self.chain:
                    cur.execute(
                        "INSERT INTO blockchain(index,data) VALUES(%s,%s) ON CONFLICT(index) DO UPDATE SET data=%s",
                        (blk.index,json.dumps(blk.to_dict()),json.dumps(blk.to_dict())))
                for addr,bal in self.balances.items():
                    cur.execute(
                        "INSERT INTO balances(address,balance) VALUES(%s,%s) ON CONFLICT(address) DO UPDATE SET balance=%s",
                        (addr,bal,bal))
                conn.commit()
        except Exception as e:
            logging.error(f"save_state error: {e}")
        finally:
            self.db_pool.putconn(conn)

    def create_genesis_block(self):
        tx=Transaction("genesis",self.owner_pub,0,nonce=0)
        blk=Block(0,[tx],"0")
        self.chain=[blk]
        self.balances[self.owner_pub]=0
        self.nonces[self.owner_pub]=0
        self.save_state()

    def get_block_reward(self,idx):
        h=idx//210000
        return BLOCK_REWARD_INITIAL//(2**h) if h<64 else 0

    def proof_of_work(self,block,difficulty=4):
        target='0'*difficulty
        while not block.hash.startswith(target):
            block.nonce+=1
            block.hash=block.calculate_hash()
        return block

    def is_valid_transaction(self,tx):
        # signature
        if not tx.verify_signature(): return False
        # anomaly/ZK
        if not validate_with_hidden_model(tx,self.zk_vk): return False
        # balance & nonce
        if tx.from_address not in ("system","genesis"):
            bal=self.balances.get(tx.from_address,0)
            if bal<tx.amount+int(tx.amount*COMMISSION_RATE): return False
            if tx.nonce!=self.nonces.get(tx.from_address,0): return False
        return True

    def is_valid_block(self,blk):
        if not self.chain: return True
        prev=self.chain[-1]
        return (blk.previous_hash==prev.hash and
                blk.hash==blk.calculate_hash() and
                blk.hash.startswith('0000'))

    def add_block(self,blk):
        if not self.is_valid_block(blk):
            raise ValueError("Invalid block proof-of-work or chain")
        # validate txs
        for tx in blk.transactions:
            if not self.is_valid_transaction(tx):
                raise ValueError(f"Invalid tx {tx.to_dict()}")
        # all good
        self.chain.append(blk)
        for tx in blk.transactions:
            if tx.from_address=="system":
                self.balances[tx.to_address]=self.balances.get(tx.to_address,0)+tx.amount
            elif tx.from_address!="genesis":
                fee=int(tx.amount*COMMISSION_RATE)
                self.balances[tx.from_address]-=(tx.amount+fee)
                self.balances[tx.to_address]=self.balances.get(tx.to_address,0)+tx.amount
                self.balances[self.owner_pub]=self.balances.get(self.owner_pub,0)+fee
            self.nonces[tx.from_address]=self.nonces.get(tx.from_address,0)+1
        self.save_state()

    def mine_block(self):
        prev=self.chain[-1]
        idx=prev.index+1
        reward=Transaction("system",self.owner_pub,self.get_block_reward(idx),nonce=0)
        txs=[reward]+self.pending_transactions
        self.pending_transactions=[]
        blk=Block(idx,txs,prev.hash)
        blk=self.proof_of_work(blk)
        self.add_block(blk)
        logging.info(f"Mined block {blk.index} hash={blk.hash}")

# --- Block ---
class Block:
    def __init__(self,index,transactions,previous_hash,timestamp=None,nonce=0,hash=None):
        self.index=index
        self.transactions=[Transaction(**t) if isinstance(t,dict) else t for t in transactions]
        self.previous_hash=previous_hash
        self.timestamp=timestamp or time.time()
        self.nonce=nonce
        self.hash=hash or self.calculate_hash()

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

# --- Tests ---
def run_tests():
    wallet=HDWallet()
    bc=Blockchain(DB_POOL)
    bc.create_genesis_block()
    # genesis
    assert len(bc.chain)==1
    assert bc.balances[bc.owner_pub]==0

    # signature & simple tx
    acct=wallet.derive_account()
    bc.balances[acct['address']]=100*BASE_UNIT
    tx=Transaction(acct['address'],bc.owner_pub,10*BASE_UNIT,nonce=0)
    tx.sign(acct['private_key'])
    assert tx.verify_signature()
    assert bc.is_valid_transaction(tx)

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

if __name__=='__main__':
    run_tests()
    print("Tests completed successfully.")
