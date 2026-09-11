"use client";

import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import {
  GROUP_COLORS,
  OBJECT_CLASSES,
  VEHICLE_CLASSES,
  groupOf,
  type CameraProfile,
  type DetectionGroup,
} from "@/lib/sim";

export interface SimEvent {
  type: string;
  className: string;
  confidence: number;
  trackingId: number;
  camera: string;
  at: string;
}

export interface FeedStats {
  fps: number;
  inferenceMs: number;
  counts: Record<DetectionGroup, number>;
  activeTracks: number;
}

interface Entity {
  id: number;
  kind: "person" | "vehicle" | "object";
  cls: string;
  x: number; // box-center, normalized to frame width (can be off-screen)
  y: number; // ground line, normalized to frame height
  hFrac: number; // box height as fraction of frame height
  aspect: number; // width/height of box
  dir: 1 | -1;
  speed: number; // normalized units / second
  confBase: number;
  conf: number;
  phase: number;
  lane: number;
  hasFace: boolean;
  faceConf: number;
}

interface Props {
  profile: CameraProfile;
  live?: boolean;
  compact?: boolean;
  density?: number;
  paused?: boolean;
  onEvent?: (e: SimEvent) => void;
  onStats?: (s: FeedStats) => void;
  className?: string;
}

const EVENT_FROM_GROUP: Record<DetectionGroup, string> = {
  face: "FACE_DETECTED",
  person: "PERSON_DETECTED",
  vehicle: "VEHICLE_DETECTED",
  object: "OBJECT_DETECTED",
  plate: "PLATE_DETECTED",
};

function drawPerson(
  ctx: CanvasRenderingContext2D,
  cx: number,
  top: number,
  w: number,
  h: number,
  phase: number,
  t: number,
) {
  const sway = Math.sin(t * 5 + phase) * w * 0.06;
  const headR = h * 0.105;
  ctx.beginPath();
  ctx.arc(cx + sway * 0.4, top + headR * 1.6, headR, 0, Math.PI * 2);
  ctx.fill();
  // torso
  ctx.beginPath();
  ctx.moveTo(cx - w * 0.3 + sway, top + h * 0.2);
  ctx.lineTo(cx + w * 0.3 + sway, top + h * 0.2);
  ctx.lineTo(cx + w * 0.26 + sway * 0.4, top + h * 0.6);
  ctx.lineTo(cx - w * 0.26 + sway * 0.4, top + h * 0.6);
  ctx.closePath();
  ctx.fill();
  // legs with walk offset
  const step = Math.sin(t * 6 + phase) * w * 0.14;
  ctx.beginPath();
  ctx.moveTo(cx - w * 0.2, top + h * 0.6);
  ctx.lineTo(cx - w * 0.18 + step, top + h * 0.99);
  ctx.lineTo(cx - w * 0.02 + step, top + h * 0.99);
  ctx.lineTo(cx + w * 0.02, top + h * 0.6);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(cx + w * 0.04, top + h * 0.6);
  ctx.lineTo(cx + w * 0.06 - step, top + h * 0.99);
  ctx.lineTo(cx + w * 0.22 - step, top + h * 0.99);
  ctx.lineTo(cx + w * 0.22, top + h * 0.6);
  ctx.closePath();
  ctx.fill();
}

