ENJOY

# 🚀 HybridChain – Blockchain & Wallet by Rami Bond

HybridChain** is a next-generation blockchain designed by Rami Bond, featuring:

* **Hybrid Proof-of-Work** with micro block rewards + transaction fees
* **Advanced privacy** via ZK-SNARKs and optional CoinJoin
* **Quantum-ASIC resistant mining** and enhanced **51% attack resistance**
* **Integrated wallet** capable of running as a full node

---

## 🌟 Key Features

### **Blockchain**

* **Hybrid reward model**:

  * **0.0289 Tokens per block** (initial reward)
  * **+0.2% transaction fee** per included transaction
* **Block time**: 10 seconds
* **ZK-SNARK privacy** for shielded transactions
* **Optional PostgreSQL-free mode** with local JSON storage
* **Continuous mining with automatic difficulty adjustment**

### **Wallet**

* **Local key generation and secure storage** (`~/.mywallet_key`)
* **Send and receive tokens** via local RPC (`http://localhost:5000`)
* **CLI tools to check balances and sign transactions**
* **Optional CoinJoin mixing** for privacy
* **Every wallet is also a node**, strengthening decentralization

---

## 📊 Tokenomics

| Parameter               | Value                          |
| ----------------------- | ------------------------------ |
| Block reward            | 0.0289 Tokens                  |
| Transaction fee         | 0.2% per transaction           |
| Block time              | 10 s                           |
| Estimated yearly tokens | \~91,000 Tokens/year (network) |
| Projected max supply    | \~5.47 M Tokens                |

> **Note:** This micro‑emission model limits inflation and prevents hash‑rate spikes from flooding the market, even under quantum ASIC mining conditions.

---

## 🔐 Security & Innovation

* **51% attack resistance** due to micro-block rewards and fee-based incentives
* **Privacy‑focused** with optional **ZK-SNARKs and CoinJoin**
* **Future‑proof** against quantum mining hardware and hash‑rate surges
* **Economic balance**: rewards scale naturally with real network usage

---

## 🖥️ How to Run the Blockchain

1. **Activate your virtual environment**:

   ```bash
   source ~/venv/bin/activate
   ```

2. **Start the blockchain node with mining enabled**:

   ```bash
   python mi_blockchain.py
   ```

3. **Run the blockchain in the background** (optional):

   ```bash
   nohup python mi_blockchain.py > node.log 2>&1 &
   ```

4. **Check logs**:

   ```bash
   tail -f node.log
   ```

---

## 💳 How to Use the Wallet

1. **Run the wallet CLI**:

   ```bash
   python wallet.py
   ```

2. **Check your balance**:

   ```bash
   python wallet.py balance
   ```

3. **Send tokens**:

   ```bash
   python wallet.py send <recipient_address> <amount>
   ```

4. **Sign a message**:

   ```bash
   python wallet.py sign "My message"
   ```

---

## ✅ Recommended Workflow

* **Step 1:** Start the blockchain node and let it mine
* **Step 2:** Launch the wallet CLI in another terminal
* **Step 3:** Use your wallet to receive mined tokens and send transactions
* **Step 4:** (Optional) Enable CoinJoin for maximum privacy

---

If you want, I can now **generate this README as a professional PDF with charts** showing:

* **Emission per block (0.0289 tokens)**
* **Yearly emission vs. total supply**
* **Transaction-fee incentives growth**

Do you want me to generate the **PDF ready to publish**?
