#!/usr/bin/env python3
"""
Simple CLI Wallet (single-file)
Features:
- Generate / load a single ECDSA key
- Show address, balance
- Send transactions to your blockchain node over HTTP
- Sign arbitrary messages and verify signatures
- (Placeholder) CoinJoin command stub
"""
import os
import sys
import json
import click
import requests
from eth_keys import keys
from eth_utils import to_checksum_address

# ─── Configuration ───────────────────────────────────────────────────────────
RPC_URL   = os.getenv("NODE_RPC", "http://localhost:5000")
KEY_FILE  = os.path.expanduser("~/.mywallet_key")
BASE_UNIT = 10**8
CHAIN_ID  = 60

# ─── Helpers ─────────────────────────────────────────────────────────────────
def load_or_create_key():
    """Load a saved private key hex or generate+save a new one."""
    if os.path.exists(KEY_FILE):
        priv_hex = open(KEY_FILE, "r").read().strip()
    else:
        priv_bytes = os.urandom(32)
        priv_hex   = priv_bytes.hex()
        with open(KEY_FILE, "w") as f:
            f.write(priv_hex)
        click.echo(f"[+] New wallet key generated and saved to {KEY_FILE}")
    priv = keys.PrivateKey(bytes.fromhex(priv_hex))
    # Ethereum‐style address: last 20 bytes of pubkey hash
    addr = to_checksum_address(priv.public_key.to_bytes()[-20:])
    return priv, addr

class ChainClient:
    """Minimal HTTP client for your blockchain node."""
    def __init__(self, rpc_url):
        self.rpc = rpc_url.rstrip("/")

    def get_balance(self, address):
        r = requests.get(f"{self.rpc}/balance?address={address}")
        r.raise_for_status()
        return int(r.json().get("balance", 0))

    def get_chain(self):
        r = requests.get(f"{self.rpc}/chain")
        r.raise_for_status()
        return r.json().get("chain", [])

    def broadcast_tx(self, tx_dict):
        r = requests.post(f"{self.rpc}/tx", json=tx_dict)
        return r.status_code == 200

def compute_nonce(chain, address):
    """Count how many txs from `address` appear in the chain as nonce."""
    count = 0
    for blk in chain:
        for tx in blk.get("transactions", []):
            if tx.get("from") == address:
                count += 1
    return count

# ─── CLI Definition ──────────────────────────────────────────────────────────
@click.group()
@click.pass_context
def cli(ctx):
    """MyWallet CLI"""
    priv, addr = load_or_create_key()
    ctx.obj = {
        "priv":  priv,
        "addr":  addr,
        "chain": ChainClient(RPC_URL),
    }

@cli.command()
@click.pass_context
def address(ctx):
    """Show your wallet address."""
    click.echo(ctx.obj["addr"])

@cli.command()
@click.pass_context
def balance(ctx):
    """Show on‐chain balance."""
    addr = ctx.obj["addr"]
    bal  = ctx.obj["chain"].get_balance(addr)
    click.echo(f"Balance for {addr}: {bal/BASE_UNIT:.8f} tokens")

@cli.command()
@click.argument("to")
@click.argument("amount", type=float)
@click.pass_context
def send(ctx, to, amount):
    """Send AMOUNT tokens to address TO."""
    priv   = ctx.obj["priv"]
    addr   = ctx.obj["addr"]
    client = ctx.obj["chain"]

    amt   = int(amount * BASE_UNIT)
    chain = client.get_chain()
    nonce = compute_nonce(chain, addr)

    # Build transaction dict
    tx = {
        "from_address": addr,
        "to_address":   to,
        "amount":       amt,
        "nonce":        nonce,
        "chain_id":     CHAIN_ID,
        "data":         ""
    }

    # Hash payload (simple concatenation + keccak)
    import hashlib
    payload = (
        tx["from_address"].encode() +
        tx["to_address"].encode() +
        tx["amount"].to_bytes(8, "big") +
        tx["nonce"].to_bytes(8, "big") +
        tx["chain_id"].to_bytes(2, "big")
    )
    msg_hash = hashlib.new("sha3_256", payload).digest()

    # Sign and attach signature
    sig = priv.sign_msg(msg_hash)
    tx["signature"] = sig.to_bytes().hex()

    # Broadcast
    if client.broadcast_tx(tx):
        click.secho(f"✅ Sent {amount:.8f} tokens to {to} (nonce={nonce})", fg="green")
    else:
        click.secho("❌ Transaction failed", fg="red")

@cli.command()
@click.option("--msg", prompt="Message", help="Message to sign")
@click.pass_context
def sign(ctx, msg):
    """Sign an arbitrary message."""
    priv = ctx.obj["priv"]
    sig  = priv.sign_msg(msg.encode())
    click.echo(sig.to_bytes().hex())

@cli.command()
@click.option("--msg", prompt="Message", help="Original message")
@click.option("--sig", prompt="Signature (hex)", help="Hex signature to verify")
def verify(msg, sig):
    """Verify a signed message."""
    try:
        signature = keys.Signature(bytes.fromhex(sig))
        pub = signature.recover_public_key_from_msg(msg.encode())
        addr = to_checksum_address(pub.to_bytes()[-20:])
        click.secho(f"✔ Signature valid! Address: {addr}", fg="green")
    except Exception as e:
        click.secho(f"❌ Invalid signature: {e}", fg="red")

@cli.command()
@click.argument("amount", type=float)
@click.option("--peers", default=2, help="Peers in CoinJoin")
@click.pass_context
def coinjoin(ctx, amount, peers):
    """(Stub) Create a CoinJoin session with N peers."""
    click.echo(f"CoinJoin of {amount} tokens with {peers} peers is not implemented yet.")

if __name__ == "__main__":
    cli()
