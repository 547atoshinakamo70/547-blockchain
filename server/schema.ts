import { sqliteTable, integer, text } from 'drizzle-orm/sqlite-core';

export const miningStats = sqliteTable('mining_stats', {
  peerId: text('peer_id').primaryKey(),
  hashes: integer('hashes').notNull(),
});

export const balances = sqliteTable('balances', {
  address: text('address').primaryKey(),
  balance: integer('balance').notNull(),
});
