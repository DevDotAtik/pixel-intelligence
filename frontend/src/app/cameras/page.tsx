"use client";

import clsx from "clsx";
import { ArrowUpRight, Cctv, PauseCircle, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CountUp, Panel, SectionTag, StatusDot } from "@/components/ui";

interface Cam {
  id: number;
  code: string;
  name: string;
  zone: string;
  status: string;
  streamType: string;
  resolution: string;
  fps: number;
  uptime: number;
  image: string;
  events_24h: number;
}

const STATUS_META: Record<string, { tone: string; label: string }> = {
  active: { tone: "signal", label: "ACTIVE" },
  maintenance: { tone: "flare", label: "MAINTENANCE" },
  offline: { tone: "alert", label: "OFFLINE" },
};

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Cam[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [online, setOnline] = useState(0);

  const load = () => {
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => {
        setCameras(d.cameras ?? []);
        setOnline(d.online ?? 0);
      })
      .catch(() => {});
  };

  useEffect(load, []);

  const setStatus = (cam: Cam, status: string) => {
    setBusyId(cam.id);
    fetch("/api/cameras", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: cam.id, status }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.camera) {
          setCameras((prev) =>
            prev.map((c) => (c.id === cam.id ? { ...c, status: d.camera.status } : c)),
          );
          setOnline((o) =>
            status === "active"
              ? Math.min(cameras.length, o + 1)
              : cam.status === "active"
                ? Math.max(0, o - 1)
                : o,
          );
        }
      })
      .catch(() => {})
      .finally(() => setBusyId(null));
  };

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
              <Panel key={c.id} className="overflow-hidden" bracket>
                <div className="relative aspect-[16/7] overflow-hidden bg-abyss">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={c.image}
                    alt={c.name}
                    className={clsx(
                      "h-full w-full object-cover transition-all duration-700",
                      c.status !== "active" && "opacity-40 saturate-50",
                    )}
                  />
                  <div className="absolute inset-0 scanlines" />
                  <div className="absolute inset-0 bg-gradient-to-t from-ink via-transparent to-ink/40" />
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
                    {c.streamType.toUpperCase()} · {c.fps}FPS
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
                    { k: "UPTIME", v: `${c.uptime.toFixed(1)}%` },
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
                      disabled={busyId === c.id}
                      onClick={() => setStatus(c, "maintenance")}
                      className="flex items-center gap-2 border border-edge px-3 py-2.5 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:border-flare/50 hover:text-flare disabled:opacity-40"
                    >
                      <PauseCircle className="h-3.5 w-3.5" />
                      MAINTAIN
                    </button>
                  ) : (
                    <button
                      disabled={busyId === c.id}
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
          STATUS CHANGES PERSIST TO POSTGRES VIA <span className="text-frost">PATCH /api/cameras</span>.
          IN THE REFERENCE DEPLOYMENT EACH STREAM WOULD BE AN AUTHORIZED RTSP SOURCE — HERE, A SIMULATED FRAME STORE.
        </p>
      </div>
    </main>
  );
}
