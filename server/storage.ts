import { db, eq } from './db';
import { miningStats, balances } from './schema';

export async function getMiningStats(peerId: string) {
  const result = await db.select().from(miningStats).where(eq(miningStats.peerId, peerId));
  return result[0] ?? null;
}

export async function updateMiningStats(peerId: string, hashes: number) {
  await db
    .insert(miningStats)
    .values({ peerId, hashes })
    .onConflictDoUpdate({ target: miningStats.peerId, set: { hashes } });
}

export async function getCurrentBalance(address: string) {
  const result = await db.select().from(balances).where(eq(balances.address, address));
  return result[0]?.balance ?? 0;
}

export async function updateBalance(address: string, balance: number) {
  await db
    .insert(balances)
    .values({ address, balance })
    .onConflictDoUpdate({ target: balances.address, set: { balance } });
}
