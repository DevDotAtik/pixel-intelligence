import { proxyGet } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const camera = searchParams.get("camera") ?? undefined;
  const limit = searchParams.get("limit") ?? "50";
  const offset = searchParams.get("offset") ?? "0";
  return proxyGet("/api/events", { camera, limit, offset });
}