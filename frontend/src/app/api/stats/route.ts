import { backend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

type BackendSighting = {
  _id?: string;
  subject_key: string;
  camera_code: string;
  class_name: string;
  identity: string | null;
  registered: boolean;
  first_seen: string;
  last_seen: string;
  status: string;
  attributes: Record<string, unknown>;
  total_detections: number;
  max_confidence: number;
};

const EVENT_TYPES = ["face", "person", "plate"] as const;

export async function GET() {
  try {
    const resp = await fetch(`${backend("/api/events")}?limit=500`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`FastAPI returned ${resp.status}`);
    const payload = (await resp.json()) as { events?: BackendSighting[] };
    const sightings = (payload.events ?? []).filter(
      (e) => Boolean(e.first_seen) && Boolean(e.last_seen),
    );
    const now = Date.now();
    const recent7d = sightings.filter(
      (e) => now - new Date(e.last_seen).getTime() <= 7 * 86_400_000,
    );
    const recent14d = sightings.filter(
      (e) => now - new Date(e.last_seen).getTime() <= 14 * 86_400_000,
    );

    const dailyMap = new Map<string, Record<string, string | number>>();
    for (const s of recent14d) {
      const day = s.first_seen.slice(0, 10);
      const row = dailyMap.get(day) ?? { day };
      row[s.class_name] = Number(row[s.class_name] ?? 0) + 1;
      dailyMap.set(day, row);
    }

    const hourly = Array.from({ length: 24 }, (_, hour) => ({ hour } as Record<string, number>));
    for (const s of recent7d) {
      const hour = new Date(s.first_seen).getHours();
      hourly[hour][s.class_name] = Number(hourly[hour][s.class_name] ?? 0) + 1;
    }
    for (const row of hourly) {
      for (const type of EVENT_TYPES) {
        row[type] = Math.round((Number(row[type] ?? 0) / 7) * 10) / 10;
      }
    }

    const classMap = new Map<string, { n: number; confidence: number }>();
    for (const s of recent7d) {
      const item = classMap.get(s.class_name) ?? { n: 0, confidence: 0 };
      item.n += 1;
      item.confidence += s.max_confidence || 0;
      classMap.set(s.class_name, item);
    }
    const classes = [...classMap.entries()]
      .map(([k, v]) => ({
        k,
        n: v.n,
        avg_conf: Math.round((v.confidence / Math.max(1, v.n)) * 10_000) / 10_000,
      }))
      .sort((a, b) => b.n - a.n);

    const confidence_hist = Array.from({ length: 10 }, (_, i) => ({ b: i + 1, n: 0 }));
    for (const s of recent7d) {
      const bucket = Math.max(1, Math.min(10, Math.ceil(((s.max_confidence || 0.5) - 0.5) * 20)));
      confidence_hist[bucket - 1].n += 1;
    }

    const uniqueIdentities = new Set(
      recent7d.map((s) => s.identity).filter((x): x is string => Boolean(x)),
    );

    const camCounts = new Map<string, number>();
    for (const s of recent7d) camCounts.set(s.camera_code, (camCounts.get(s.camera_code) ?? 0) + 1);
    const cameras = [...camCounts.entries()].map(([code, n]) => ({
      code,
      name: code,
      status: "active" as const,
      n,
    }));

    return Response.json({
      totals: {
        events_7d: recent7d.length,
        unique_tracks: uniqueIdentities.size,
        avg_per_hour: Math.round((recent7d.length / 168) * 10) / 10,
      },
      daily: [...dailyMap.values()].sort((a, b) => String(a.day).localeCompare(String(b.day))),
      hourly,
      classes,
      cameras,
      confidence_hist,
      generated_at: new Date().toISOString(),
    });
  } catch (error) {
    return Response.json({ error: "backend_stats_unavailable", detail: String(error) }, { status: 503 });
  }
}