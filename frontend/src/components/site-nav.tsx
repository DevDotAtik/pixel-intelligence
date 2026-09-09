"use client";

import clsx from "clsx";
import { Aperture, Radio } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "OVERVIEW" },
  { href: "/console", label: "LIVE CONSOLE" },
  { href: "/register", label: "REGISTER" },
  { href: "/analytics", label: "ANALYTICS" },
  { href: "/events", label: "EVENTS" },
  { href: "/cameras", label: "CAMERAS" },
  { href: "/api-docs", label: "API" },
];

function UtcClock() {
  const [now, setNow] = useState<string>("--:--:--");
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      const p = (n: number) => String(n).padStart(2, "0");
      setNow(`${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}Z`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="tabular-nums">{now}</span>;
}

export function SiteNav() {
  const pathname = usePathname();
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-edge/80 bg-ink/78 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1500px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-3">
          <span className="relative grid h-8 w-8 place-items-center border border-edge2 bg-panel">
            <Aperture className="h-4 w-4 text-signal transition-transform duration-500 group-hover:rotate-90" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-mono text-[13px] font-bold tracking-[0.3em] text-pale">
              PIXEL INTELLIGENCE
            </span>
            <span className="mt-1 font-mono text-[9px] tracking-[0.28em] text-mist">
              AI VIDEO ANALYTICS
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex">
          {LINKS.map((l) => {
            const active =
              l.href === "/"
                ? pathname === "/"
                : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={clsx(
                  "relative px-3.5 py-2 font-mono text-[11px] tracking-[0.22em] transition-colors",
                  active ? "text-signal" : "text-mist hover:text-pale",
                )}
              >
                {l.label}
                <span
                  className={clsx(
                    "absolute inset-x-3 -bottom-[1px] h-px bg-signal transition-opacity",
                    active ? "opacity-100" : "opacity-0",
                  )}
                />
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-4 font-mono text-[10px] tracking-[0.18em] text-mist">
          <UtcClock />
          <span className="hidden items-center gap-2 border border-edge bg-panel px-2.5 py-1.5 sm:flex">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute h-full w-full animate-ping rounded-full bg-signal opacity-70" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-signal" />
            </span>
            <Radio className="h-3 w-3 text-signal" />
            <span className="text-signal">NOMINAL</span>
          </span>
        </div>
      </div>
      <div className="flex gap-1 overflow-x-auto border-t border-edge/60 px-4 py-1.5 lg:hidden">
        {LINKS.map((l) => {
          const active =
            l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "whitespace-nowrap px-2 py-1 font-mono text-[10px] tracking-[0.2em]",
                active ? "text-signal" : "text-mist",
              )}
            >
              {l.label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
