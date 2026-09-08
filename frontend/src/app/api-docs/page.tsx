"use client";

import clsx from "clsx";
import { Braces, Play, Terminal } from "lucide-react";
import { useState } from "react";
import { Panel, SectionTag, StatusDot } from "@/components/ui";

interface Endpoint {
  method: "GET" | "POST" | "PATCH";
  path: string;
  desc: string;
  params?: Array<[string, string]>;
  body?: unknown;
}

const GROUPS: Array<{ name: string; endpoints: Endpoint[] }> = [
  {
    name: "SYSTEM",
    endpoints: [
      {
        method: "GET",
        path: "/api/health",
        desc: "Liveness probe with Postgres round-trip latency.",
      },
      {
        method: "GET",
        path: "/api/models",
        desc: "YOLO model registry, weights paths and runtime configuration.",
      },
    ],
  },
  {
    name: "INFERENCE",
    endpoints: [
      {
        method: "POST",
        path: "/api/detect",
        desc: "Single-frame detection pass. Optional body { scenario }. BBox format [x, y, w, h] on a 1280×720 frame.",
        params: [["scenario", "\"random\" | \"crowd\" | \"empty\" | \"convoy\""]],
        body: { scenario: "crowd" },
      },
    ],
  },
  {
    name: "LEDGER",
    endpoints: [
      {
        method: "GET",
        path: "/api/events?limit=5",
        desc: "Paginated event ledger. Filters: camera, class, type, min_conf, track, limit, offset.",
        params: [
          ["camera", "CAM-01 … CAM-04 | all"],
          ["class", "person | face | vehicle | object | class name"],
          ["type", "FACE_DETECTED | PERSON_DETECTED | …"],
          ["limit / offset", "pagination (max 200)"],
        ],
      },
      {
        method: "POST",
        path: "/api/events",
        desc: "Append detection events (what the live console calls every ~2.5s).",
        body: {
          events: [
            {
              event_type: "PERSON_DETECTED",
              class_name: "person",
              confidence: 0.93,
              tracking_id: 42,
              camera: "CAM-01",
            },
          ],
        },
      },
      {
        method: "GET",
        path: "/api/event-counts",
        desc: "All-time event totals grouped by type, plus last-24h volume.",
      },
      {
        method: "GET",
        path: "/api/stats",
        desc: "Analytics bundle: 14-day trend, diurnal rhythm, class mix, camera leaders, confidence histogram.",
      },
    ],
  },
  {
    name: "FLEET",
    endpoints: [
      {
        method: "GET",
        path: "/api/cameras",
        desc: "Camera registry with 24h event volumes and online counts.",
      },
      {
        method: "PATCH",
        path: "/api/cameras",
        desc: "Update camera status.",
        params: [["status", "active | maintenance | offline"]],
        body: { id: 3, status: "active" },
      },
    ],
  },
];

const METHOD_CLS: Record<string, string> = {
  GET: "border-signal/50 bg-signal/10 text-signal",
  POST: "border-flare/50 bg-flare/10 text-flare",
  PATCH: "border-frost/50 bg-frost/10 text-frost",
};

interface RunResult {
  status: number;
  ms: number;
  json: string;
}

