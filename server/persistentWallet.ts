import fs from 'fs';
import path from 'path';

const WALLET_FILE = path.join(__dirname, '..', 'wallet.json');

export function getWalletAddress(): string | null {
  try {
    const raw = fs.readFileSync(WALLET_FILE, 'utf8');
    const data = JSON.parse(raw);
    return data.address || null;
  } catch {
    return null;
  }
}
