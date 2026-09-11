"use client";

import clsx from "clsx";
import { Camera, CheckCircle2, Loader2, RefreshCw, Square, UploadCloud, UserPlus, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Panel, SectionTag, StatusDot } from "@/components/ui";

interface Registration {
  name: string;
  notes: string;
  created_at: string;
  face_photo?: string;
  sample_count?: number;
}

export default function RegisterPage() {
  const [photos, setPhotos] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [gatewayActive, setGatewayActive] = useState(false);
  const [gatewayFrame, setGatewayFrame] = useState<string | null>(null);
  const [cameraBusy, setCameraBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const previewUrlsRef = useRef<string[]>([]);

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

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
  }, []);

  const stopGatewayCamera = useCallback(() => {
    setGatewayActive(false);
    setGatewayFrame(null);
  }, []);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const setReferencePhotos = (next: File[]) => {
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    const urls = next.map((file) => URL.createObjectURL(file));
    previewUrlsRef.current = urls;
    setPhotos(next);
    setPreviews(urls);
  };

  const startGatewayCamera = useCallback(async () => {
    setError(null);
    setOk(null);
    stopCamera();
    const probeUrl = "/api/registration-camera?camera=CAM-01";
    try {
      const response = await fetch(probeUrl, { cache: "no-store" });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "The project camera did not return a frame");
      }
      setGatewayFrame(`${probeUrl}&t=${Date.now()}`);
      setGatewayActive(true);
      return true;
    } catch (gatewayError) {
      const message = gatewayError instanceof Error ? gatewayError.message : "Unable to access project camera";
      setError(`Project camera unavailable: ${message}. Check CAM-01 and the Django video service.`);
      return false;
    }
  }, [stopCamera]);

  useEffect(() => {
    if (!gatewayActive) return;
    const refresh = () => setGatewayFrame(`/api/registration-camera?camera=CAM-01&t=${Date.now()}`);
    const timer = window.setInterval(refresh, 350);
    return () => window.clearInterval(timer);
  }, [gatewayActive]);

  const pickPhotos = (files: FileList | null) => {
    setError(null);
    setOk(null);
    const selected = Array.from(files ?? []);
    if (selected.length < 3 || selected.length > 5) {
      setError("Choose 3 to 5 clear photos of the same person.");
      return;
    }
    if (selected.some((file) => !file.type.startsWith("image/"))) {
      setError("Every selected file must be an image.");
      return;
    }
    setReferencePhotos(selected);
  };

  const startCamera = async () => {
    setError(null);
    setOk(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      const usingProjectFeed = await startGatewayCamera();
      if (usingProjectFeed) {
        setOk("Browser webcam access is unavailable; using the live project camera feed for registration.");
      } else {
        setError("This browser does not support webcam access and the project-camera fallback is unavailable.");
      }
      return;
    }
    setCameraBusy(true);
    try {
      stopGatewayCamera();
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 720 } },
      });
      streamRef.current = stream;
      if (!videoRef.current) throw new Error("Camera preview is unavailable");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraActive(true);
    } catch (cameraError) {
      stopCamera();
      const message = cameraError instanceof Error ? cameraError.message : "Unable to access webcam";
      // When Django owns /dev/videoN, share its already-open capture instead
      // of asking the OS to open the physical device a second time.
      const usingProjectFeed = await startGatewayCamera();
      if (usingProjectFeed) {
        setOk("Browser webcam is busy; using the live project camera feed for registration.");
      } else {
        setError(`Webcam unavailable: ${message}. The project-camera fallback also failed; check CAM-01 or close other camera apps.`);
      }
    } finally {
      setCameraBusy(false);
    }
  };

  const captureReference = async () => {
    const video = videoRef.current;
    if (!cameraActive && !gatewayActive) {
      setError("Start the webcam and wait for the live preview before capturing.");
      return;
    }
    if (photos.length >= 5) {
      setError("You already captured 5 references. Clear them or submit this registration.");
      return;
    }
    try {
      let blob: Blob | null = null;
      if (cameraActive) {
        if (!video?.videoWidth || !video.videoHeight) throw new Error("Wait for the webcam preview before capturing");
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Could not capture the webcam frame");
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
      } else {
        const response = await fetch(`/api/registration-camera?camera=CAM-01&t=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error("The project camera did not return a frame");
        blob = await response.blob();
      }
      if (!blob) throw new Error("Could not encode the camera frame");
      setReferencePhotos([...photos, new File([blob], `webcam-reference-${photos.length + 1}.jpg`, { type: "image/jpeg" })]);
      setError(null);
    } catch (captureError) {
      setError(captureError instanceof Error ? captureError.message : "Could not capture the camera frame.");
    }
  };

  const clearReferences = () => {
    setReferencePhotos([]);
    if (fileRef.current) fileRef.current.value = "";
    setError(null);
  };

  const submit = async () => {
    setError(null);
    setOk(null);
    if (photos.length < 3) { setError("Capture or upload 3 clear references — a single face should be visible in each."); return; }
    if (!name.trim()) { setError("Name is required."); return; }
    setBusy(true);
    try {
      const form = new FormData();
      photos.forEach((photo) => form.append("image_data", photo));
      form.append("name", name.trim());
      form.append("notes", notes.trim());
      const r = await fetch("/api/registrations", { method: "POST", body: form });
      const d = await r.json();
      if (!r.ok) {
        setError(d.detail ?? d.error ?? "Registration failed. Make sure a face is clearly visible.");
      } else {
        setOk(`${d.registration?.name ?? name.trim()} enrolled with ${photos.length} references. The Face model will name them only after high-confidence confirmation.`);
        setName("");
        setNotes("");
        clearReferences();
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
          Capture 3–5 live webcam references (front, slight left, slight right), then add the
          person&apos;s details. The backend accepts only sharp single-face frames and names a live
          face only after repeated high-confidence matches.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {/* registration form */}
          <Panel className="p-5" tone="border-signal/40">
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.22em] text-mist">
              <UserPlus className="h-3.5 w-3.5 text-signal" />
              NEW REGISTRATION
              <span className="ml-auto h-px flex-1 bg-edge" />
            </div>

            <div className="mt-4 grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(260px,0.9fr)]">
              <div>
                <div className="relative aspect-video overflow-hidden border border-edge2 bg-abyss">
                  {gatewayActive && gatewayFrame ? (
                    <img
                      src={gatewayFrame}
                      alt="live project camera for registration"
                      className="h-full w-full -scale-x-100 object-cover"
                      onError={() => { stopGatewayCamera(); setError("Project camera feed stopped. Check CAM-01, then reconnect."); }}
                    />
                  ) : (
                    <video ref={videoRef} muted playsInline className="h-full w-full -scale-x-100 object-cover" />
                  )}
                  {!cameraActive && !gatewayActive && (
                    <div className="absolute inset-0 grid place-items-center bg-abyss/85 px-5 text-center font-mono text-[10px] tracking-[0.16em] text-mist">
                      <Camera className="mb-2 h-6 w-6 text-signal" />
                      START WEBCAM TO CAPTURE REFERENCES
                    </div>
                  )}
                  {(cameraActive || gatewayActive) && (
                    <div className="pointer-events-none absolute inset-[14%_31%] rounded-[48%] border-2 border-signal/70 shadow-[0_0_28px_rgba(76,255,162,0.2)]" />
                  )}
                  <div className="absolute bottom-2 left-2 flex items-center gap-2 bg-abyss/85 px-2 py-1 font-mono text-[9px] tracking-[0.14em] text-signal">
                    <StatusDot tone={cameraActive || gatewayActive ? "signal" : "mist"} ping={cameraActive || gatewayActive} />
                    {cameraActive ? "LIVE WEBCAM" : gatewayActive ? "LIVE PROJECT CAMERA" : "CAMERA OFF"}
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {!cameraActive && !gatewayActive ? (
                    <>
                      <button onClick={startCamera} disabled={cameraBusy} className="flex items-center gap-2 border border-signal/60 bg-signal/10 px-3 py-2 font-mono text-[10px] font-bold tracking-[0.14em] text-signal disabled:opacity-50">
                        {cameraBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
                        START WEBCAM
                      </button>
                      <button onClick={() => void startGatewayCamera()} className="flex items-center gap-2 border border-edge2 px-3 py-2 font-mono text-[10px] tracking-[0.14em] text-mist hover:border-signal/50 hover:text-signal">
                        USE PROJECT CAMERA
                      </button>
                    </>
                  ) : (
                    <>
                      <button onClick={captureReference} className="flex items-center gap-2 border border-signal/60 bg-signal/10 px-3 py-2 font-mono text-[10px] font-bold tracking-[0.14em] text-signal">
                        <Camera className="h-3.5 w-3.5" />
                        CAPTURE {photos.length + 1} OF 3
                      </button>
                      <button onClick={cameraActive ? stopCamera : stopGatewayCamera} className="flex items-center gap-2 border border-edge2 px-3 py-2 font-mono text-[10px] tracking-[0.14em] text-mist hover:text-pale">
                        <Square className="h-3 w-3" /> STOP
                      </button>
                    </>
                  )}
                  <button onClick={() => fileRef.current?.click()} className="flex items-center gap-2 border border-edge px-3 py-2 font-mono text-[10px] tracking-[0.14em] text-mist hover:border-signal/50 hover:text-signal">
                    <UploadCloud className="h-3.5 w-3.5" /> UPLOAD INSTEAD
                  </button>
                  <input ref={fileRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => pickPhotos(e.target.files)} />
                </div>
                <p className="mt-3 font-mono text-[9px] leading-relaxed tracking-[0.08em] text-mist/80">
                  Capture a front-facing frame, then turn slightly left and right. Keep one face inside the guide with good lighting.
                </p>

                {previews.length > 0 && (
                  <div className="mt-3">
                    <div className="mb-1.5 flex items-center justify-between font-mono text-[9px] tracking-[0.16em] text-mist">
                      <span>REFERENCE FRAMES · {previews.length}/3 MINIMUM</span>
                      <button onClick={clearReferences} className="text-alert hover:text-pale">CLEAR</button>
                    </div>
                    <div className="grid grid-cols-5 gap-1.5">
                      {previews.map((preview, index) => (
                        <img key={preview} src={preview} alt={`reference ${index + 1}`} className="aspect-square w-full border border-edge object-cover" />
                      ))}
                    </div>
                  </div>
                )}
              </div>

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
                      <span className={clsx("ml-2", (r.sample_count ?? 1) >= 3 ? "text-signal/80" : "text-alert")}>
                        {(r.sample_count ?? 1) >= 3 ? `${r.sample_count} REFERENCES` : "RE-ENROL: 3 REFERENCES REQUIRED"}
                      </span>
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
