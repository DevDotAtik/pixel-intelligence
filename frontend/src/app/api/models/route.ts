import { MODELS, RUNTIME_CONFIG } from "@/lib/sim";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({
    models: MODELS.map((m) => ({
      ...m,
      exists: m.status === "online",
      path: `/backend/${m.file}`,
    })),
    configuration: {
      confidence_threshold: RUNTIME_CONFIG.confidenceThreshold,
      camera_index: RUNTIME_CONFIG.cameraIndex,
      resolution: RUNTIME_CONFIG.resolution,
      device: RUNTIME_CONFIG.device,
      process_every_n_frames: RUNTIME_CONFIG.processEveryNFrames,
      face_model_exists: true,
      object_model_exists: true,
      plate_model_exists: false,
    },
  });
}
