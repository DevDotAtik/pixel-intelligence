"use client";

import clsx from "clsx";
import {
  ArrowUpRight,
  Cctv,
  CheckCircle2,
  Loader2,
  Pencil,
  PauseCircle,
  Plus,
  RefreshCw,
  Trash2,
  Wrench,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CountUp, Panel, SectionTag, StatusDot } from "@/components/ui";

interface Cam {
  code: string;
  name: string;
  zone: string;
  status: string;
  stream_type: string;
  stream_url: string;
  username?: string;
  password?: string;
  resolution: string;
  fps: number;
  enabled: boolean;
  notes?: string;
  mirror?: boolean | null;
  events_24h: number;
}

type FormState = {
  code: string;
  name: string;
  zone: string;
  stream_type: "rtsp" | "mjpeg" | "webcam";
  stream_url: string;
  username: string;
  password: string;
  resolution: string;
  fps: number;
  status: string;
  enabled: boolean;
  mirror: "auto" | "on" | "off";
  notes: string;
};

const EMPTY_FORM: FormState = {
  code: "",
  name: "",
  zone: "",
  stream_type: "rtsp",
  stream_url: "",
  username: "",
  password: "",
  resolution: "1280x720",
  fps: 30,
  status: "active",
  enabled: true,
  mirror: "auto",
  notes: "",
};

const STATUS_META: Record<string, { tone: string; label: string }> = {
  active: { tone: "signal", label: "ACTIVE" },
  maintenance: { tone: "flare", label: "MAINTENANCE" },
  offline: { tone: "alert", label: "OFFLINE" },
};

const inputCls =
  "w-full border border-edge bg-abyss px-3 py-2 font-mono text-[11px] text-pale outline-none placeholder:text-mist/50 focus:border-signal/50";

