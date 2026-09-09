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
  runnable?: boolean;
  href?: string;
}

const GROUPS: Array<{ name: string; endpoints: Endpoint[] }> = [
  {
    name: "SYSTEM",
    endpoints: [
      {
        method: "GET",
        path: "/api/health",
        desc: "Liveness probe with MongoDB heartbeat.",
      },
      {
        method: "GET",
        path: "/api/models",
        desc: "Model registry (face / person / plate), installed weights and runtime configuration.",
      },
      {
        method: "GET",
        path: "/api/config",
        desc: "Live runtime tuning — inference size, thresholds, camera defaults.",
      },
    ],
  },
  {
    name: "INFERENCE",
    endpoints: [
      {
        method: "POST",
        path: "/api/detect",
        desc: "Single-frame detection pass, multipart/form-data. Returns bboxes in [x, y, w, h] with identity, clothing and timeline action.",
        params: [
          ["image_data", "image file (faces, scene, plate…)"],
          ["model", "face | person | plate"],
          ["camera_code", "CAM-01 … CAM-04"],
        ],
        runnable: false,
      },
    ],
  },
  {
    name: "IDENTITY",
    endpoints: [
      {
        method: "POST",
        path: "/api/registrations",
        desc: "Enrol a person — multipart/form-data with a clear face photo. Stored as a 64-dim embedding in Mongo.",
        params: [
          ["image_data", "face photo file"],
          ["name", "display name"],
          ["notes", "optional notes"],
        ],
        runnable: false,
      },
      {
        method: "GET",
        path: "/api/registrations",
        desc: "Registered people and their enrolment date.",
      },
      {
        method: "GET",
        path: "/api/subjects",
        desc: "Identity aggregate per tracked subject — registered flag, sighting count, last seen, camera.",
      },
    ],
  },
  {
    name: "LEDGER",
    endpoints: [
      {
        method: "GET",
        path: "/api/events?limit=25",
        desc: "Deduplicated subject sightings — one entry per reappearance.",
        params: [
          ["camera", "CAM-01 … CAM-04 | all"],
          ["limit / offset", "pagination (limit max 200)"],
        ],
      },
      {
        method: "GET",
        path: "/api/event-counts",
        desc: "All-time sighting counts by class.",
      },
      {
        method: "GET",
        path: "/api/stats",
        desc: "Analytics bundle: per-class totals, daily/hourly rhythms, confidence histogram, per-camera counts.",
      },
    ],
  },
  {
    name: "FLEET",
    endpoints: [
      {
        method: "GET",
        path: "/api/cameras",
        desc: "Camera registry (seeded CAM-01…CAM-04) with 24h sighting volumes.",
      },
      {
        method: "PATCH",
        path: "/api/cameras",
        desc: "Flip a camera between active / maintenance / offline.",
        runnable: false,
        body: { code: "CAM-02", status: "active" },
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
    fetch(ep.path, { method: ep.method, cache: "no-store" })
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
          These endpoints mirror the FastAPI service one-to-one — the Next.js
          route handlers proxy straight to it. Every response below is generated
          live against the running backend and its MongoDB ledger — press
          <span className="mx-1 font-mono text-[11px] text-signal">RUN</span>
          to execute a real GET request.
        </p>

        <div className="mt-6 flex items-center gap-3 border border-edge bg-panel px-4 py-3 font-mono text-[10px] tracking-[0.16em] text-mist">
          <Terminal className="h-3.5 w-3.5 text-signal" />
          <span>BASE URL</span>
          <span className="text-pale">http://127.0.0.1:8000</span>
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
                      {ep.runnable !== false ? (
                        <button
                          onClick={() => run(ep)}
                          disabled={running === key}
                          className="ml-auto flex items-center gap-2 border border-signal/50 bg-signal/10 px-3 py-1.5 font-mono text-[10px] font-bold tracking-[0.18em] text-signal transition-colors hover:bg-signal hover:text-ink disabled:opacity-40"
                        >
                          <Play className={clsx("h-3 w-3", running === key && "animate-pulse")} />
                          {running === key ? "RUNNING" : "RUN"}
                        </button>
                      ) : (
                        <span className="ml-auto font-mono text-[9px] tracking-[0.2em] text-mist">
                          MULTIPART / BODY — RUN FROM APP OR CURL
                        </span>
                      )}
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