import { db } from "@/db";
import { cameras, events } from "@/db/schema";
import { ensureSeeded } from "@/lib/seed";
import { CLASS_GROUP, GROUP_EVENT, groupOf } from "@/lib/sim";
import { and, desc, eq, gte, sql, type SQL } from "drizzle-orm";

export const dynamic = "force-dynamic";

const GROUP_TO_CLASSES: Record<string, string[]> = Object.entries(
  CLASS_GROUP,
).reduce<Record<string, string[]>>((acc, [cls, group]) => {
  (acc[group] ??= []).push(cls);
  return acc;
}, {});

export async function GET(req: Request) {
  try {
    await ensureSeeded();
    const { searchParams } = new URL(req.url);
    const camera = searchParams.get("camera");
    const klass = searchParams.get("class");
    const type = searchParams.get("type");
    const minConf = Number(searchParams.get("min_conf") ?? "0");
    const track = Number(searchParams.get("track") ?? "");
    const limit = Math.min(
      200,
      Math.max(1, Number(searchParams.get("limit") ?? "50") || 50),
    );
    const offset = Math.max(0, Number(searchParams.get("offset") ?? "0") || 0);

    const conditions: SQL[] = [];
    if (camera && camera !== "all") {
      if (/^\d+$/.test(camera)) {
        conditions.push(eq(events.cameraId, Number(camera)));
      } else {
        conditions.push(eq(cameras.code, camera));
      }
    }
    if (klass && klass !== "all") {
      const groupClasses = GROUP_TO_CLASSES[klass];
      if (groupClasses) {
        conditions.push(
          sql`${events.className} = ANY(${groupClasses})`,
        );
      } else {
        conditions.push(eq(events.className, klass));
      }
    }
    if (type && type !== "all") conditions.push(eq(events.eventType, type));
    if (minConf > 0) conditions.push(gte(events.confidence, minConf));
    if (Number.isFinite(track) && track > 0)
      conditions.push(eq(events.trackingId, track));

    const where = conditions.length ? and(...conditions) : undefined;

    const [rows, countRows] = await Promise.all([
      db
        .select({
          id: events.id,
          timestamp: events.timestamp,
          eventType: events.eventType,
          className: events.className,
          confidence: events.confidence,
          trackingId: events.trackingId,
          cameraId: events.cameraId,
          cameraCode: cameras.code,
          cameraName: cameras.name,
        })
        .from(events)
        .innerJoin(cameras, eq(events.cameraId, cameras.id))
        .where(where)
        .orderBy(desc(events.timestamp), desc(events.id))
        .limit(limit)
        .offset(offset),
      db
        .select({ n: sql<number>`count(*)::int` })
        .from(events)
        .innerJoin(cameras, eq(events.cameraId, cameras.id))
        .where(where),
    ]);

    return Response.json({
      events: rows,
      count: countRows[0]?.n ?? 0,
      limit,
      offset,
    });
  } catch (err) {
    return Response.json(
      { error: "events_query_failed", detail: String(err) },
      { status: 500 },
    );
  }
}

interface IncomingEvent {
  event_type?: unknown;
  class_name?: unknown;
  className?: unknown;
  confidence?: unknown;
  tracking_id?: unknown;
  trackingId?: unknown;
  camera?: unknown;
  camera_code?: unknown;
}

export async function POST(req: Request) {
  try {
    await ensureSeeded();
    const body = (await req.json()) as { events?: IncomingEvent[] };
    const list = Array.isArray(body.events) ? body.events.slice(0, 500) : [];
    if (list.length === 0) {
      return Response.json(
        { error: "no_events", detail: "body.events must be a non-empty array" },
        { status: 400 },
      );
    }

    const camRows = await db
      .select({ id: cameras.id, code: cameras.code })
      .from(cameras);
    const codeToId = new Map(camRows.map((c) => [c.code, c.id]));
    const fallbackCam = camRows[0]?.id;

    const rows: Array<typeof events.$inferInsert> = [];
    for (const raw of list) {
      const className = String(
        raw.class_name ?? raw.className ?? "person",
      ).slice(0, 40);
      const group = groupOf(className);
      const cameraCode = String(raw.camera ?? raw.camera_code ?? "");
      const cameraId = codeToId.get(cameraCode) ?? fallbackCam;
      if (!cameraId) continue;
      const confidence = Math.max(
        0,
        Math.min(1, Number(raw.confidence ?? 0.9) || 0),
      );
      rows.push({
        eventType: String(raw.event_type ?? GROUP_EVENT[group]).slice(0, 40),
        className,
        confidence,
        trackingId: Math.max(
          0,
          Math.min(1_000_000, Number(raw.tracking_id ?? raw.trackingId ?? 0) || 0),
        ),
        cameraId,
      });
    }

    if (rows.length > 0) await db.insert(events).values(rows);
    return Response.json(
      { inserted: rows.length, timestamp: new Date().toISOString() },
      { status: 201 },
    );
  } catch (err) {
    return Response.json(
      { error: "events_insert_failed", detail: String(err) },
      { status: 500 },
    );
  }
}
