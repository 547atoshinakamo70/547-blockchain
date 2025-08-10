import express, { Express, Request, Response } from 'express';
import { createServer, Server } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import crypto from 'crypto';
import PeerBalanceManager from './PeerBalanceManager';
import qnnValidator from './qnnValidator';

// External dependencies provided by the runtime environment
// These are declared here to satisfy TypeScript without explicit imports.
declare const db: unknown;
declare const wallets: unknown;
declare const persistentWallet: unknown;
declare const storage: unknown;

const connectedPeers = new Set<WebSocket>();
const peerBalanceManager = new PeerBalanceManager();

export async function registerRoutes(app: Express): Promise<Server> {
  app.use(express.json());

  const server = createServer(app);
  const wss = new WebSocketServer({ server, path: '/ws' });

  wss.on('connection', (ws: WebSocket) => {
    connectedPeers.add(ws);

    ws.on('message', async (data: WebSocket.RawData) => {
      try {
        const message = JSON.parse(data.toString());
        if (message.type === 'new_transaction') {
          await qnnValidator.validateTransaction(message.payload);
        }
      } catch (err) {
        console.error('Failed to process message', err);
      }
    });

    ws.on('close', () => {
      connectedPeers.delete(ws);
    });
  });

  app.get('/api/wallet/status', (_req: Request, res: Response) => {
    try {
      res.json({ db, wallets, persistentWallet, storage });
    } catch {
      res.status(500).json({ error: 'Unable to fetch status' });
    }
  });

  const miningStats = { active: false, rewardsIssued: 0 };
  let miningInterval: NodeJS.Timeout | null = null;

  app.post('/api/mining/start', (_req: Request, res: Response) => {
    miningStats.active = !miningStats.active;
    if (miningStats.active) {
      miningInterval = setInterval(() => {
        peerBalanceManager.issueReward();
        miningStats.rewardsIssued += 1;
      }, 10000);
    } else if (miningInterval) {
      clearInterval(miningInterval);
      miningInterval = null;
    }
    res.json(miningStats);
  });

  app.get('/api/wallet/multi-addresses', (_req: Request, res: Response) => {
    const coins = ['BTC', 'ETH', 'USDT', 'USDC'];
    const addresses = coins.reduce<Record<string, string>>((acc, coin) => {
      const hash = crypto.createHash('sha256').update(coin).digest('hex');
      acc[coin.toLowerCase()] = hash.slice(0, 34);
      return acc;
    }, {});
    res.json(addresses);
  });

  return server;
}

