import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

// The live console can run against Django/FastAPI without Postgres. Keep the
// local Arena database as the default for optional analytics/event pages, while
// allowing deployments to override it with DATABASE_URL.
const databaseUrl =
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@127.0.0.1:5432/app_db";

const globalForDb = globalThis as typeof globalThis & {
  __arenaNextJsPostgresqlPool?: Pool;
};

export const pool =
  globalForDb.__arenaNextJsPostgresqlPool ??
  new Pool({
    connectionString: databaseUrl,
  });

if (process.env.NODE_ENV !== "production") {
  globalForDb.__arenaNextJsPostgresqlPool = pool;
}

export const db = drizzle(pool);
