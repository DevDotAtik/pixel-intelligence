import { db } from "@/db";
import { cameras, events } from "@/db/schema";
import { sql } from "drizzle-orm";
import { CAMERA_PROFILES, GROUP_EVENT, groupOf } from "./sim";

let seedPromise: Promise<void> | null = null;

/** Idempotent lazy seed — safe to call from any route handler. */
export function ensureSeeded(): Promise<void> {
  if (!seedPromise) {
    seedPromise = seed().catch((err) => {
      seedPromise = null;
      throw err;
    });
  }
  return seedPromise;
}

const CLASS_MIX: Array<[string, number]> = [
  ["person", 0.44],
  ["face", 0.28],
  ["car", 0.12],
  ["truck", 0.07],
  ["motorbike", 0.03],
  ["bus", 0.02],
  ["backpack", 0.02],
  ["suitcase", 0.02],
];

const CAMERA_WEIGHTS = [0.26, 0.34, 0.18, 0.22];

function pickWeighted<T>(pairs: Array<[T, number]>, r: number): T {
  let acc = 0;
  for (const [v, w] of pairs) {
    acc += w;
    if (r <= acc) return v;
  }
  return pairs[pairs.length - 1][0];
}

function hourlyVolume(hour: number): number {
  // Diurnal border-activity curve: quiet nights, dusk surge.
  if (hour <= 5) return 6 + Math.random() * 10;
  if (hour <= 10) return 18 + Math.random() * 26;
  if (hour <= 16) return 24 + Math.random() * 30;
  if (hour <= 21) return 38 + Math.random() * 56;
  return 12 + Math.random() * 18;
}

async function seed() {
  const camRows = await db
    .select({ n: sql<number>`count(*)::int` })
    .from(cameras);
  const camCount = camRows[0]?.n ?? 0;

  const cameraIds = new Map<string, number>();

  if (camCount === 0) {
    const inserted = await db
      .insert(cameras)
      .values(
        CAMERA_PROFILES.map((p, i) => ({
          code: p.code,
          name: p.name,
          zone: p.zone,
          status: i === 2 ? "maintenance" : "active",
          streamType: p.streamType,
          resolution: "1280x720",
          fps: 30,
          uptime: 99.6 - i * 0.37,
          image: p.image,
        })),
      )
      .returning({ id: cameras.id, code: cameras.code });
    for (const row of inserted) cameraIds.set(row.code, row.id);
  } else {
    const all = await db
      .select({ id: cameras.id, code: cameras.code })
      .from(cameras);
    for (const row of all) cameraIds.set(row.code, row.id);
  }

  const evRows = await db
    .select({ n: sql<number>`count(*)::int` })
    .from(events);
  if ((evRows[0]?.n ?? 0) > 0) return;

  // Generate ~8 days of plausible detection history.
  const codes = CAMERA_PROFILES.map((p) => p.code);
  const now = Date.now();
  const HOUR = 3_600_000;
  const HOURS = 8 * 24;

  type Row = typeof events.$inferInsert;
  let batch: Row[] = [];
  const flush = async () => {
    if (batch.length === 0) return;
    const toInsert = batch;
    batch = [];
    await db.insert(events).values(toInsert);
  };

  for (let h = HOURS; h >= 1; h--) {
    const slotStart = now - h * HOUR;
    const hour = new Date(slotStart).getHours();
    const volume = Math.round(hourlyVolume(hour));
    for (let i = 0; i < volume; i++) {
      const className = pickWeighted(CLASS_MIX, Math.random());
      const camIndex = pickWeighted(
        CAMERA_WEIGHTS.map((w, idx) => [idx, w] as [number, number]),
        Math.random(),
      );
      const cameraId = cameraIds.get(codes[camIndex]);
      if (!cameraId) continue;
      const confidence = Math.min(
        0.995,
        0.52 + Math.pow(Math.random(), 0.6) * 0.47,
      );
      batch.push({
        timestamp: new Date(slotStart + Math.random() * HOUR),
        eventType: GROUP_EVENT[groupOf(className)],
        className,
        confidence: Math.round(confidence * 1000) / 1000,
        trackingId: 1 + Math.floor(Math.random() * 380),
        cameraId,
      });
      if (batch.length >= 1000) await flush();
    }
  }
  await flush();
}
