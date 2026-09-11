"use client";

import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import type { CameraProfile } from "@/lib/sim";
import type { FeedStats, SimEvent } from "./feed-canvas";

const BACKEND_URL = (process.env.NEXT_PUBLIC_DJANGO_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");

type Track = {
  id: string;
  tracking_id: number;
  class: string;
  confidence: number;
  last_seen: string;
  total_detections: number;
};

type SidebarResponse = {
  detection_count?: number;
  updated_at?: string | null;
  sidebar?: { tracks?: Track[]; total_tracks?: number };
  analytics?: Record<string, number>;
};

export function BackendCameraFeed({
  profile,
  model = "face",
  paused = false,
  onEvent,
  onStats,
  className,
}: {
  profile: CameraProfile;
  model?: string;
  paused?: boolean;
  onEvent?: (event: SimEvent) => void;
  onStats?: (stats: FeedStats) => void;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [mirrorMode, setMirrorMode] = useState<"auto" | "on" | "off">("auto");
  const knownTracks = useRef(new Set<number>());
  const mirrorParam = mirrorMode === "auto" ? "" : `&mirror=${mirrorMode === "on" ? 1 : 0}`;
  const streamUrl = `${BACKEND_URL}/video/?camera=${encodeURIComponent(profile.code)}&model=${encodeURIComponent(model)}${mirrorParam}`;

  const cycleMirror = () =>
    setMirrorMode((m) => (m === "auto" ? "on" : m === "on" ? "off" : "auto"));

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/video/sidebar-data/`, { cache: "no-store" });
        if (!response.ok) throw new Error(`backend returned ${response.status}`);
        const data = (await response.json()) as SidebarResponse;
        if (cancelled) return;
        const tracks = data.sidebar?.tracks ?? [];
        const analytics = data.analytics ?? {};
        const counts = {
          face: analytics.current_face ?? 0,
          person: analytics.current_person ?? 0,
          vehicle: (analytics.current_car ?? 0) + (analytics.current_truck ?? 0) + (analytics.current_bus ?? 0) + (analytics.current_motorcycle ?? 0),
          object: 0,
          plate: analytics.current_plate ?? 0,
        };
        onStats?.({
          fps: analytics.inference_ms ? Math.min(30, 1000 / Math.max(analytics.inference_ms, 1)) : 0,
          inferenceMs: analytics.inference_ms ?? 0,
          counts,
          activeTracks: data.detection_count ?? 0,
        });
        setLastUpdate(data.updated_at ?? null);
        for (const track of tracks) {
          if (knownTracks.current.has(track.tracking_id)) continue;
          knownTracks.current.add(track.tracking_id);
          const eventType =
            track.class === "face"
              ? "FACE_DETECTED"
              : track.class === "plate"
                ? "PLATE_DETECTED"
                : "PERSON_DETECTED";
          onEvent?.({
            type: eventType,
            className: track.class,
            confidence: track.confidence,
            trackingId: track.tracking_id,
            camera: profile.code,
            at: track.last_seen,
          });
        }
      } catch {
        if (!cancelled) setLastUpdate(null);
      }
    };
    poll();
    const timer = window.setInterval(poll, 2000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [onEvent, onStats, profile.code]);

  return (
    <div className={clsx("relative overflow-hidden bg-abyss", className)}>
      {!paused && !failed ? (
        <img
          src={streamUrl}
          alt={`${profile.code} live webcam with YOLO detection overlays`}
          className="absolute inset-0 h-full w-full object-contain"
          onError={() => setFailed(true)}
        />
      ) : null}
      {paused && <div className="absolute inset-0 grid place-items-center bg-abyss/85 font-mono text-xs tracking-[0.2em] text-flare">STREAM PAUSED</div>}
      {failed && !paused && (
        <div className="absolute inset-0 grid place-items-center bg-abyss px-6 text-center font-mono text-xs tracking-[0.12em] text-alert">
          <div><p>CAMERA STREAM UNAVAILABLE</p><p className="mt-2 text-[10px] text-mist">Check that the camera is reachable and enabled in the Camera Fleet page.<br />Register the RTSP/MJPEG URL there if it is not yet configured.</p><button className="mt-4 border border-alert/50 px-3 py-2 text-[10px] text-alert" onClick={() => { setFailed(false); window.location.reload(); }}>RECONNECT</button></div>
        </div>
      )}
      <div className="pointer-events-none absolute bottom-2 left-3 font-mono text-[9px] tracking-[0.12em] text-pale/70">
        {lastUpdate ? `BACKEND · ${lastUpdate}` : "CONNECTING TO DJANGO ANALYTICS"}
      </div>
      <button
        onClick={cycleMirror}
        title="Cycle mirror orientation: AUTO → MIRRORED → NORMAL → AUTO"
        className={clsx(
          "pointer-events-auto absolute right-2 top-2 border px-2 py-1 font-mono text-[9px] tracking-[0.2em] backdrop-blur-sm transition-colors",
          mirrorMode === "on" && "border-signal/50 bg-signal/15 text-signal",
          mirrorMode === "off" && "border-flare/50 bg-flare/15 text-flare",
          mirrorMode === "auto" && "border-edge bg-ink/70 text-mist hover:text-pale",
        )}
      >
        {mirrorMode === "auto" ? "MIRROR · AUTO" : mirrorMode === "on" ? "MIRRORED" : "NORMAL"}
      </button>
    </div>
  );
}
