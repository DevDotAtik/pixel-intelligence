"use client";

import {
  Activity,
  Camera as CameraIcon,
  Crosshair,
  Gauge,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ClassDot, CountUp, Panel, SectionTag } from "@/components/ui";
import { GROUP_COLORS, groupOf } from "@/lib/sim";

const EVENT_COLOR: Record<string, string> = {
  face: GROUP_COLORS.face,
  person: GROUP_COLORS.person,
  plate: GROUP_COLORS.plate,
  vehicle: GROUP_COLORS.vehicle,
  object: GROUP_COLORS.object,
};
const EVENT_KEYS = Object.keys(EVENT_COLOR);

interface Stats {
  totals: { events_7d: number; unique_tracks: number; avg_per_hour: number };
  daily: Array<Record<string, number | string>>;
  hourly: Array<Record<string, number>>;
  classes: Array<{ k: string; n: number; avg_conf: number }>;
  cameras: Array<{ code: string; name: string; status: string; n: number }>;
  confidence_hist: Array<{ b: number; n: number }>;
}

interface Subject {
  identity: string;
  registered: boolean;
  sighting_count: number;
  updated_at: string;
  attributes: Record<string, unknown>;
  recent_sightings?: Array<{
    first_seen: string;
    last_seen: string;
    camera_code: string;
    status: string;
    attributes?: Record<string, unknown>;
  }>;
}

function ChartTip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color?: string }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-40 border border-edge2 bg-ink/95 px-3 py-2 font-mono text-[10px] shadow-2xl">
      <div className="mb-1.5 tracking-[0.22em] text-mist">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 py-0.5">
          <span className="h-1.5 w-1.5" style={{ background: p.color }} />
          <span className="text-pale/80">{p.name.replace("_DETECTED", "")}</span>
          <span className="ml-auto pl-4 tabular-nums text-signal">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

