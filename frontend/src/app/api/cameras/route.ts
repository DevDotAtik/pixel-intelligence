import { proxyGet, backend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyGet("/api/cameras");
}

export async function PATCH(req: Request) {
  try {
    const body = (await req.json()) as { code?: string; status?: string };
    const code = body.code;
    const status = body.status;
    if (!code || !["active", "maintenance", "offline"].includes(status ?? "")) {
      return Response.json(
        { error: "invalid_request", detail: "expected { code: string, status: 'active' | 'maintenance' | 'offline' }" },
        { status: 400 },
      );
    }
    const resp = await fetch(
      backend(`/api/cameras/${encodeURIComponent(code)}?status=${status}`),
      { method: "PATCH", cache: "no-store" },
    );
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json({ error: "camera_update_failed", detail: String(error) }, { status: 503 });
  }
}