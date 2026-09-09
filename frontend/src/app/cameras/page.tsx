"use client";

import clsx from "clsx";
import { ArrowUpRight, Cctv, PauseCircle, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CountUp, Panel, SectionTag, StatusDot } from "@/components/ui";

interface Cam {
  code: string;
  name: string;
  zone: string;
  status: string;
  stream_type: string;
  resolution: string;
  fps: number;
  events_24h: number;
}

const STATUS_META: Record<string, { tone: string; label: string }> = {
  active: { tone: "signal", label: "ACTIVE" },
  maintenance: { tone: "flare", label: "MAINTENANCE" },
  offline: { tone: "alert", label: "OFFLINE" },
};

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Cam[]>([]);
  const [busyCode, setBusyCode] = useState<string | null>(null);

  const load = () => {
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => setCameras(d.cameras ?? []))
      .catch(() => {});
  };

  useEffect(load, []);

  const setStatus = (cam: Cam, status: string) => {
    setBusyCode(cam.code);
    fetch("/api/cameras", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: cam.code, status }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.camera) {
          setCameras((prev) =>
            prev.map((c) =>
              c.code === cam.code ? { ...c, status: d.camera.status } : c,
            ),
          );
        }
      })
      .catch(() => {})
      .finally(() => setBusyCode(null));
  };

  const online = cameras.filter((c) => c.status === "active").length;

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <SectionTag index="C1" label="CAMERA FLEET" />
            <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              Four eyes on the <span className="text-signal text-glow">perimeter</span>
            </h1>
          </div>
          <div className="flex items-center gap-3 border border-edge bg-panel px-4 py-3 font-mono text-[10px] tracking-[0.2em]">
            <StatusDot tone="signal" />
            <span className="text-pale">
              ONLINE <CountUp value={online} className="text-signal" /> / {cameras.length}
            </span>
          </div>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {cameras.map((c) => {
            const meta = STATUS_META[c.status] ?? STATUS_META.offline;
            return (
              <Panel key={c.code} className="overflow-hidden" bracket>
                <div className="relative aspect-[16/7] overflow-hidden bg-abyss">
                  <div
                    className={clsx(
                      "absolute inset-0 bg-gradient-to-br transition-all duration-700",
                      c.code === "CAM-01"
                        ? "from-[#123] via-[#0c1a26] to-[#07141f]"
                        : "from-[#1a1626] via-[#131022] to-[#0b0916]",
                      c.status !== "active" && "opacity-40 saturate-50",
                    )}
                  />
                  <div className="absolute inset-0 scanlines" />
                  <div className="absolute inset-0 bg-gradient-to-t from-ink via-transparent to-ink/40" />
                  <div className="absolute bottom-4 right-4 font-mono text-[9px] tracking-[0.28em] text-signal/50">
                    {c.code === "CAM-01" ? "LIVE FEED" : "SIMULATED SOURCE"}
                  </div>
                  <div className="absolute left-3 top-3 flex items-center gap-2">
                    <span
                      className={clsx(
                        "flex items-center gap-1.5 border px-2 py-1 font-mono text-[9px] tracking-[0.22em] backdrop-blur-sm",
                        meta.tone === "signal" && "border-signal/40 bg-signal/10 text-signal",
                        meta.tone === "flare" && "border-flare/40 bg-flare/10 text-flare",
                        meta.tone === "alert" && "border-alert/40 bg-alert/10 text-alert",
                      )}
                    >
                      <StatusDot tone={meta.tone} ping={c.status === "active"} />
                      {meta.label}
                    </span>
                  </div>
                  <div className="absolute right-3 top-3 border border-edge bg-ink/70 px-2 py-1 font-mono text-[9px] tracking-[0.18em] text-mist backdrop-blur-sm">
                    {c.stream_type.toUpperCase()} · {c.fps}FPS
                  </div>
                  <div className="absolute bottom-3 left-4">
                    <div className="font-mono text-xl font-bold tracking-[0.16em] text-pale">
                      {c.code}
                    </div>
                    <div className="font-mono text-[11px] tracking-[0.14em] text-signal">
                      {c.name.toUpperCase()}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-4 divide-x divide-edge border-t border-edge bg-abyss/60 text-center">
                  {[
                    { k: "ZONE", v: c.zone.split("·")[0].trim() },
                    { k: "RES", v: c.resolution },
                    { k: "STREAM", v: c.stream_type.toUpperCase() },
                    { k: "EVT 24H", v: c.events_24h.toLocaleString() },
                  ].map((s) => (
                    <div key={s.k} className="px-2 py-3">
                      <div className="font-mono text-[8px] tracking-[0.22em] text-mist">{s.k}</div>
                      <div className="mt-1 truncate font-mono text-[11px] font-bold text-pale">
                        {s.v}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center gap-2 border-t border-edge p-3">
                  <Link
                    href={`/console?cam=${c.code}`}
                    className="flex flex-1 items-center justify-center gap-2 border border-signal/50 bg-signal/10 px-3 py-2.5 font-mono text-[10px] font-bold tracking-[0.2em] text-signal transition-colors hover:bg-signal hover:text-ink"
                  >
                    <Cctv className="h-3.5 w-3.5" />
                    OPEN FEED
                    <ArrowUpRight className="h-3 w-3" />
                  </Link>
                  {c.status === "active" ? (
                    <button
                      disabled={busyCode === c.code}
                      onClick={() => setStatus(c, "maintenance")}
                      className="flex items-center gap-2 border border-edge px-3 py-2.5 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:border-flare/50 hover:text-flare disabled:opacity-40"
                    >
                      <PauseCircle className="h-3.5 w-3.5" />
                      MAINTAIN
                    </button>
                  ) : (
                    <button
                      disabled={busyCode === c.code}
                      onClick={() => setStatus(c, "active")}
                      className="flex items-center gap-2 border border-edge px-3 py-2.5 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:border-signal/50 hover:text-signal disabled:opacity-40"
                    >
                      <Wrench className="h-3.5 w-3.5" />
                      ACTIVATE
                    </button>
                  )}
                </div>
              </Panel>
            );
          })}
        </div>

        <p className="mt-6 font-mono text-[10px] leading-relaxed tracking-[0.12em] text-mist">
          STATUS CHANGES PERSIST TO MONGO VIA <span className="text-frost">PATCH /api/cameras</span>.
          CAM-01 IS THE REAL WEBCAM — CAM-02…CAM-04 ARE SEEDED SIMULATED SOURCES IN THE REFERENCE DEPLOYMENT.
        </p>
      </div>
    </main>
  );
}