import { db } from "@/db";
import { cameras } from "@/db/schema";
import { ensureSeeded } from "@/lib/seed";
import { asc, eq, sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

const VALID_STATUS = new Set(["active", "maintenance", "offline"]);

export async function GET() {
  try {
    await ensureSeeded();
    const list = await db
      .select()
      .from(cameras)
      .orderBy(asc(cameras.id));

    const counts = await db.execute(sql`
      SELECT camera_id, count(*)::int AS n
      FROM events
      WHERE "timestamp" > now() - interval '24 hours'
      GROUP BY 1
    `);
    const countRows = (
      counts as unknown as { rows: Array<{ camera_id: number; n: number }> }
    ).rows;
    const countMap = new Map(countRows.map((r) => [r.camera_id, r.n]));

    return Response.json({
      cameras: list.map((c) => ({
        ...c,
        events_24h: countMap.get(c.id) ?? 0,
      })),
      online: list.filter((c) => c.status === "active").length,
      count: list.length,
    });
  } catch (err) {
    return Response.json(
      { error: "cameras_query_failed", detail: String(err) },
      { status: 500 },
    );
  }
}

export async function PATCH(req: Request) {
  try {
    const body = (await req.json()) as { id?: unknown; status?: unknown };
    const id = Number(body.id);
    const status = String(body.status ?? "");
    if (!Number.isInteger(id) || !VALID_STATUS.has(status)) {
      return Response.json(
        {
          error: "invalid_request",
          detail: "expected { id: number, status: 'active' | 'maintenance' | 'offline' }",
        },
        { status: 400 },
      );
    }
    const updated = await db
      .update(cameras)
      .set({ status })
      .where(eq(cameras.id, id))
      .returning();
    if (updated.length === 0) {
      return Response.json({ error: "not_found" }, { status: 404 });
    }
    return Response.json({ camera: updated[0] });
  } catch (err) {
    return Response.json(
      { error: "camera_update_failed", detail: String(err) },
      { status: 500 },
    );
  }
}
