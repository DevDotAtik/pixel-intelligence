"use client";

import { motion } from "framer-motion";
import { ArrowRight, ChevronDown, Play } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CAMERA_PROFILES } from "@/lib/sim";
import { CameraFeed } from "@/components/console/feed-canvas";
import { CountUp } from "@/components/ui";

function RevealWord({
  children,
  delay,
  className,
}: {
  children: string;
  delay: number;
  className?: string;
}) {
  return (
    <span className="inline-block overflow-hidden pb-1 align-bottom">
      <motion.span
        className={`inline-block ${className ?? ""}`}
        initial={{ y: "115%" }}
        animate={{ y: 0 }}
        transition={{ delay, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </motion.span>
    </span>
  );
}

export function Hero() {
  const [metrics, setMetrics] = useState({
    total: 0,
    last24: 0,
    camsOnline: 0,
  });

  useEffect(() => {
    fetch("/api/event-counts")
      .then((r) => r.json())
      .then((d) =>
        setMetrics((m) => ({
          ...m,
          total: d.total ?? 0,
          last24: d.last_24h ?? 0,
        })),
      )
      .catch(() => {});
    fetch("/api/cameras")
      .then((r) => r.json())
      .then((d) => setMetrics((m) => ({ ...m, camsOnline: d.online ?? 0 })))
      .catch(() => {});
  }, []);

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      {/* simulated live feed as backdrop */}
      <CameraFeed
        profile={CAMERA_PROFILES[0]}
        live={false}
        density={1.35}
        compact
        className="absolute inset-0 h-full w-full opacity-75"
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-ink/85 via-ink/35 to-ink" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-ink/85 via-transparent to-ink/60" />
      <div className="pointer-events-none absolute inset-0 grid-bg" />
      <div className="absolute inset-x-0 h-px bg-signal/40 sweep-line" style={{ top: "-12%" }} />

      {/* content */}
      <div className="relative z-10 mx-auto flex w-full max-w-[1500px] flex-1 flex-col justify-center px-4 pb-16 pt-36 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05, duration: 0.6 }}
          className="mb-6 flex flex-wrap items-center gap-3 font-mono text-[11px] tracking-[0.3em] text-mist"
        >
          <span className="border border-signal/40 bg-signal/10 px-2.5 py-1 text-signal">
            SMART INDIA HACKATHON · PS 187 / SIH26187
          </span>
          <span className="hidden sm:inline">AI-BASED INTELLIGENT VIDEO ANALYTICS</span>
        </motion.div>

        <h1 className="max-w-6xl text-[15vw] font-bold leading-[0.92] tracking-tight sm:text-[11vw] lg:text-[7.2rem]">
          <RevealWord delay={0.12}>EVERY</RevealWord>{" "}
          <RevealWord delay={0.2} className="text-signal text-glow">FRAME</RevealWord>
          <br />
          <RevealWord delay={0.28}>ACCOUNTED</RevealWord>{" "}
          <RevealWord delay={0.36}>FOR.</RevealWord>
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.7 }}
          className="mt-7 max-w-xl text-base leading-relaxed text-pale/70 sm:text-lg"
        >
          Pixel Intelligence layers YOLO detection, persistent tracking and an
          append-only
          event ledger on top of existing CCTV infrastructure — turning passive
          border cameras into a real-time analytic grid.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.62, duration: 0.7 }}
          className="mt-9 flex flex-wrap items-center gap-3"
        >
          <Link
            href="/console"
            className="group flex items-center gap-3 border border-signal/60 bg-signal/10 px-6 py-3.5 font-mono text-xs font-bold tracking-[0.24em] text-signal transition-all hover:bg-signal hover:text-ink"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            OPEN LIVE CONSOLE
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
          </Link>
          <Link
            href="/api-docs"
            className="border border-edge2 px-6 py-3.5 font-mono text-xs tracking-[0.24em] text-pale/80 transition-colors hover:border-pale/60 hover:text-pale"
          >
            READ THE API
          </Link>
        </motion.div>
      </div>

      {/* metrics strip */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.85, duration: 0.9 }}
        className="relative z-10 border-t border-edge/80 bg-ink/72 backdrop-blur-md"
      >
        <div className="mx-auto grid max-w-[1500px] grid-cols-2 divide-x divide-edge/70 md:grid-cols-4">
          {[
            { label: "EVENTS IN LEDGER", value: metrics.total, suffix: "" },
            { label: "LAST 24 HOURS", value: metrics.last24, suffix: "" },
            { label: "CAMERAS ONLINE", value: metrics.camsOnline, suffix: " / 4" },
            { label: "MODELS READY", value: 2, suffix: " / 3" },
          ].map((m) => (
            <div key={m.label} className="px-4 py-5 sm:px-6">
              <div className="font-mono text-[9px] tracking-[0.26em] text-mist">
                {m.label}
              </div>
              <div className="mt-1.5 font-mono text-2xl font-bold text-pale sm:text-3xl">
                <CountUp value={m.value} suffix={m.suffix} />
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      <div className="pointer-events-none absolute bottom-28 left-1/2 z-10 hidden -translate-x-1/2 md:block">
        <ChevronDown className="h-5 w-5 animate-bounce text-mist" />
      </div>
    </section>
  );
}
