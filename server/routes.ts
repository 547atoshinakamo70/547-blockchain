import { Router } from 'express';
import { getWalletAddress } from './persistentWallet';
import { getMiningStats, updateMiningStats, getCurrentBalance, updateBalance } from './storage';
import { PeerBalanceManager } from './peer-balances-recovery';
import { db, eq } from './db';

const router = Router();
const balanceManager = new PeerBalanceManager();

router.get('/wallet', (req, res) => {
  res.json({ address: getWalletAddress() });
});

router.get('/balances/:address', async (req, res) => {
  const address = req.params.address;
  const balance = await balanceManager.load(address);
  res.json({ balance });
});

export default router;
