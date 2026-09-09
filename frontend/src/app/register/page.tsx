"use client";

import clsx from "clsx";
import { CheckCircle2, Loader2, RefreshCw, UploadCloud, UserPlus, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Panel, SectionTag, StatusDot } from "@/components/ui";

interface Registration {
  name: string;
  notes: string;
  created_at: string;
  face_photo?: string;
}

export default function RegisterPage() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    fetch("/api/registrations", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setRegistrations(d.registrations ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(load, 0);
    const id = setInterval(load, 15000);
    return () => { window.clearTimeout(initial); clearInterval(id); };
  }, [load]);

  const pickPhoto = (file: File | undefined) => {
    setError(null);
    setOk(null);
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    setPhoto(file);
    setPreview(URL.createObjectURL(file));
  };

  const submit = async () => {
    setError(null);
    setOk(null);
    if (!photo) { setError("Upload a clear face photo — a single face should be visible."); return; }
    if (!name.trim()) { setError("Name is required."); return; }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("image_data", photo);
      form.append("name", name.trim());
      form.append("notes", notes.trim());
      const r = await fetch("/api/registrations", { method: "POST", body: form });
      const d = await r.json();
      if (!r.ok) {
        setError(d.detail ?? d.error ?? "Registration failed. Make sure a face is clearly visible.");
      } else {
        setOk(`${d.registration?.name ?? name.trim()} registered. The Face model will now show their name.`);
        setName("");
        setNotes("");
        setPhoto(null);
        setPreview(null);
        if (fileRef.current) fileRef.current.value = "";
        load();
      }
    } catch {
      setError("Backend unavailable — is FastAPI (port 8000) running?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="pt-14">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6">
        <SectionTag index="R1" label="IDENTITY REGISTRY" />
        <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
          Enrol people the <span className="text-signal text-glow">Face model</span> should know
        </h1>
        <p className="mt-3 max-w-2xl font-mono text-[11px] leading-relaxed tracking-[0.08em] text-mist">
          Upload one clear face photo per person. The backend computes a compact
          embedding (OpenCV / CPU-friendly), stores it in MongoDB, and the live
          Face detector will annotate the Analytics timeline with the person’s name.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {/* registration form */}
          <Panel className="p-5" tone="border-signal/40">
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
              <UserPlus className="h-3.5 w-3.5 text-signal" />
              NEW REGISTRATION
              <span className="ml-auto h-px flex-1 bg-edge" />
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {/* photo */}
              <button
                onClick={() => fileRef.current?.click()}
                className={clsx(
                  "group relative grid aspect-square place-items-center overflow-hidden border border-dashed text-center transition-colors",
                  preview ? "border-edge2" : "border-edge2 hover:border-signal/50",
                )}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => pickPhoto(e.target.files?.[0])}
                />
                {preview ? (
                  <img src={preview} alt="face preview" className="absolute inset-0 h-full w-full object-cover" />
                ) : (
                  <div className="px-4 font-mono text-[10px] tracking-[0.16em] text-mist">
                    <UploadCloud className="mx-auto mb-2 h-6 w-6 text-mist transition-colors group-hover:text-signal" />
                    CLICK TO UPLOAD<br />FACED PHOTO
                    <div className="mt-1 text-[8px] text-mist/60">SINGLE CLEAR FACE</div>
                  </div>
                )}
              </button>

              {/* fields */}
              <div className="flex flex-col gap-3">
                <div>
                  <div className="mb-1.5 font-mono text-[9px] tracking-[0.22em] text-mist">FULL NAME</div>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Atik Ahmed"
                    className="h-10 w-full border border-edge bg-abyss px-3 font-mono text-[12px] text-pale outline-none placeholder:text-mist/50 focus:border-signal/50"
                  />
                </div>
                <div className="flex-1">
                  <div className="mb-1.5 font-mono text-[9px] tracking-[0.22em] text-mist">NOTES</div>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Role, access level, notes…"
                    className="h-full min-h-20 w-full resize-none border border-edge bg-abyss px-3 py-2 font-mono text-[11px] text-pale outline-none placeholder:text-mist/50 focus:border-signal/50"
                  />
                </div>
              </div>
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 border border-alert/50 bg-alert/10 px-3 py-2.5 font-mono text-[10px] tracking-[0.1em] text-alert">
                <XCircle className="h-3.5 w-3.5 shrink-0" /> {error}
              </div>
            )}
            {ok && (
              <div className="mt-4 flex items-center gap-2 border border-signal/40 bg-signal/10 px-3 py-2.5 font-mono text-[10px] tracking-[0.1em] text-signal">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> {ok}
              </div>
            )}

            <button
              onClick={submit}
              disabled={busy}
              className="mt-5 flex w-full items-center justify-center gap-2 border border-signal/60 bg-signal/10 px-4 py-3 font-mono text-[11px] font-bold tracking-[0.22em] text-signal transition-colors hover:bg-signal/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserPlus className="h-3.5 w-3.5" />}
              REGISTER PERSON
            </button>
          </Panel>

          {/* registry list */}
          <Panel className="p-5">
            <div className="flex items-center justify-between gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
              <div className="flex items-center gap-2">
                <RefreshCw className="h-3 w-3 text-signal" />
                REGISTERED PEOPLE · {registrations.length}
              </div>
              <button onClick={load} className="text-mist transition-colors hover:text-signal">
                RELOAD
              </button>
            </div>

            <div className="mt-4 space-y-2.5">
              {registrations.length === 0 && (
                <div className="border border-edge bg-abyss/70 px-4 py-8 text-center font-mono text-[10px] tracking-[0.2em] text-mist">
                  NO ONE REGISTERED YET<br />
                  <span className="mt-2 inline-block text-[9px] text-mist/60">ENROL THE FIRST PERSON ON THE LEFT</span>
                </div>
              )}
              {registrations.map((r) => (
                <div key={r.name} className="flex items-center gap-3 border border-edge bg-abyss/70 p-3">
                  {r.face_photo ? (
                    <img src={r.face_photo} alt={r.name} className="h-10 w-10 rounded-full border border-edge2 object-cover" />
                  ) : (
                    <div className="grid h-10 w-10 place-items-center rounded-full bg-panel font-mono text-[11px] font-bold text-signal">
                      {r.name.slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 font-mono text-[12px] font-bold tracking-[0.1em] text-pale">
                      {r.name}
                      <StatusDot tone="signal" ping={false} />
                    </div>
                    <div className="truncate font-mono text-[9px] text-mist">
                      {r.notes || "—"}
                      <span className="ml-2 text-mist/60">{r.created_at?.slice(0, 10)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}