function drawVehicle(
  ctx: CanvasRenderingContext2D,
  cx: number,
  top: number,
  w: number,
  h: number,
) {
  const x = cx - w / 2;
  ctx.beginPath();
  ctx.roundRect(x, top + h * 0.32, w, h * 0.5, h * 0.08);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x + w * 0.18, top + h * 0.34);
  ctx.lineTo(x + w * 0.3, top + h * 0.06);
  ctx.lineTo(x + w * 0.72, top + h * 0.06);
  ctx.lineTo(x + w * 0.84, top + h * 0.34);
  ctx.closePath();
  ctx.fill();
  const wy = top + h * 0.82;
  for (const wx of [x + w * 0.22, x + w * 0.78]) {
    ctx.beginPath();
    ctx.arc(wx, wy, h * 0.16, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawBox(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string,
  label: string,
  alpha: number,
  glow: boolean,
  labelInside = false,
) {
  ctx.save();
  ctx.globalAlpha = alpha;
  if (glow) {
    ctx.shadowColor = color;
    ctx.shadowBlur = 9;
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  const L = Math.min(14, Math.min(w, h) * 0.28);
  ctx.beginPath();
  ctx.moveTo(x, y + L); ctx.lineTo(x, y); ctx.lineTo(x + L, y);
  ctx.moveTo(x + w - L, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + L);
  ctx.moveTo(x + w, y + h - L); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - L, y + h);
  ctx.moveTo(x + L, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h - L);
  ctx.stroke();
  ctx.shadowBlur = 0;

  // label chip
  const fontSize = Math.max(9, Math.min(12, w * 0.11));
  ctx.font = `600 ${fontSize}px "JetBrains Mono", monospace`;
  const tw = ctx.measureText(label).width + 10;
  const th = fontSize + 6;
  const ty = labelInside ? y + 2 : Math.max(2, y - th - 2);
  ctx.fillStyle = color;
  ctx.globalAlpha = alpha * 0.94;
  ctx.fillRect(x, ty, tw, th);
  ctx.fillStyle = "#021009";
  ctx.fillText(label, x + 5, ty + th - 4.5);
  ctx.restore();
}

export function CameraFeed({
  profile,
  live = false,
  compact = false,
  density = 1,
  paused = false,
  onEvent,
  onStats,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);

  const stateRef = useRef({
    entities: [] as Entity[],
    nextTrack: 1,
    fps: 25,
    statsTimer: 0,
  });
  const cbRef = useRef({ onEvent, onStats, live, density, paused, profile });
  useEffect(() => {
    cbRef.current = { onEvent, onStats, live, density, paused, profile };
  }, [onEvent, onStats, live, density, paused, profile]);

  useEffect(() => {
    const image = new Image();
    image.src = profile.image;
    image.onload = () => setImg(image);
    return () => {
      image.onload = null;
    };
  }, [profile.image]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let W = 0;
    let H = 0;
    let dpr = 1;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      W = Math.max(2, rect.width);
      H = Math.max(2, rect.height);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const st = stateRef.current;
    let raf = 0;
    let last = performance.now();

    const spawn = (kind: Entity["kind"], prof: CameraProfile) => {
      const lanes =
        kind === "vehicle"
          ? prof.vehicleLanes
          : prof.personLanes;
      if (lanes.length === 0) return null;
      const lane = lanes[Math.floor(Math.random() * lanes.length)];
      const dir: 1 | -1 = Math.random() < 0.5 ? 1 : -1;
      const id = st.nextTrack++;
      const depth = 0.09 + (lane - 0.55) * 0.42;
      if (kind === "vehicle") {
        const cls = VEHICLE_CLASSES[Math.floor(Math.random() * VEHICLE_CLASSES.length)];
        const hFrac = cls === "bus" || cls === "truck" ? depth * 1.5 : depth * 1.15;
        return {
          id, kind, cls,
          x: dir === 1 ? -0.09 : 1.09,
          y: lane,
          hFrac: Math.max(0.09, hFrac),
          aspect: cls === "motorbike" ? 1.7 : 2.25,
          dir,
          speed: (0.05 + Math.random() * 0.06) * (cls === "motorbike" ? 1.4 : 1),
          confBase: 0.87 + Math.random() * 0.1,
          conf: 0.9, phase: Math.random() * 10, lane,
          hasFace: false, faceConf: 0,
        } satisfies Entity;
      }
      if (kind === "object") {
        const cls = OBJECT_CLASSES[Math.floor(Math.random() * OBJECT_CLASSES.length)];
        return {
          id, kind, cls,
          x: dir === 1 ? -0.06 : 1.06,
          y: lane + 0.015,
          hFrac: Math.max(0.035, depth * 0.5),
          aspect: 1.15, dir,
          speed: 0.018 + Math.random() * 0.02,
          confBase: 0.6 + Math.random() * 0.2,
          conf: 0.7, phase: Math.random() * 10, lane,
          hasFace: false, faceConf: 0,
        } satisfies Entity;
      }
      const hasFace = Math.random() < 0.72;
      return {
        id, kind, cls: "person",
        x: dir === 1 ? -0.06 : 1.06,
        y: lane,
        hFrac: Math.max(0.075, depth),
        aspect: 0.42, dir,
        speed: 0.022 + Math.random() * 0.03,
        confBase: 0.85 + Math.random() * 0.12,
        conf: 0.9, phase: Math.random() * 10, lane,
        hasFace, faceConf: 0.78 + Math.random() * 0.18,
      } satisfies Entity;
    };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const cb = cbRef.current;
      const prof = cb.profile;
      const t = now / 1000;

      if (!cb.paused) {
        st.fps = st.fps * 0.93 + (1 / Math.max(dt, 1e-4)) * 0.07;

        const ents = st.entities;
        const nPersons = ents.filter((e) => e.kind === "person").length;
        const nVehicles = ents.filter((e) => e.kind === "vehicle").length;
        const nObjects = ents.filter((e) => e.kind === "object").length;
        const d = cb.density * prof.activity;

        if (nPersons < Math.round(prof.persons * cb.density) && Math.random() < dt * 0.55 * d) {
          const e = spawn("person", prof);
          if (e) {
            ents.push(e);
            if (cb.live) {
              cb.onEvent?.({ type: "PERSON_DETECTED", className: "person", confidence: e.confBase, trackingId: e.id, camera: prof.code, at: new Date().toISOString() });
              if (e.hasFace) cb.onEvent?.({ type: "FACE_DETECTED", className: "face", confidence: e.faceConf, trackingId: e.id, camera: prof.code, at: new Date().toISOString() });
            }
          }
        }
        if (nVehicles < Math.round(prof.vehicles * cb.density) && Math.random() < dt * 0.4 * d) {
          const e = spawn("vehicle", prof);
          if (e) {
            ents.push(e);
            if (cb.live) cb.onEvent?.({ type: "VEHICLE_DETECTED", className: e.cls, confidence: e.confBase, trackingId: e.id, camera: prof.code, at: new Date().toISOString() });
          }
        }
        if (nObjects < Math.round(prof.objects * cb.density) && Math.random() < dt * 0.25 * d) {
          const e = spawn("object", prof);
          if (e) {
            ents.push(e);
            if (cb.live) cb.onEvent?.({ type: "OBJECT_DETECTED", className: e.cls, confidence: e.confBase, trackingId: e.id, camera: prof.code, at: new Date().toISOString() });
          }
        }

        for (const e of ents) {
          e.x += e.dir * e.speed * dt * (e.kind === "vehicle" ? 1.35 : 1);
          const jitter = e.kind === "person" ? 0.03 : 0.02;
          e.conf = Math.min(0.995, Math.max(0.5, e.confBase + Math.sin(t * 1.9 + e.phase) * jitter));
        }
        st.entities = ents.filter((e) => e.x > -0.22 && e.x < 1.22);

        // DOM stats at ~4 Hz
        st.statsTimer += dt;
        if (st.statsTimer > 0.25 && cb.live) {
          st.statsTimer = 0;
          const counts: Record<DetectionGroup, number> = { face: 0, person: 0, vehicle: 0, object: 0, plate: 0 };
          for (const e of st.entities) {
            counts[groupOf(e.cls)]++;
            if (e.hasFace) counts.face++;
          }
          const infer = 16 + st.entities.length * 3.2 + st.entities.filter((e) => e.kind === "vehicle").length * 2.4 + Math.random() * 5;
          cb.onStats?.({
            fps: Math.min(30, st.fps),
            inferenceMs: infer,
            counts,
            activeTracks: st.entities.length,
          });
        }
      }

      /* ---------- render ---------- */
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      if (img) {
        const ir = img.width / img.height;
        const fr = W / H;
        let dw = W, dh = H, dx = 0, dy = 0;
        if (ir > fr) { dh = H; dw = H * ir; dx = (W - dw) / 2; }
        else { dw = W; dh = W / ir; dy = (H - dh) / 2; }
        ctx.drawImage(img, dx, dy, dw, dh);
      } else {
        const g = ctx.createLinearGradient(0, 0, 0, H);
        g.addColorStop(0, "#0a1417");
        g.addColorStop(1, "#050a0c");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
      }

      // sensor grade
      ctx.fillStyle = "rgba(16, 84, 60, 0.20)";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "rgba(2, 6, 8, 0.38)";
      ctx.fillRect(0, 0, W, H);

      // entities + detection overlays
      for (const e of st.entities) {
        const hPx = e.hFrac * H;
        const bw = e.hFrac * H * e.aspect;
        const bx = e.x * W;
        const by = e.y * H - hPx;
        const edgeFade = Math.max(0, Math.min(1, Math.min(e.x + 0.12, 1.12 - e.x) / 0.08));
        const alpha = compact ? edgeFade * 0.95 : edgeFade;

        ctx.fillStyle = "rgba(2,7,9,0.88)";
        if (e.kind === "person") {
          drawPerson(ctx, bx, by, bw, hPx, e.phase, t);
          ctx.strokeStyle = "rgba(120,255,200,0.07)";
          ctx.strokeRect(bx - bw / 2, by, bw, hPx);
        } else if (e.kind === "vehicle") {
          drawVehicle(ctx, bx, by, bw, hPx);
        } else {
          ctx.fillRect(bx - bw / 2, by + hPx * 0.25, bw, hPx * 0.75);
        }

        const color = GROUP_COLORS[groupOf(e.cls)];
        const label = `${e.cls.toUpperCase()} #${String(e.id).padStart(3, "0")} ${e.conf.toFixed(2)}`;
        const bx0 = bx - bw / 2;
        drawBox(ctx, bx0 - 3, by - 4, bw + 6, hPx + 7, color, compact ? `${e.cls.toUpperCase()} #${String(e.id).padStart(3, "0")}` : label, alpha, !compact, by - 6 < 20);

        if (e.hasFace && !compact) {
          const fS = hPx * 0.26;
          const fx = bx - fS / 2 + Math.sin(t * 5 + e.phase) * bw * 0.05;
          const fy = by + hPx * 0.035;
          const fConf = Math.min(0.995, Math.max(0.5, e.faceConf + Math.sin(t * 2.3 + e.phase) * 0.03));
          drawBox(ctx, fx, fy, fS, fS * 1.15, GROUP_COLORS.face, `FACE ${fConf.toFixed(2)}`, alpha, !compact, true);
        }
      }
    };

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [img, compact]);

  return (
    <div className={clsx("relative overflow-hidden bg-abyss", className)}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="pointer-events-none absolute inset-0 scanlines" />
    </div>
  );
}
