"use client";

import clsx from "clsx";
import { ArrowLeft, ArrowRight, Braces, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ClassDot, ConfBar, Panel, SectionTag, StatusDot } from "@/components/ui";
import { CAMERA_PROFILES, GROUP_COLORS, groupOf } from "@/lib/sim";

interface EventRow {
  id: number;
  timestamp: string;
  eventType: string;
  className: string;
  confidence: number;
  trackingId: number;
  cameraCode: string;
  cameraName: string;
}

const PAGE = 25;
const GROUPS = ["all", "person", "face", "vehicle", "object"];
const TYPES = ["all", "FACE_DETECTED", "PERSON_DETECTED", "VEHICLE_DETECTED", "OBJECT_DETECTED"];

function fmt(iso: string) {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} · ${p(d.getDate())}/${p(d.getMonth() + 1)}`;
}

export default function EventsPage() {
  const [rows, setRows] = useState<EventRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [camera, setCamera] = useState("all");
  const [group, setGroup] = useState("all");
  const [type, setType] = useState("all");
  const [minConf, setMinConf] = useState(0);
  const [track, setTrack] = useState("");
  const [page, setPage] = useState(0);

  const query = useMemo(() => {
    const q = new URLSearchParams({ limit: String(PAGE), offset: String(page * PAGE) });
    if (camera !== "all") q.set("camera", camera);
    if (group !== "all") q.set("class", group);
    if (type !== "all") q.set("type", type);
    if (minConf > 0) q.set("min_conf", minConf.toFixed(2));
    if (track.trim()) q.set("track", track.trim());
    return q.toString();
  }, [camera, group, type, minConf, track, page]);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`/api/events?${query}`)
      .then((r) => r.json())
      .then((d) => {
        setRows(d.events ?? []);
        setCount(d.count ?? 0);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [query]);

  useEffect(() => {
    const initial = window.setTimeout(load, 0);
    const id = setInterval(load, 12000);
    return () => { window.clearTimeout(initial); clearInterval(id); };
  }, [load]);

  const pages = Math.max(1, Math.ceil(count / PAGE));

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <SectionTag index="L1" label="EVENT LEDGER" />
            <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              Every detection, <span className="text-signal text-glow">on record</span>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              className="flex items-center gap-2 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:text-signal"
            >
              <RefreshCw className={clsx("h-3.5 w-3.5", loading && "animate-spin")} />
              REFRESH
            </button>
            <a
              href={`/api/events?${query}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:text-signal"
            >
              <Braces className="h-3.5 w-3.5" />
              RAW JSON
            </a>
          </div>
        </div>

        {/* filters */}
        <Panel className="mt-6 p-4" bracket={false}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <FilterSelect label="CAMERA" value={camera} onChange={(v) => { setCamera(v); setPage(0); }}>
              <option value="all">ALL CAMERAS</option>
              {CAMERA_PROFILES.map((c) => (
                <option key={c.code} value={c.code}>{c.code}</option>
              ))}
            </FilterSelect>
            <FilterSelect label="CLASS GROUP" value={group} onChange={(v) => { setGroup(v); setPage(0); }}>
              {GROUPS.map((g) => (
                <option key={g} value={g}>{g.toUpperCase()}</option>
              ))}
            </FilterSelect>
            <FilterSelect label="EVENT TYPE" value={type} onChange={(v) => { setType(v); setPage(0); }}>
              {TYPES.map((t) => (
                <option key={t} value={t}>{t === "all" ? "ALL TYPES" : t}</option>
              ))}
            </FilterSelect>
            <div>
              <div className="mb-1.5 font-mono text-[9px] tracking-[0.22em] text-mist">
                MIN CONF · {minConf.toFixed(2)}
              </div>
              <input
                type="range"
                min={0}
                max={0.9}
                step={0.05}
                value={minConf}
                onChange={(e) => { setMinConf(Number(e.target.value)); setPage(0); }}
                className="h-9 w-full accent-signal"
              />
            </div>
            <div>
              <div className="mb-1.5 font-mono text-[9px] tracking-[0.22em] text-mist">
                TRACK ID
              </div>
              <input
                value={track}
                onChange={(e) => { setTrack(e.target.value.replace(/\D/g, "")); setPage(0); }}
                placeholder="e.g. 042"
                className="h-9 w-full border border-edge bg-abyss px-3 font-mono text-[11px] text-pale outline-none placeholder:text-mist/50 focus:border-signal/50"
              />
            </div>
          </div>
        </Panel>

        {/* table */}
        <Panel className="mt-4 overflow-hidden" bracket>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-edge bg-abyss/70 font-mono text-[9px] tracking-[0.26em] text-mist">
                  <th className="px-4 py-3 font-medium">TIME</th>
                  <th className="px-4 py-3 font-medium">EVENT</th>
                  <th className="px-4 py-3 font-medium">CLASS</th>
                  <th className="px-4 py-3 font-medium">CONFIDENCE</th>
                  <th className="px-4 py-3 font-medium">TRACK</th>
                  <th className="px-4 py-3 font-medium">CAMERA</th>
                  <th className="px-4 py-3 text-right font-medium">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-edge/50 transition-colors last:border-0 hover:bg-signal/5"
                  >
                    <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums text-mist">
                      {fmt(r.timestamp)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className="inline-block border px-2 py-0.5 font-mono text-[10px] font-bold tracking-[0.1em]"
                        style={{
                          color: GROUP_COLORS[groupOf(r.className)],
                          borderColor: `${GROUP_COLORS[groupOf(r.className)]}44`,
                          backgroundColor: `${GROUP_COLORS[groupOf(r.className)]}11`,
                        }}
                      >
                        {r.eventType}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2 font-mono text-[11px] text-pale/85">
                        <ClassDot cls={r.className} />
                        {r.className}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2 font-mono text-[11px] tabular-nums text-pale/85">
                        <ConfBar value={r.confidence} />
                        {r.confidence.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums text-mist">
                      #{String(r.trackingId).padStart(3, "0")}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-pale/85">
                      {r.cameraCode}
                      <span className="ml-2 hidden text-mist lg:inline">{r.cameraName.toUpperCase()}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <StatusDot tone="signal" ping={false} className="ml-auto" />
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && !loading && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center font-mono text-[11px] tracking-[0.2em] text-mist">
                      NO EVENTS MATCH THIS FILTER SET
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* pagination */}
        <div className="mt-4 flex items-center justify-between">
          <span className="font-mono text-[10px] tracking-[0.16em] text-mist">
            {count.toLocaleString()} MATCHING ROWS · PAGE {page + 1} / {pages}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="flex items-center gap-1.5 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-mist transition-colors enabled:hover:text-signal disabled:opacity-30"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> PREV
            </button>
            <button
              disabled={page >= pages - 1}
              onClick={() => setPage((p) => p + 1)}
              className="flex items-center gap-1.5 border border-edge bg-panel px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-mist transition-colors enabled:hover:text-signal disabled:opacity-30"
            >
              NEXT <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 font-mono text-[9px] tracking-[0.22em] text-mist">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full appearance-none border border-edge bg-abyss px-3 font-mono text-[11px] text-pale outline-none focus:border-signal/50"
      >
        {children}
      </select>
    </div>
  );
}
