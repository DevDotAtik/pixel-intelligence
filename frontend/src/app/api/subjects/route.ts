import { proxyGet } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const limit = searchParams.get("limit") ?? "50";
  return proxyGet("/api/subjects", { limit });
}