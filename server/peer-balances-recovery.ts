import { getCurrentBalance, updateBalance } from './storage';

export class PeerBalanceManager {
  private cache = new Map<string, number>();

  async load(address: string) {
    const balance = await getCurrentBalance(address);
    this.cache.set(address, balance);
    return balance;
  }

  async set(address: string, balance: number) {
    this.cache.set(address, balance);
    await updateBalance(address, balance);
  }

  get(address: string) {
    return this.cache.get(address) ?? 0;
  }
}
