import { backend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { stream_url?: string; stream_type?: string };
    const url = String(body.stream_url ?? "").trim();
    if (!url) {
      return Response.json({ error: "invalid_request", detail: "stream_url is required." }, { status: 400 });
    }
    const resp = await fetch(backend("/api/cameras/test"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json({ error: "camera_test_failed", detail: String(error) }, { status: 503 });
  }
}