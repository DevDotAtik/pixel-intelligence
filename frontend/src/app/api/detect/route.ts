import { CLASS_GROUP, GROUP_EVENT, RUNTIME_CONFIG } from "@/lib/sim";

export const dynamic = "force-dynamic";

const CLASSES: Array<[string, number]> = [
  ["person", 0.36],
  ["face", 0.22],
  ["car", 0.18],
  ["truck", 0.1],
  ["motorbike", 0.06],
  ["bus", 0.04],
  ["backpack", 0.04],
];

function pick(r: number): string {
  let acc = 0;
  for (const [c, w] of CLASSES) {
    acc += w;
    if (r <= acc) return c;
  }
  return "person";
}

/**
 * POST /api/detect
 * Simulated YOLO inference pass over a single frame.
 * Accepts an optional JSON body { scenario?: "random" | "crowd" | "empty" | "convoy" }.
 * Bounding boxes use [x, y, width, height] on a 1280x720 frame.
 */
export async function POST(req: Request) {
  let body: Record<string, unknown> = {};
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  const scenario =
    typeof body.scenario === "string" ? body.scenario : "random";

  let n = Math.floor(Math.random() * 4);
  if (scenario === "crowd") n = 5 + Math.floor(Math.random() * 4);
  if (scenario === "empty") n = 0;
  if (scenario === "convoy") n = 3 + Math.floor(Math.random() * 3);

  const vehicleBias = scenario === "convoy" ? ["car", "truck", "bus"] : null;

  const detections = Array.from({ length: n }, (_, i) => {
    const cls = vehicleBias
      ? vehicleBias[i % vehicleBias.length]
      : pick(Math.random());
    const confidence = Math.min(
      0.995,
      0.55 + Math.pow(Math.random(), 0.7) * 0.44,
    );
    const w = 60 + Math.floor(Math.random() * 260);
    const h = 80 + Math.floor(Math.random() * 280);
    return {
      class: cls,
      confidence: Math.round(confidence * 1000) / 1000,
      bbox: [
        Math.floor(Math.random() * (1280 - w)),
        Math.floor(Math.random() * (720 - h)),
        w,
        h,
      ],
      event_type: GROUP_EVENT[CLASS_GROUP[cls] ?? "object"],
      bbox_format: "xywh",
    };
  });

  const count = (group: string) =>
    detections.filter((d) => (CLASS_GROUP[d.class] ?? "object") === group)
      .length;

  return Response.json({
    detections,
    analytics: {
      face_count: count("face"),
      person_count: count("person"),
      vehicle_count: count("vehicle"),
      object_count: count("object"),
      total: detections.length,
    },
    inference_ms: Math.round((24 + n * 4.5 + Math.random() * 9) * 10) / 10,
    model: { face: "yolov8m-face.pt", object: "model.pt" },
    device: RUNTIME_CONFIG.device,
    resolution: RUNTIME_CONFIG.resolution,
    confidence_threshold: RUNTIME_CONFIG.confidenceThreshold,
  });
}
