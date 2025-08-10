import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import { eq } from 'drizzle-orm';

const sqlite = new Database('app.db');
export const db = drizzle(sqlite);
export { eq };
