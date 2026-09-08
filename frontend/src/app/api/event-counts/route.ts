import { db } from "@/db";
import { events } from "@/db/schema";
import { ensureSeeded } from "@/lib/seed";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await ensureSeeded();
    const rows = await db
      .select({ eventType: events.eventType, n: sql<number>`count(*)::int` })
      .from(events)
      .groupBy(events.eventType);

    const counts: Record<string, number> = {};
    let total = 0;
    for (const r of rows) {
      counts[r.eventType] = r.n;
      total += r.n;
    }

    const last24 = await db
      .select({ n: sql<number>`count(*)::int` })
      .from(events)
      .where(sql`${events.timestamp} > now() - interval '24 hours'`);

    return Response.json({
      counts,
      total,
      last_24h: last24[0]?.n ?? 0,
    });
  } catch (err) {
    return Response.json(
      { error: "counts_query_failed", detail: String(err) },
      { status: 500 },
    );
  }
}
