import { DJANGO_URL } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/**
 * Same-origin proxy for the Django camera snapshot. It lets the registration
 * page share the server-owned webcam without browser CORS/device-lock issues.
 */
export async function GET(req: Request) {
  const camera = new URL(req.url).searchParams.get("camera") ?? "CAM-01";
  try {
    const response = await fetch(`${DJANGO_URL}/video/snapshot/?camera=${encodeURIComponent(camera)}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      const detail = await response.text();
      return Response.json({ error: "camera_unavailable", detail }, { status: response.status });
    }
    return new Response(await response.arrayBuffer(), {
      status: 200,
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store, max-age=0" },
    });
  } catch (error) {
    return Response.json({ error: "camera_unavailable", detail: String(error) }, { status: 503 });
  }
}
