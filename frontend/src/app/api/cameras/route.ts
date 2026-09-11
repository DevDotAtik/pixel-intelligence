import { backend, proxyGet } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyGet("/api/cameras");
}

/** Forward a JSON camera document to FastAPI (create or update). */
async function forward(method: string, path: string, body: unknown): Promise<Response> {
  try {
    const resp = await fetch(backend(path), {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json({ error: "camera_operation_failed", detail: String(error) }, { status: 503 });
  }
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as Record<string, unknown>;
    if (!String(body.name ?? "").trim()) {
      return Response.json({ error: "invalid_request", detail: "Camera name is required." }, { status: 400 });
    }
    return forward("POST", "/api/cameras", body);
  } catch {
    return Response.json({ error: "invalid_request", detail: "Expected a JSON camera document." }, { status: 400 });
  }
}

export async function PATCH(req: Request) {
  try {
    const body = (await req.json()) as Record<string, unknown>;
    const code = String(body.code ?? "").trim();
    if (!code) {
      return Response.json(
        { error: "invalid_request", detail: "expected { code: string, ...fields }" },
        { status: 400 },
      );
    }
    delete body.code;
    return forward("PATCH", `/api/cameras/${encodeURIComponent(code)}`, body);
  } catch {
    return Response.json({ error: "invalid_request", detail: "Expected a JSON camera document." }, { status: 400 });
  }
}

export async function DELETE(req: Request) {
  const code = new URL(req.url).searchParams.get("code") ?? "";
  if (!code) {
    return Response.json({ error: "invalid_request", detail: "expected a ?code= query param" }, { status: 400 });
  }
  return forward("DELETE", `/api/cameras/${encodeURIComponent(code)}`, undefined);
}