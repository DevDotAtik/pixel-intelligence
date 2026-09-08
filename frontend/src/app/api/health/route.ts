import { db } from "@/db";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  let dbStatus: "up" | "down" = "down";
  let latencyMs: number | null = null;
  try {
    const t0 = performance.now();
    await db.execute(sql`select 1`);
    dbStatus = "up";
    latencyMs = Math.round((performance.now() - t0) * 10) / 10;
  } catch {
    dbStatus = "down";
  }
  return Response.json({
    ok: true,
    status: "ok",
    service: "Pixel Intelligence · AI Video Analytics API",
    version: "1.0.0",
    db: dbStatus,
    db_latency_ms: latencyMs,
    timestamp: new Date().toISOString(),
  });
}