export default function ApiDocsPage() {
  const [results, setResults] = useState<Record<string, RunResult>>({});
  const [running, setRunning] = useState<string | null>(null);

  const run = (ep: Endpoint) => {
    const key = ep.method + ep.path;
    setRunning(key);
    // This handler runs only after a user click; the timestamp measures the API request.
    // eslint-disable-next-line react-hooks/purity
    const t0 = performance.now();
    const cleanPath = ep.path;
    fetch(cleanPath, {
      method: ep.method,
      headers: ep.body ? { "Content-Type": "application/json" } : undefined,
      body: ep.body ? JSON.stringify(ep.body) : undefined,
    })
      .then(async (r) => {
        const ms = Math.round(performance.now() - t0);
        const text = JSON.stringify(await r.json(), null, 2);
        setResults((prev) => ({
          ...prev,
          [key]: { status: r.status, ms, json: text },
        }));
      })
      .catch((e) =>
        setResults((prev) => ({
          ...prev,
          [key]: { status: 0, ms: 0, json: String(e) },
        })),
      )
      .finally(() => setRunning(null));
  };

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
        <SectionTag index="D1" label="API REFERENCE" />
        <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
          Contracts, <span className="text-signal text-glow">executable</span>
        </h1>
        <p className="mt-4 max-w-2xl leading-relaxed text-pale/70">
          These endpoints mirror the reference FastAPI service one-to-one. Every
          response below is generated live against the running backend and its
          Postgres ledger — press
          <span className="mx-1 font-mono text-[11px] text-signal">RUN</span>
          to execute a real request.
        </p>

        <div className="mt-6 flex items-center gap-3 border border-edge bg-panel px-4 py-3 font-mono text-[10px] tracking-[0.16em] text-mist">
          <Terminal className="h-3.5 w-3.5 text-signal" />
          <span>BASE URL</span>
          <span className="text-pale">https://your-deployment</span>
          <StatusDot tone="signal" className="ml-auto" />
          <span className="text-signal">OPERATIONAL</span>
        </div>

        {GROUPS.map((g) => (
          <section key={g.name} className="mt-10">
            <div className="mb-3 flex items-center gap-3">
              <span className="font-mono text-[10px] tracking-[0.3em] text-mist">
                {g.name}
              </span>
              <span className="h-px flex-1 bg-edge" />
            </div>
            <div className="space-y-4">
              {g.endpoints.map((ep) => {
                const key = ep.method + ep.path;
                const res = results[key];
                return (
                  <Panel key={key} className="overflow-hidden" bracket={false}>
                    <div className="flex flex-wrap items-center gap-3 border-b border-edge bg-abyss/60 px-4 py-3">
                      <span
                        className={clsx(
                          "border px-2 py-1 font-mono text-[10px] font-bold tracking-[0.14em]",
                          METHOD_CLS[ep.method],
                        )}
                      >
                        {ep.method}
                      </span>
                      <code className="font-mono text-[12px] font-bold text-pale">
                        {ep.path}
                      </code>
                      <button
                        onClick={() => run(ep)}
                        disabled={running === key}
                        className="ml-auto flex items-center gap-2 border border-signal/50 bg-signal/10 px-3 py-1.5 font-mono text-[10px] font-bold tracking-[0.18em] text-signal transition-colors hover:bg-signal hover:text-ink disabled:opacity-40"
                      >
                        <Play className={clsx("h-3 w-3", running === key && "animate-pulse")} />
                        {running === key ? "RUNNING" : "RUN"}
                      </button>
                    </div>
                    <div className="px-4 py-3">
                      <p className="text-sm leading-relaxed text-pale/70">{ep.desc}</p>
                      {ep.params && (
                        <div className="mt-3 overflow-x-auto">
                          <table className="w-full min-w-[380px] text-left font-mono text-[10px]">
                            <tbody>
                              {ep.params.map(([k, v]) => (
                                <tr key={k} className="border-t border-edge/50">
                                  <td className="py-1.5 pr-4 text-frost">{k}</td>
                                  <td className="py-1.5 text-mist">{v}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      {ep.body != null && (
                        <pre className="mt-3 overflow-x-auto border border-edge/60 bg-abyss p-3 font-mono text-[10px] leading-relaxed text-flare/90">
{JSON.stringify(ep.body, null, 2)}
                        </pre>
                      )}
                      {res && (
                        <div className="mt-3">
                          <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.14em]">
                            <span
                              className={clsx(
                                "border px-2 py-0.5",
                                res.status >= 200 && res.status < 300
                                  ? "border-signal/50 text-signal"
                                  : "border-alert/50 text-alert",
                              )}
                            >
                              {res.status || "ERR"}
                            </span>
                            <span className="text-mist">{res.ms} MS</span>
                            <span className="flex items-center gap-1 text-mist">
                              <Braces className="h-3 w-3" /> APPLICATION/JSON
                            </span>
                          </div>
                          <pre className="mt-2 max-h-72 overflow-auto border border-edge/60 bg-ink p-3 font-mono text-[10px] leading-relaxed text-pale/80">
{res.json}
                          </pre>
                        </div>
                      )}
                    </div>
                  </Panel>
                );
              })}
            </div>
          </section>
        ))}

        <div className="mt-12 border border-edge bg-abyss/60 p-5 font-mono text-[10px] leading-relaxed tracking-[0.1em] text-mist">
          INTEGRATION NOTE — A DJANGO (OR ANY) FRONTEND CONSUMES THESE CONTRACTS
          OVER HTTP. NOTHING HERE IS COUPLED TO THE SIMULATION; POINTING THE
          SAME CONTRACTS AT A YOLO-BACKED FASTAPI WORKER REQUIRES NO UI CHANGES.
        </div>
      </div>
    </main>
  );
}
