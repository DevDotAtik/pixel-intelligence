"use client";

import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Cpu,
  Crosshair,
  Database,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  ScanEye,
  Square,
  Video,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CAMERA_PROFILES,
  GROUP_COLORS,
  GROUP_LABEL,
  MODELS,
  MODEL_COLORS,
  RUNTIME_CONFIG,
  type CameraProfile,
  type DetectionGroup,
} from "@/lib/sim";
import { Corners, Panel, StatusDot } from "@/components/ui";
import { CameraFeed, type FeedStats, type SimEvent } from "./feed-canvas";
import { BackendCameraFeed } from "./backend-camera-feed";

interface TickerEvent extends SimEvent {
  key: number;
}

type SessionCounts = Record<"face" | "person" | "plate" | "vehicle", number> & { total: number };

type RegisteredCamera = {
  code: string;
  name: string;
  zone: string;
  stream_type: string;
  stream_url: string;
  status: string;
};

/** A console tile: either from the static sim profiles or the live registry. */
type LiveProfile = Pick<CameraProfile, "code" | "name" | "zone" | "streamType"> & {
  /** True when the camera has a real source (registered URL or the CAM-01 device). */
  live: boolean;
};

const GROUP_ORDER: Array<"face" | "person" | "plate" | "vehicle"> = ["face", "person", "plate", "vehicle"];

function timeOf(iso: string) {
  try {
    const d = new Date(iso);
    const p = (n: number) => String(n).padStart(2, "0");
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  } catch {
    return "--:--:--";
  }
}

