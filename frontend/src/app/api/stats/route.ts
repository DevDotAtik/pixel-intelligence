import { db } from "@/db";
import { ensureSeeded } from "@/lib/seed";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

function rows<T>(r: unknown): T[] {
  return (r as { rows: T[] }).rows;
}

export async function GET() {
  try {
    await ensureSeeded();

    const [totals, daily, hourly, klass, perCam, confHist, recent] =
      await Promise.all([
        db.execute(sql`
          SELECT count(*)::int AS n,
                 count(DISTINCT tracking_id)::int AS tracks
          FROM events
          WHERE "timestamp" > now() - interval '7 days'
        `),
        db.execute(sql`
          SELECT to_char(date_trunc('day', "timestamp"), 'YYYY-MM-DD') AS d,
                 event_type,
                 count(*)::int AS n
          FROM events
          WHERE "timestamp" > now() - interval '14 days'
          GROUP BY 1, 2
          ORDER BY 1
        `),
        db.execute(sql`
          SELECT extract(hour from "timestamp")::int AS h,
                 event_type,
                 (count(*) / 7.0)::float AS n
          FROM events
          WHERE "timestamp" > now() - interval '7 days'
          GROUP BY 1, 2
          ORDER BY 1
        `),
        db.execute(sql`
          SELECT class_name AS k,
                 count(*)::int AS n,
                 round(avg(confidence)::numeric, 4)::float AS avg_conf
          FROM events
          WHERE "timestamp" > now() - interval '7 days'
          GROUP BY 1
          ORDER BY 2 DESC
        `),
        db.execute(sql`
          SELECT c.code, c.name, c.status, count(*)::int AS n
          FROM events e
          JOIN cameras c ON c.id = e.camera_id
          WHERE e."timestamp" > now() - interval '7 days'
          GROUP BY 1, 2, 3
          ORDER BY 4 DESC
        `),
        db.execute(sql`
          SELECT width_bucket(confidence, 0.5, 1.0, 10) AS b,
                 count(*)::int AS n
          FROM events
          WHERE "timestamp" > now() - interval '7 days'
          GROUP BY 1
          ORDER BY 1
        `),
        db.execute(sql`
          SELECT e.id, e."timestamp", e.event_type, e.class_name,
                 e.confidence, e.tracking_id, c.code AS camera_code, c.name AS camera_name
          FROM events e
          JOIN cameras c ON c.id = e.camera_id
          ORDER BY e."timestamp" DESC, e.id DESC
          LIMIT 9
        `),
      ]);

    const totalsRow = rows<{ n: number; tracks: number }>(totals)[0] ?? {
      n: 0,
      tracks: 0,
    };

    // Pivot daily + hourly rows into chart-friendly shapes.
    const dailyMap = new Map<string, Record<string, number | string>>();
    for (const r of rows<{ d: string; event_type: string; n: number }>(daily)) {
      const row = dailyMap.get(r.d) ?? { day: r.d };
      row[r.event_type] = r.n;
      dailyMap.set(r.d, row);
    }

    const hourlyArr: Array<Record<string, number>> = Array.from(
      { length: 24 },
      (_, h) => ({ hour: h }),
    );
    for (const r of rows<{ h: number; event_type: string; n: number }>(hourly)) {
      hourlyArr[r.h][r.event_type] = Math.round(r.n * 10) / 10;
    }

    return Response.json({
      totals: {
        events_7d: totalsRow.n,
        unique_tracks: totalsRow.tracks,
        avg_per_hour: Math.round((totalsRow.n / 168) * 10) / 10,
      },
      daily: [...dailyMap.values()],
      hourly: hourlyArr,
      classes: rows<{ k: string; n: number; avg_conf: number }>(klass),
      cameras: rows<{ code: string; name: string; status: string; n: number }>(
        perCam,
      ),
      confidence_hist: rows<{ b: number; n: number }>(confHist),
      recent: rows<Record<string, unknown>>(recent),
      generated_at: new Date().toISOString(),
    });
  } catch (err) {
    return Response.json(
      { error: "stats_query_failed", detail: String(err) },
      { status: 500 },
    );
  }
}