function ChartHead({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-edge px-4 py-3">
      <span className="font-mono text-[10px] tracking-[0.24em] text-pale">
        {title}
      </span>
      <span className="font-mono text-[9px] tracking-[0.16em] text-mist">{sub}</span>
    </div>
  );
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch("/api/stats", { cache: "no-store" })
        .then((response) => {
          if (!response.ok) throw new Error("analytics backend unavailable");
          return response.json() as Promise<Stats>;
        })
        .then((data) => {
          if (!cancelled) { setStats(data); setErr(false); }
        })
        .catch(() => { if (!cancelled) setErr(true); });
      fetch("/api/subjects", { cache: "no-store" })
        .then((r) => r.json())
        .then((d) => { if (!cancelled) setSubjects(d.subjects ?? []); })
        .catch(() => {});
    };
    load();
    const timer = window.setInterval(load, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  const daily = (stats?.daily ?? []).map((d) => {
    const row: Record<string, number | string> = { ...d };
    for (const k of EVENT_KEYS) row[k] = Number(row[k] ?? 0);
    row.day = String(d.day).slice(5);
    return row;
  });

  const hourly = (stats?.hourly ?? []).map((h) => {
    const row: Record<string, number | string> = { ...h };
    for (const k of EVENT_KEYS) row[k] = Number(row[k] ?? 0);
    row.hour = `${String(h.hour).padStart(2, "0")}:00`;
    return row;
  });

  const classTotal = (stats?.classes ?? []).reduce((a, c) => a + c.n, 0) || 1;
  const topCamera = stats?.cameras?.[0];

  const confHist = (stats?.confidence_hist ?? []).map((b) => ({
    range: `${(50 + (b.b - 1) * 5) / 100}–${(50 + b.b * 5) / 100}`,
    n: b.n,
  }));

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6">
        <SectionTag index="A2" label="ANALYTICS" />
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Signals from the <span className="text-signal text-glow">ledger</span>
          </h1>
          <span className="font-mono text-[10px] tracking-[0.2em] text-mist">
            WINDOW · LAST 7 DAYS · MONGO SUBJECT TIMELINE
          </span>
        </div>

        {/* stat cards */}
        <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            {
              icon: Activity,
              label: "EVENTS · 7D",
              value: stats?.totals.events_7d ?? 0,
              decimals: 0,
              tone: "text-signal",
            },
            {
              icon: Crosshair,
              label: "UNIQUE TRACKS",
              value: stats?.totals.unique_tracks ?? 0,
              decimals: 0,
              tone: "text-flare",
            },
            {
              icon: Gauge,
              label: "AVG EVENTS / HOUR",
              value: stats?.totals.avg_per_hour ?? 0,
              decimals: 1,
              tone: "text-frost",
            },
            {
              icon: CameraIcon,
              label: topCamera ? `HOTTEST · ${topCamera.code}` : "HOTTEST CAM",
              value: topCamera?.n ?? 0,
              decimals: 0,
              tone: "text-ghost",
            },
          ].map((s) => (
            <Panel key={s.label} className="p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] tracking-[0.22em] text-mist">
                  {s.label}
                </span>
                <s.icon className="h-3.5 w-3.5 text-mist" />
              </div>
              <div className={`mt-2 font-mono text-3xl font-bold tabular-nums sm:text-4xl ${s.tone}`}>
                <CountUp value={s.value} decimals={s.decimals} />
              </div>
            </Panel>
          ))}
        </div>

        {err && (
          <div className="mt-6 border border-alert/50 bg-alert/10 px-4 py-3 font-mono text-[11px] tracking-[0.14em] text-alert">
            ANALYTICS OFFLINE — FASTAPI EVENT LOG UNREACHABLE
          </div>
        )}

        {/* daily trend */}
        <Panel className="mt-6">
          <ChartHead title="DETECTION VOLUME · 14 DAYS" sub="STACKED BY EVENT TYPE" />
          <div className="h-72 px-2 py-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={daily} margin={{ top: 6, right: 16, left: -16, bottom: 0 }}>
                <defs>
                  {EVENT_KEYS.map((k) => (
                    <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={EVENT_COLOR[k]} stopOpacity={0.45} />
                      <stop offset="100%" stopColor={EVENT_COLOR[k]} stopOpacity={0.03} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis tickLine={false} axisLine={false} width={48} />
                <Tooltip content={<ChartTip />} />
                {EVENT_KEYS.map((k) => (
                  <Area
                    key={k}
                    type="monotone"
                    dataKey={k}
                    stackId="1"
                    stroke={EVENT_COLOR[k]}
                    strokeWidth={1.4}
                    fill={`url(#g-${k})`}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          {/* hourly */}
          <Panel className="lg:col-span-2">
            <ChartHead title="DIURNAL RHYTHM" sub="AVG EVENTS BY HOUR OF DAY" />
            <div className="h-72 px-2 py-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourly} margin={{ top: 6, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="hour" tickLine={false} axisLine={false} interval={3} />
                  <YAxis tickLine={false} axisLine={false} width={48} />
                  <Tooltip content={<ChartTip />} />
                  {EVENT_KEYS.map((k) => (
                    <Bar key={k} dataKey={k} stackId="1" fill={EVENT_COLOR[k]} fillOpacity={0.85} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {/* classes donut */}
          <Panel>
            <ChartHead title="CLASS MIX" sub="7-DAY DISTRIBUTION" />
            <div className="h-64 px-2 py-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={(stats?.classes ?? []).map((c) => ({ ...c }))}
                    dataKey="n"
                    nameKey="k"
                    innerRadius="58%"
                    outerRadius="88%"
                    paddingAngle={3}
                    strokeWidth={0}
                  >
                    {(stats?.classes ?? []).map((c) => (
                      <Cell key={c.k} fill={GROUP_COLORS[groupOf(c.k)]} fillOpacity={0.9} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-1.5 px-4 pb-4">
              {(stats?.classes ?? []).slice(0, 6).map((c) => (
                <div key={c.k} className="flex items-center gap-2 font-mono text-[10px] text-mist">
                  <ClassDot cls={c.k} />
                  <span className="text-pale/80">{c.k}</span>
                  <span className="ml-auto tabular-nums text-pale">
                    {Math.round((c.n / classTotal) * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          {/* per-camera */}
          <Panel>
            <ChartHead title="CAMERA LEADERS" sub="EVENTS · 7 DAYS" />
            <div className="space-y-3 p-4">
              {(stats?.cameras ?? []).map((c, i) => {
                const max = stats?.cameras?.[0]?.n || 1;
                return (
                  <div key={c.code}>
                    <div className="flex items-center justify-between font-mono text-[10px]">
                      <span className="tracking-[0.12em] text-pale">
                        <span className="text-mist">{String(i + 1).padStart(2, "0")} </span>
                        {c.code} <span className="text-mist">· {c.name.toUpperCase()}</span>
                      </span>
                      <span className="tabular-nums text-signal">{c.n}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 w-full bg-edge">
                      <div
                        className="h-full bg-signal/70 transition-all duration-700"
                        style={{ width: `${(c.n / max) * 100}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>

          {/* confidence histogram */}
          <Panel>
            <ChartHead title="CONFIDENCE HISTOGRAM" sub="DETECTION QUALITY · 7D" />
            <div className="h-56 px-2 py-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={confHist} margin={{ top: 6, right: 12, left: -24, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="range" tickLine={false} axisLine={false} interval={1} />
                  <YAxis tickLine={false} axisLine={false} width={48} />
                  <Tooltip content={<ChartTip />} />
                  <Bar dataKey="n" fill="#4cc9f0" fillOpacity={0.8} radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {/* subject timeline */}
          <Panel>
            <ChartHead title="SUBJECT TIMELINE" sub="ONE ENTRY PER REAPPEARANCE" />
            <div className="max-h-72 divide-y divide-edge/60 overflow-y-auto">
              {subjects.length === 0 && (
                <div className="px-4 py-8 text-center font-mono text-[10px] tracking-[0.18em] text-mist">
                  NO SUBJECTS SEEN YET — START THE LIVE CAMERA
                </div>
              )}
              {subjects.map((s) => {
                const latest = s.recent_sightings?.[0];
                const clothing = (s.attributes?.clothing ?? {}) as Record<string, unknown>;
                return (
                  <div key={s.identity} className="flex items-center gap-3 px-4 py-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-panel font-mono text-[11px] font-bold text-signal">
                      {String(s.identity).slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 font-mono text-[10px] font-bold tracking-[0.08em] text-pale">
                        {s.identity}
                        {s.registered && (
                          <span className="inline-block border border-signal/40 bg-signal/10 px-1.5 py-px text-[8px] tracking-[0.12em] text-signal">
                            REGISTERED
                          </span>
                        )}
                      </div>
                      <div className="truncate font-mono text-[9px] text-mist">
                        {s.sighting_count} sightings
                        {clothing.type ? ` · ${String(clothing.type)} ${String(clothing.colour ?? "")}` : ""}
                        {latest ? ` · last ${fmtTime(latest.last_seen)} @ ${latest.camera_code}` : ""}
                      </div>
                    </div>
                    <span className={`ml-auto font-mono text-[9px] ${latest?.status === "closed" ? "text-mist" : "text-signal"}`}>
                      {latest?.status ?? "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}

function fmtTime(iso: string) {
  try {
    const d = new Date(iso);
    const p = (n: number) => String(n).padStart(2, "0");
    return `${p(d.getHours())}:${p(d.getMinutes())}`;
  } catch {
    return "--:--";
  }
}