function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={clsx("block", className)}>
      <span className="mb-1.5 block font-mono text-[9px] tracking-[0.22em] text-mist">{label}</span>
      {children}
    </label>
  );
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Cam[]>([]);
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Cam | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [testBusy, setTestBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => setCameras(d.cameras ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(load, 0);
    const id = setInterval(load, 15000);
    return () => { window.clearTimeout(initial); clearInterval(id); };
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setTestResult(null);
    setMessage(null);
    setFormOpen(true);
  };

  const openEdit = (cam: Cam) => {
    setEditing(cam);
    setForm({
      code: cam.code,
      name: cam.name,
      zone: cam.zone,
      stream_type: (["rtsp", "mjpeg", "webcam"] as const).includes(cam.stream_type as "rtsp") ? (cam.stream_type as "rtsp" | "mjpeg" | "webcam") : "rtsp",
      stream_url: cam.stream_url ?? "",
      username: cam.username ?? "",
      password: cam.password ?? "",
      resolution: cam.resolution,
      fps: cam.fps,
      status: cam.status,
      enabled: cam.enabled,
      mirror: cam.mirror === true ? "on" : cam.mirror === false ? "off" : "auto",
      notes: cam.notes ?? "",
    });
    setTestResult(null);
    setMessage(null);
    setFormOpen(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const patch = (code: string, body: Record<string, unknown>) => {
    setBusyCode(code);
    return fetch("/api/cameras", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, ...body }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.camera) {
          setCameras((prev) => prev.map((c) => (c.code === code ? { ...c, ...d.camera } : c)));
        }
        return d;
      })
      .catch(() => ({}))
      .finally(() => setBusyCode(null));
  };

  const setStatus = (cam: Cam, status: string) => patch(cam.code, { status });

  const testUrl = async () => {
    setTestBusy(true);
    setTestResult(null);
    setMessage(null);
    try {
      const r = await fetch("/api/cameras/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stream_url: form.stream_url, stream_type: form.stream_type }),
      });
      const d = await r.json();
      setTestResult({ ok: Boolean(d.ok), detail: d.detail ?? (d.ok ? "Reachable" : "Unreachable") });
    } catch {
      setTestResult({ ok: false, detail: "Could not reach the backend test service." });
    } finally {
      setTestBusy(false);
    }
  };

  const save = async () => {
    setMessage(null);
    if (!form.name.trim()) { setMessage({ ok: false, text: "Camera name is required." }); return; }
    if (form.stream_type !== "webcam" && !form.stream_url.trim()) {
      setMessage({ ok: false, text: "A stream URL is required for RTSP / MJPEG sources." });
      return;
    }
    setSaving(true);
    const payload = {
      name: form.name.trim(),
      zone: form.zone.trim(),
      stream_type: form.stream_type,
      stream_url: form.stream_url.trim(),
      username: form.username.trim(),
      password: form.password.trim(),
      resolution: form.resolution.trim(),
      fps: Number(form.fps) || 30,
      status: form.status,
      enabled: form.enabled,
      mirror: form.mirror === "auto" ? null : form.mirror === "on",
      notes: form.notes.trim(),
    };
    try {
      const r = await fetch("/api/cameras", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editing ? { code: editing.code, ...payload } : payload),
      });
      const d = await r.json();
      if (!r.ok) {
        setMessage({ ok: false, text: d.detail ?? d.error ?? "Save failed." });
        return;
      }
      setMessage({ ok: true, text: editing ? `${editing.code} updated.` : `${d.camera?.code ?? "Camera"} registered — it is streamable in the console now.` });
      setFormOpen(false);
      load();
    } catch {
      setMessage({ ok: false, text: "Backend unavailable — is FastAPI (port 8000) running?" });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (cam: Cam) => {
    if (!window.confirm(`Delete ${cam.code} (${cam.name})? This cannot be undone.`)) return;
    setDeleting(cam.code);
    try {
      await fetch(`/api/cameras?code=${encodeURIComponent(cam.code)}`, { method: "DELETE" });
      load();
    } finally {
      setDeleting(null);
    }
  };

  const online = cameras.filter((c) => c.status === "active").length;
  const sourceCount = cameras.filter((c) => c.stream_url).length;

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <SectionTag index="C1" label="CAMERA FLEET" />
            <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              CCTV <span className="text-signal text-glow">surveillance grid</span>
            </h1>
            <p className="mt-3 max-w-2xl font-mono text-[11px] leading-relaxed tracking-[0.08em] text-mist">
              Register RTSP / MJPEG sources (CCTV recorders, IP cameras, room cameras) with a
              name, location and credentials. Every registered source is immediately streamable
              in the Live Console with the safe <span className="text-frost">Face / Person / Plate</span> detectors.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 border border-edge bg-panel px-4 py-3 font-mono text-[10px] tracking-[0.2em]">
              <StatusDot tone="signal" />
              <span className="text-pale">
                ONLINE <CountUp value={online} className="text-signal" /> / {cameras.length}
              </span>
              <span className="h-4 w-px bg-edge" />
              <span className="text-mist">
                STREAM SOURCES <CountUp value={sourceCount} className="text-signal" />
              </span>
            </div>
            <button
              onClick={openCreate}
              className="flex items-center gap-2 border border-signal/60 bg-signal/10 px-4 py-3 font-mono text-[10px] font-bold tracking-[0.2em] text-signal transition-colors hover:bg-signal hover:text-ink"
            >
              <Plus className="h-3.5 w-3.5" />
              REGISTER CAMERA
            </button>
          </div>
        </div>

        {formOpen && (
          <Panel className="mt-8 p-5" tone="border-signal/40">
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
              <Cctv className="h-3.5 w-3.5 text-signal" />
              {editing ? `EDIT ${editing.code}` : "NEW CAMERA SOURCE"}
              <span className="ml-auto h-px flex-1 bg-edge" />
              {editing && <span className="text-signal">AUTO-REFRESH ON THE CONSOLE IN ~15s</span>}
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Field label="CAMERA NAME *">
                <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gate 4 — North Wall" />
              </Field>
              <Field label="LOCATION / ZONE">
                <input className={inputCls} value={form.zone} onChange={(e) => setForm({ ...form, zone: e.target.value })} placeholder="Entrance, Sector 2, Parking…" />
              </Field>
              <Field label="STREAM TYPE">
                <select
                  className={inputCls}
                  value={form.stream_type}
                  onChange={(e) => setForm({ ...form, stream_type: e.target.value as FormState["stream_type"] })}
                >
                  <option value="rtsp">RTSP — H.264 CCTV / room camera</option>
                  <option value="mjpeg">MJPEG — HTTP browser stream (e.g. IP Webcam)</option>
                  <option value="webcam">Webcam — local /dev/video device</option>
                </select>
              </Field>

              <Field label="STREAM URL" className="md:col-span-2 lg:col-span-2">
                <div className="flex gap-2">
                  <input
                    className={inputCls}
                    value={form.stream_url}
                    onChange={(e) => { setForm({ ...form, stream_url: e.target.value }); setTestResult(null); }}
                    placeholder={
                      form.stream_type === "rtsp"
                        ? "rtsp://192.168.1.50:554/stream"
                        : form.stream_type === "mjpeg"
                          ? "http://192.168.1.50:8080/video"
                          : "leave empty to use the local camera"
                    }
                  />
                  <button
                    onClick={testUrl}
                    disabled={testBusy || !form.stream_url.trim()}
                    className="flex shrink-0 items-center gap-2 border border-edge px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-mist transition-colors hover:border-signal/50 hover:text-signal disabled:opacity-40"
                  >
                    {testBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    TEST
                  </button>
                </div>
                {testResult && (
                  <div
                    className={clsx(
                      "mt-2 flex items-center gap-2 border px-3 py-2 font-mono text-[10px] tracking-[0.08em]",
                      testResult.ok ? "border-signal/40 bg-signal/10 text-signal" : "border-alert/50 bg-alert/10 text-alert",
                    )}
                  >
                    {testResult.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> : <XCircle className="h-3.5 w-3.5 shrink-0" />}
                    {testResult.detail}
                  </div>
                )}
              </Field>

              {form.stream_type === "rtsp" && (
                <>
                  <Field label="USERNAME">
                    <input className={inputCls} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="admin" autoComplete="off" />
                  </Field>
                  <Field label="PASSWORD">
                    <input className={inputCls} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••" autoComplete="new-password" />
                  </Field>
                </>
              )}

              <Field label="RESOLUTION">
                <input className={inputCls} value={form.resolution} onChange={(e) => setForm({ ...form, resolution: e.target.value })} placeholder="1280x720" />
              </Field>
              <Field label="FPS">
                <input className={inputCls} type="number" min={1} max={120} value={form.fps} onChange={(e) => setForm({ ...form, fps: Number(e.target.value) })} />
              </Field>
              <Field label="MIRROR">
                <select className={inputCls} value={form.mirror} onChange={(e) => setForm({ ...form, mirror: e.target.value as FormState["mirror"] })}>
                  <option value="auto">AUTO — webcam mirrors, network streams don&apos;t</option>
                  <option value="on">MIRRORED (selfie style)</option>
                  <option value="off">NORMAL (physical)</option>
                </select>
              </Field>
              <Field label="BOOT STATUS">
                <select className={inputCls} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option value="active">ACTIVE</option>
                  <option value="maintenance">MAINTENANCE</option>
                  <option value="offline">OFFLINE</option>
                </select>
              </Field>

              <Field label="NOTES">
                <input className={inputCls} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Model, firmware, orientation…" />
              </Field>

              <label className="flex items-center gap-2 self-end pb-2 font-mono text-[10px] tracking-[0.18em] text-mist">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                  className="h-4 w-4 accent-[#3ef2a6]"
                />
                ENABLED FOR STREAMING
              </label>
            </div>

            {message && (
              <div
                className={clsx(
                  "mt-4 flex items-center gap-2 border px-3 py-2.5 font-mono text-[10px] tracking-[0.1em]",
                  message.ok ? "border-signal/40 bg-signal/10 text-signal" : "border-alert/50 bg-alert/10 text-alert",
                )}
              >
                {message.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> : <XCircle className="h-3.5 w-3.5 shrink-0" />}
                {message.text}
              </div>
            )}

            <div className="mt-5 flex items-center gap-3">
              <button
                onClick={save}
                disabled={saving}
                className="flex flex-1 items-center justify-center gap-2 border border-signal/60 bg-signal/10 px-4 py-3 font-mono text-[11px] font-bold tracking-[0.22em] text-signal transition-colors hover:bg-signal/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Cctv className="h-3.5 w-3.5" />}
                {editing ? "SAVE CHANGES" : "REGISTER CAMERA"}
              </button>
              <button
                onClick={() => setFormOpen(false)}
                className="border border-edge px-4 py-3 font-mono text-[10px] tracking-[0.2em] text-mist transition-colors hover:text-pale"
              >
                CANCEL
              </button>
            </div>
          </Panel>
        )}

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {cameras.map((c) => {
            const meta = STATUS_META[c.status] ?? STATUS_META.offline;
            const live = c.status === "active";
            return (
              <Panel key={c.code} className="overflow-hidden" bracket>
                <div className="relative aspect-[16/7] overflow-hidden bg-abyss">
                  <div
                    className={clsx(
                      "absolute inset-0 bg-gradient-to-br transition-all duration-700",
                      live ? "from-[#123] via-[#0c1a26] to-[#07141f]" : "from-[#1a1626] via-[#131022] to-[#0b0916]",
                      !live && "opacity-40 saturate-50",
                    )}
                  />
                  <div className="absolute inset-0 scanlines" />
                  <div className="absolute inset-0 bg-gradient-to-t from-ink via-transparent to-ink/40" />
                  <div className="absolute right-3 top-3 flex items-center gap-2">
                    {c.stream_url && c.password && (
                      <span className="border border-flare/40 bg-flare/10 px-2 py-1 font-mono text-[8px] tracking-[0.2em] text-flare">SECURED</span>
                    )}
                    <span className="border border-edge bg-ink/70 px-2 py-1 font-mono text-[9px] tracking-[0.18em] text-mist backdrop-blur-sm">
                      {c.stream_type.toUpperCase()} · {c.fps}FPS
                      {c.mirror === true ? ` · MIRROR` : c.mirror === false ? ` · NORMAL` : ""}
                    </span>
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
                      <StatusDot tone={meta.tone} ping={live} />
                      {meta.label}
                    </span>
                  </div>
                  <div className="absolute bottom-3 left-4">
                    <div className="font-mono text-xl font-bold tracking-[0.16em] text-pale">
                      {c.code}
                    </div>
                    <div className="font-mono text-[11px] tracking-[0.14em] text-signal">
                      {c.name.toUpperCase()}
                    </div>
                    <div className="mt-0.5 max-w-[85%] truncate font-mono text-[9px] tracking-[0.1em] text-mist">
                      {c.stream_url ? c.stream_url.replace(/\/\/([^:]+):[^@]+@/, "//***:***@") : "LOCAL DEVICE / NO URL"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-4 divide-x divide-edge border-t border-edge bg-abyss/60 text-center">
                  {[
                    { k: "LOCATION", v: c.zone.split("·")[0].trim() },
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
                  <button
                    onClick={() => openEdit(c)}
                    disabled={busyCode === c.code || deleting === c.code}
                    className="flex items-center gap-2 border border-edge px-3 py-2.5 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:border-signal/50 hover:text-signal disabled:opacity-40"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    EDIT
                  </button>
                  <button
                    onClick={() => remove(c)}
                    disabled={busyCode === c.code || deleting === c.code}
                    className="flex items-center gap-2 border border-edge px-3 py-2.5 font-mono text-[10px] tracking-[0.18em] text-mist transition-colors hover:border-alert/50 hover:text-alert disabled:opacity-40"
                  >
                    {deleting === c.code ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    DELETE
                  </button>
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
          CAMERAS PERSIST TO MONGO (<span className="text-frost">POST / PATCH / DELETE /api/cameras</span>). DJANGO REFRESHES THE REGISTRY EVERY
          {" "}<span className="text-frost">15s</span>, SO A NEWLY REGISTERED RTSP/MJPEG SOURCE GOES LIVE IN THE CONSOLE WITHOUT A RESTART.
          RTSP CREDENTIALS ARE INJECTED INTO THE URL (<span className="text-flare">rtsp://user:pass@host</span>) AND SHOWN AS SECURED.
        </p>
      </div>
    </main>
  );
}