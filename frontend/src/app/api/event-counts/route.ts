import { proxyGet } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyGet("/api/event-counts");
}