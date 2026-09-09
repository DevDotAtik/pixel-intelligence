/* Shared server-side helper for proxying to the FastAPI backend. */

export const BACKEND_URL = (process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
export const DJANGO_URL = (process.env.NEXT_PUBLIC_DJANGO_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");

export function backend(path: string, params?: Record<string, string | undefined>): string {
  let url = `${BACKEND_URL}${path}`;
  if (params) {
    const qs = Object.entries(params)
      .filter(([, v]) => v)
      .map(([k, v]) => `${k}=${v}`)
      .join("&");
    if (qs) url += `?${qs}`;
  }
  return url;
}

/**
 * Proxy a GET request from a Next.js route handler to FastAPI.
 * Returns `Response` compatible with the Next.js App Router.
 */
export async function proxyGet(path: string, params?: Record<string, string | undefined>): Promise<Response> {
  try {
    const resp = await fetch(backend(path, params), { cache: "no-store" });
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json(
      { error: "backend_unavailable", detail: String(error) },
      { status: 503 },
    );
  }
}

/**
 * Proxy a POST with a JSON body to FastAPI.
 */
export async function proxyPost(path: string, body?: unknown): Promise<Response> {
  try {
    const resp = await fetch(backend(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const payload = await resp.json();
    return Response.json(payload, { status: resp.status });
  } catch (error) {
    return Response.json(
      { error: "backend_unavailable", detail: String(error) },
      { status: 503 },
    );
  }
}