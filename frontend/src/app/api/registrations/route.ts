import { proxyGet, proxyPost } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyGet("/api/registrations");
}

export async function POST(req: Request) {
  try {
    const form = await req.formData();
    const resp = await fetch(new URL("/api/registrations", process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://127.0.0.1:8000"), {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json({ error: "registration_failed", detail: String(error) }, { status: 503 });
  }
}