export function ConsoleClient({ initialCamCode }: { initialCamCode?: string }) {
  const [camIdx, setCamIdx] = useState(initialCamCode ? -1 : 0);
  const [model, setModel] = useState<string>("face");
  const [paused, setPaused] = useState(false);
  const [ticker, setTicker] = useState<TickerEvent[]>([]);
  const [session, setSession] = useState<SessionCounts>({
    face: 0,
    person: 0,
    plate: 0,
    vehicle: 0,
    total: 0,
  });
  const [stats, setStats] = useState<FeedStats | null>(null);
  const [camStatus, setCamStatus] = useState<Record<string, string>>({});
  const [clockNow, setClockNow] = useState(0);
  /** Registered cameras from the registry; null until the fetch settles. */
  const [registry, setRegistry] = useState<LiveProfile[] | null>(null);

  const seqRef = useRef(0);

  useEffect(() => {
    const timer = window.setInterval(() => setClockNow(Date.now()), 1000);
    const initial = window.setTimeout(() => setClockNow(Date.now()), 0);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => {
        const cams = (d.cameras ?? []) as RegisteredCamera[];
        if (!cams.length) return;
        const statuses: Record<string, string> = {};
        const list: LiveProfile[] = cams.map((c) => {
          statuses[c.code] = c.status;
          return {
            code: c.code,
            name: c.name,
            zone: c.zone,
            streamType: c.stream_type === "mjpeg" ? "mjpeg" : c.stream_type === "webcam" ? "webcam" : "rtsp",
            live: Boolean(c.stream_url) || c.code === "CAM-01",
          };
        });
        setCamStatus(statuses);
        setRegistry(list);
        setCamIdx((prev) => {
          const target = initialCamCode ? list.findIndex((p) => p.code === initialCamCode) : -1;
          if (target >= 0) return target;
          return prev === -1 ? 0 : prev;
        });
      })
      .catch(() => {});
  }, [initialCamCode]);

  useEffect(() => {
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => {
        const map: Record<string, string> = {};
        for (const c of d.cameras ?? []) map[c.code] = c.status;
        setCamStatus(map);
      })
      .catch(() => {});
  }, []);

  const handleEvent = useCallback((e: SimEvent) => {
    setTicker((prev) =>
      [{ ...e, key: ++seqRef.current }, ...prev].slice(0, 30),
    );
    setSession((s) => {
      const group = (
        { face: "face", person: "person", car: "vehicle", truck: "vehicle", bus: "vehicle", motorbike: "vehicle", plate: "plate" } as Record<string, "face" | "person" | "plate" | "vehicle">
      )[e.className];
      if (!group) return s;
      return { ...s, [group]: s[group] + 1, total: s.total + 1 };
    });
  }, []);

  const handleStats = useCallback((s: FeedStats) => setStats(s), []);

  const rate = useMemo(() => {
    const buckets = new Array(12).fill(0) as number[];
    const now = clockNow;
    for (const e of ticker) {
      const age = now - new Date(e.at).getTime();
      const b = Math.floor(age / 5000);
      if (b >= 0 && b < 12) buckets[11 - b]++;
    }
    return buckets;
  }, [ticker, clockNow]);
  const maxRate = Math.max(1, ...rate);

  /** Tile list — the live registry when available, otherwise the static sim fleet. */
  const list = (registry ?? CAMERA_PROFILES) as Array<LiveProfile | CameraProfile>;
  const viewIdx = Math.max(0, Math.min(camIdx, list.length - 1));
  const liveOf = (p: LiveProfile | CameraProfile, i: number) =>
    registry ? (p as LiveProfile).live : i === 0;
  const profile = list[viewIdx];

  const resetSession = () => {
    setTicker([]);
    setSession({ face: 0, person: 0, plate: 0, vehicle: 0, total: 0 });
  };

  return (
    <main className="min-h-[calc(100vh-3.5rem)] w-full pt-14">
      <div className="mx-auto w-full max-w-none px-4 py-5 sm:px-6 lg:px-8">
        {/* header */}
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 font-mono text-[11px] tracking-[0.32em] text-mist">
              <span className="text-signal">02</span>
              <span className="h-px w-9 bg-edge2" />
              <span>LIVE CONSOLE</span>
            </div>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Surveillance <span className="text-glow text-signal">Grid</span>
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center border border-edge bg-panel font-mono text-[10px] tracking-[0.18em]">
              {MODELS.map((m) => {
                const active = model === m.key;
                const color = MODEL_COLORS[m.key] ?? "#a78bfa";
                return (
                  <button
                    key={m.key}
                    onClick={() => setModel(m.key)}
                    title={m.note}
                    className={clsx(
                      "flex items-center gap-1.5 border-l border-edge px-3 py-2 transition-colors first:border-l-0",
                      active ? "text-pale" : "text-mist hover:text-pale",
                    )}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-[1px]"
                      style={{ backgroundColor: active ? color : "#3a4660" }}
                    />
                    {m.name.toUpperCase()}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setPaused((p) => !p)}
              className="flex items-center gap-2 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.18em] text-pale transition-colors hover:border-signal/50 hover:text-signal"
            >
              {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
              {paused ? "RESUME" : "PAUSE"}
            </button>
            <button
              onClick={resetSession}
              className="flex items-center gap-2 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:text-pale"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              RESET SESSION
            </button>
          </div>
        </div>

        <div className="grid min-w-0 gap-4 lg:grid-cols-12 lg:items-start">
          {/* feed column */}
          <div className="min-w-0 space-y-4 lg:col-span-9">
            <Panel bracket tone="border-signal/50" className="bg-abyss/90">
              <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
                <div className="flex items-center gap-3">
                    <Video className="h-4 w-4 text-signal" />
                    <span className="font-mono text-xs font-bold tracking-[0.22em] text-pale">
                      {profile.code}
                    </span>
                    <span className="font-mono text-[11px] tracking-[0.14em] text-mist">
                      {profile.name.toUpperCase()} · {profile.zone.toUpperCase()}
                    </span>
                  </div>
                  {paused && (
                    <span className="font-mono text-[10px] tracking-[0.18em] text-flare">PAUSED</span>
                  )}
              </div>

              {liveOf(profile, viewIdx) ? (
                <BackendCameraFeed
                  key={`backend-cam-${profile.code ?? "?"}-${model}`}
                  profile={profile as CameraProfile}
                  model={model}
                  paused={paused}
                  onEvent={handleEvent}
                  onStats={handleStats}
                  className="aspect-video w-full"
                />
              ) : (
                <div className="grid aspect-video w-full place-items-center bg-abyss font-mono text-xs tracking-[0.2em] text-mist">
                  {profile?.code ?? "CAM-?"} · NO STREAM SOURCE
                  <br />
                  <span className="mt-2 inline-block text-[10px] text-mist/60">
                    ADD AN RTSP/MJPEG URL IN THE CAMERA FLEET PAGE
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between gap-3 border-t border-edge px-4 py-2.5 font-mono text-[10px] tracking-[0.16em] text-mist">
                <div className="flex items-center gap-2">
                  <Crosshair className="h-3.5 w-3.5 text-signal" />
                  <span>MODEL: {MODELS.find((m) => m.key === model)?.name.toUpperCase() ?? "FACE"}</span>
                </div>
              </div>
            </Panel>

            {/* camera thumbs */}
            <div className="grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-4">
              {list.map((p, i) => {
                const active = i === viewIdx;
                const live = liveOf(p, i);
                const status = registry
                  ? camStatus[p.code] ?? (live ? "active" : "offline")
                  : i === 0
                    ? camStatus[p.code] ?? "active"
                    : "offline";
                return (
                  <button
                    key={p.code}
                    onClick={() => setCamIdx(i)}
                    className={clsx(
                      "group relative border text-left transition-all",
                      active
                        ? "border-signal/60 panel-glow"
                        : "border-edge hover:border-edge2 opacity-80 hover:opacity-100",
                    )}
                  >
                    {registry === null && i === 0 ? (
                      <CameraFeed profile={p as CameraProfile} compact live={false} className="aspect-video w-full" />
                    ) : (
                      <div className="grid aspect-video w-full place-items-center bg-abyss font-mono text-[10px] tracking-[0.18em] text-mist">
                        {live ? (
                          <span className="flex items-center gap-2 text-signal">
                            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal" />
                            LIVE
                          </span>
                        ) : (
                          "NO FEED"
                        )}
                      </div>
                    )}
                    <div className="flex items-center justify-between border-t border-edge bg-panel/90 px-2 py-1.5">
                      <span className={clsx("font-mono text-[10px] font-bold tracking-[0.14em]", active ? "text-signal" : "text-pale")}>
                        {p.code}
                      </span>
                      <StatusDot
                        tone={status === "active" ? "signal" : status === "maintenance" ? "flare" : "alert"}
                        ping={status === "active"}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* right column */}
          <div className="min-w-0 space-y-4 lg:col-span-3">
            <Panel className="p-4">
              <PanelTitle icon={<ScanEye className="h-3.5 w-3.5" />} label="IN FRAME — CURRENT COUNT" />
              <div className="mt-3 grid grid-cols-2 gap-2">
                {GROUP_ORDER.map((g) => (
                  <div key={g} className="border border-edge bg-abyss/70 p-3">
                    <div className="flex items-center gap-1.5 font-mono text-[9px] tracking-[0.2em] text-mist">
                      <span className="h-1.5 w-1.5 rounded-[1px]" style={{ backgroundColor: GROUP_COLORS[g] }} />
                      {GROUP_LABEL[g].toUpperCase()}
                    </div>
                    <div className="mt-1 font-mono text-3xl font-bold tabular-nums" style={{ color: GROUP_COLORS[g] }}>
                      {stats ? String(stats.counts[g]).padStart(2, "0") : "—"}
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-3 font-mono text-[9px] leading-relaxed tracking-[0.08em] text-mist">
                CURRENT = OBJECTS VISIBLE NOW. EVENTS = UNIQUE TRACKED IDs LOGGED.
              </p>
            </Panel>

            <Panel className="p-4">
              <PanelTitle icon={<Gauge className="h-3.5 w-3.5" />} label="PIPELINE TELEMETRY" />
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="border border-edge bg-abyss/70 p-3">
                  <div className="font-mono text-[9px] tracking-[0.2em] text-mist">FPS</div>
                  <div className="mt-1 font-mono text-2xl font-bold text-signal tabular-nums">
                    {stats ? stats.fps.toFixed(1) : "—"}
                  </div>
                </div>
                <div className="border border-edge bg-abyss/70 p-3">
                  <div className="font-mono text-[9px] tracking-[0.2em] text-mist">INFERENCE</div>
                  <div className="mt-1 font-mono text-2xl font-bold text-frost tabular-nums">
                    {stats ? `${stats.inferenceMs.toFixed(0)}ms` : "—"}
                  </div>
                </div>
              </div>
              <div className="mt-3 space-y-2.5">
                {MODELS.map((m) => {
                  const color = MODEL_COLORS[m.key] ?? "#a78bfa";
                  return (
                    <div key={m.key} className="flex items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <StatusDot tone={m.exists ? "signal" : "alert"} ping={false} />
                        <span className="truncate font-mono text-[10px] tracking-[0.08em] text-pale">{m.name}</span>
                      </div>
                      <span className="font-mono text-[9px]" style={{ color }}>
                        {m.exists ? "READY" : "FALLBACK"}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-edge pt-3 font-mono text-[10px] tracking-[0.14em] text-mist">
                <span className="flex items-center gap-1.5">
                  <Cpu className="h-3 w-3" /> DEVICE
                </span>
                <span className="text-pale">CPU · {RUNTIME_CONFIG.device.toUpperCase()}</span>
              </div>
            </Panel>

            <Panel className="p-4">
              <PanelTitle icon={<Database className="h-3.5 w-3.5" />} label="SESSION EVENTS" />
              <div className="mt-3 space-y-2">
                {GROUP_ORDER.map((g) => (
                  <div key={g} className="flex items-center justify-between font-mono text-[11px]">
                    <span className="flex items-center gap-2 text-mist">
                      <span className="h-1.5 w-1.5 rounded-[1px]" style={{ backgroundColor: GROUP_COLORS[g] }} />
                      {GROUP_LABEL[g].toUpperCase()}
                    </span>
                    <span className="font-bold tabular-nums" style={{ color: GROUP_COLORS[g] }}>
                      {session[g]}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-edge pt-3">
                <span className="font-mono text-[10px] tracking-[0.18em] text-mist">TOTAL UNIQUE</span>
                <span className="font-mono text-xl font-bold text-pale tabular-nums">{session.total}</span>
              </div>
              <div className="mt-2 flex items-center justify-between font-mono text-[9px] tracking-[0.14em] text-mist">
                <span className="flex items-center gap-1.5">
                  <Database className="h-3 w-3 text-signal" /> MONGO TIMELINE
                </span>
                <span className="text-signal">LIVE ↗</span>
              </div>
            </Panel>
          </div>
        </div>

        {/* event stream */}
        <Panel className="mt-4 w-full min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-edge px-4 py-2.5">
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
              <Activity className="h-3.5 w-3.5 text-signal" />
              LIVE EVENT STREAM
            </div>
            <div className="flex h-6 items-end gap-1">
              {rate.map((v, i) => (
                <span
                  key={i}
                  className="w-2.5 bg-signal/60 transition-all duration-500"
                  style={{ height: `${Math.max(8, (v / maxRate) * 100)}%` }}
                />
              ))}
            </div>
          </div>
          <div className="grid max-h-72 grid-cols-1 gap-px overflow-y-auto bg-edge/40 md:grid-cols-2">
            <AnimatePresence initial={false}>
              {ticker.length === 0 && (
                <div className="col-span-full bg-panel px-4 py-6 text-center font-mono text-[11px] tracking-[0.2em] text-mist">
                  AWAITING DETECTIONS…
                </div>
              )}
              {ticker.map((e) => (
                <motion.div
                  key={e.key}
                  layout
                  initial={{ opacity: 0, x: -14 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex items-center gap-3 bg-panel px-4 py-2"
                >
                  <span className="font-mono text-[10px] tabular-nums text-mist">{timeOf(e.at)}</span>
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-[1px]"
                    style={{
                      backgroundColor:
                        GROUP_COLORS[
                          ({ face: "face", person: "person", car: "vehicle", truck: "vehicle", bus: "vehicle", motorbike: "vehicle", plate: "plate" } as Record<string, DetectionGroup>)[e.className] ?? "object"
                        ],
                    }}
                  />
                  <span className="font-mono text-[10px] font-bold tracking-[0.14em] text-pale">
                    {e.type}
                  </span>
                  <span className="font-mono text-[10px] text-mist">
                    {e.className} · {e.confidence.toFixed(2)}
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-mist">
                    TRK#{String(e.trackingId).padStart(3, "0")} · {e.camera}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Panel>
      </div>
    </main>
  );
}

function PanelTitle({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
      <span className="text-signal">{icon}</span>
      {label}
      <span className="ml-auto h-px flex-1 bg-edge" />
      <Square className="h-1.5 w-1.5 text-edge2" />
    </div>
  );
}
