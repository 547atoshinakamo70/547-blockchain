import { pgTable, serial, varchar, decimal, integer, boolean, timestamp, text } from "drizzle-orm/pg-core";

// Tabla principal de wallets
export const wallets = pgTable("wallets", {
  id: serial("id").primaryKey(),
  address: varchar("address", { length: 42 }).notNull().unique(),
  balance: decimal("balance", { precision: 20, scale: 8 }).notNull().default("0"),
  privateBalance: decimal("private_balance", { precision: 20, scale: 8 }).notNull().default("0"),
  totalMined: decimal("total_mined", { precision: 20, scale: 8 }).notNull().default("0"),
  totalBlocks: integer("total_blocks").notNull().default(0),
  lastMiningSession: timestamp("last_mining_session").defaultNow(),
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at").defaultNow()
});

// Direcciones multi-currency (BTC, ETH, USDT, USDC)
export const multiWalletAddresses = pgTable("multi_wallet_addresses", {
  id: serial("id").primaryKey(),
  mainWallet: varchar("main_wallet", { length: 42 }).notNull(),
  currency: varchar("currency", { length: 10 }).notNull(), // BTC, ETH, USDT, USDC
  address: varchar("address", { length: 64 }).notNull(),
  balance: decimal("balance", { precision: 20, scale: 8 }).notNull().default("0"),
  privateKey: varchar("private_key", { length: 128 }), // Encrypted
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at").defaultNow()
});

// Mensajes ZK-SNARKs en blockchain
export const zkChatMessages = pgTable('zk_chat_messages', {
  id: serial('id').primaryKey(),
  messageHash: varchar('message_hash', { length: 64 }).notNull().unique(),
  senderAddress: varchar('sender_address', { length: 42 }).notNull(),
  encryptedContent: text('encrypted_content').notNull(),
  zkProof: text('zk_proof').notNull(),
  nullifierHash: varchar('nullifier_hash', { length: 64 }).notNull(),
  commitment: varchar('commitment', { length: 64 }).notNull(),
  blockHeight: integer('block_height').notNull(),
  timestamp: timestamp('timestamp').defaultNow().notNull(),
  roomId: varchar('room_id', { length: 32 }).notNull().default('global'),
  isVerified: boolean('is_verified').notNull().default(false)
});

// Recompensas de minería
export const miningRewards = pgTable("mining_rewards", {
  id: serial("id").primaryKey(),
  walletAddress: varchar("wallet_address", { length: 42 }).notNull(),
  blockHeight: integer("block_height").notNull(),
  reward: decimal("reward", { precision: 20, scale: 8 }).notNull(),
  minedAt: timestamp("mined_at").defaultNow(),
  sessionId: varchar("session_id", { length: 64 }).notNull()
});
