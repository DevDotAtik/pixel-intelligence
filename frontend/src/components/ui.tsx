"use client";

import clsx from "clsx";
import { motion, useInView } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { GROUP_COLORS, groupOf } from "@/lib/sim";

/* ---------- corner brackets ---------- */

export function Corners({
  tone = "border-edge2",
  className,
}: {
  tone?: string;
  className?: string;
}) {
  const base = clsx("pointer-events-none absolute h-2.5 w-2.5", tone);
  return (
    <span aria-hidden className={clsx("pointer-events-none absolute inset-0", className)}>
      <i className={clsx(base, "left-0 top-0 border-l border-t")} />
      <i className={clsx(base, "right-0 top-0 border-r border-t")} />
      <i className={clsx(base, "bottom-0 left-0 border-b border-l")} />
      <i className={clsx(base, "bottom-0 right-0 border-b border-r")} />
    </span>
  );
}

/* ---------- panel ---------- */

export function Panel({
  children,
  className,
  bracket = true,
  tone,
}: {
  children: ReactNode;
  className?: string;
  bracket?: boolean;
  tone?: string;
}) {
  return (
    <div
      className={clsx(
        "relative border border-edge bg-panel/80 backdrop-blur-sm",
        className,
      )}
    >
      {bracket && <Corners tone={tone} />}
      {children}
    </div>
  );
}

/* ---------- section kicker ---------- */

export function SectionTag({
  index,
  label,
  className,
}: {
  index: string;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "flex items-center gap-3 font-mono text-[11px] tracking-[0.32em] text-mist uppercase",
        className,
      )}
    >
      <span className="text-signal">{index}</span>
      <span className="h-px w-9 bg-edge2" />
      <span>{label}</span>
    </div>
  );
}

/* ---------- scroll reveal ---------- */

export function Reveal({
  children,
  delay = 0,
  y = 26,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y, filter: "blur(6px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-70px" }}
      transition={{ duration: 0.75, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ---------- animated counter ---------- */

export function CountUp({
  value,
  decimals = 0,
  suffix = "",
  duration = 1.6,
  className,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  duration?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-30px" });
  const [v, setV] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - p, 3);
      setV(value * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration]);

  return (
    <span ref={ref} className={className}>
      {v.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}

/* ---------- status dot ---------- */

const DOT_TONES: Record<string, string> = {
  signal: "bg-signal",
  flare: "bg-flare",
  frost: "bg-frost",
  alert: "bg-alert",
  ghost: "bg-ghost",
  mist: "bg-mist",
};

export function StatusDot({
  tone = "signal",
  ping = true,
  className,
}: {
  tone?: string;
  ping?: boolean;
  className?: string;
}) {
  const color = DOT_TONES[tone] ?? DOT_TONES.signal;
  return (
    <span className={clsx("relative flex h-2 w-2", className)}>
      {ping && (
        <span
          className={clsx(
            "absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping",
            color,
          )}
        />
      )}
      <span className={clsx("relative inline-flex h-2 w-2 rounded-full", color)} />
    </span>
  );
}

/* ---------- detection class dot ---------- */

export function ClassDot({ cls, className }: { cls: string; className?: string }) {
  return (
    <span
      className={clsx("inline-block h-1.5 w-1.5 rounded-[2px]", className)}
      style={{ backgroundColor: GROUP_COLORS[groupOf(cls)] }}
    />
  );
}

/* ---------- confidence bar ---------- */

export function ConfBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.9 ? "bg-signal" : value >= 0.75 ? "bg-frost" : "bg-flare";
  return (
    <span
      className={clsx(
        "relative inline-block h-1 w-16 overflow-hidden rounded-full bg-edge align-middle",
        className,
      )}
    >
      <span
        className={clsx("absolute inset-y-0 left-0 rounded-full", color)}
        style={{ width: `${pct}%` }}
      />
    </span>
  );
}
