import {
  ArrowRight,
  CarFront,
  Check,
  Circle,
  Database,
  LineChart,
  LocateFixed,
  PersonStanding,
  ScanFace,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { ArchitectureDiagram } from "@/components/landing/architecture";
import { Hero } from "@/components/landing/hero";
import { Panel, Reveal, SectionTag, StatusDot } from "@/components/ui";
import { GROUP_COLORS } from "@/lib/sim";

const MARQUEE = [
  "FACE DETECTION",
  "PERSON TRACKING",
  "VEHICLE COUNTING",
  "EVENT LEDGER",
  "BORDER SECTORS",
  "YOLOV8M INFERENCE",
  "REST CONTRACTS",
  "POSTGRES PERSISTENCE",
];

const CAPABILITIES = [
  {
    icon: ScanFace,
    title: "Face Detection",
    body: "The compact face model flags faces without making a low-end CPU process the larger 25.9M-parameter checkpoint.",
    tag: "MODEL · model.pt",
  },
  {
    icon: PersonStanding,
    title: "Person Detection",
    body: "Person detection is supported by the architecture, but requires a deliberately configured multi-class YOLO model. The installed model is face-only.",
    tag: "MODEL · configure required",
  },
  {
    icon: CarFront,
    title: "Vehicle Counting",
    body: "Vehicle counting is ready in the pipeline, but stays disabled until a compatible model exposing vehicle classes is configured.",
    tag: "MODEL · configure required",
  },
  {
    icon: LocateFixed,
    title: "Persistent Tracking",
    body: "Each detection carries a tracking ID across frames, so one person over 300 frames is one event — not 300.",
    tag: "ALGO · track-id",
  },
  {
    icon: Database,
    title: "Event Persistence",
    body: "Every detection lands in a Postgres ledger — metadata only, never raw frames — queryable by any dashboard.",
    tag: "STORE · postgres",
  },
  {
    icon: LineChart,
    title: "Live Analytics",
    body: "Hourly rhythms, class distribution, per-camera leaders and confidence histograms computed on demand.",
    tag: "VIEW · /api/stats",
  },
];

const ROADMAP: Array<{ label: string; done: boolean }> = [
  { label: "Face detection over authorized webcam", done: true },
  { label: "Person + vehicle detection with compatible model", done: false },
  { label: "Tracking IDs and current/event count separation", done: true },
  { label: "REST API with JSON responses", done: true },
  { label: "Postgres event ledger and analytics dashboard", done: true },
  { label: "RTSP / CCTV stream ingest (replace webcam source)", done: false },
  { label: "Multi-camera concurrent processing", done: false },
  { label: "Intrusion zones, line-crossing and loitering logic", done: false },
  { label: "Plate OCR, GPU acceleration and edge deployment", done: false },
];

const PRIVACY = [
  "Process only authorized camera feeds — never covert monitoring.",
  "Frames processed in memory; raw video is never stored by default.",
  "Face detection, not face recognition — no identity inference.",
  "Event logs carry metadata only: time, class, confidence, track ID.",
  "Logging is configurable and streams stay private in development.",
  "API hardened for production: HTTPS, scoped CORS, validated uploads.",
];

const CLASS_LEGEND = [
  { cls: "face", note: "yolov8m-face" },
  { cls: "person", note: "general model" },
  { cls: "car", note: "vehicle set" },
  { cls: "truck", note: "vehicle set" },
  { cls: "motorbike", note: "vehicle set" },
  { cls: "backpack", note: "object set" },
];

export default function LandingPage() {
  return (
    <main>
      <Hero />

      {/* marquee */}
      <div className="overflow-hidden border-y border-edge bg-abyss py-3">
        <div className="marquee-track flex w-max items-center gap-10">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span
              key={i}
              className="flex items-center gap-10 font-mono text-[11px] tracking-[0.34em] text-mist"
            >
              {m}
              <span className="h-1 w-1 rotate-45 bg-signal/70" />
            </span>
          ))}
        </div>
      </div>

      {/* problem / layer */}
      <section className="mx-auto max-w-[1500px] px-4 py-24 sm:px-6">
        <SectionTag index="01" label="WHY" />
        <div className="mt-8 grid gap-10 lg:grid-cols-2 lg:gap-16">
          <Reveal>
            <h2 className="text-4xl font-bold leading-[1.02] tracking-tight sm:text-5xl">
              Too many feeds.
              <br />
              <span className="text-mist">Too few eyes.</span>
            </h2>
            <p className="mt-6 max-w-md leading-relaxed text-pale/70">
              Border CCTV generates a continuous flood of video, but attention
              does not scale with camera count. Operators juggle dozens of
              streams; events go unseen; footage is reviewed only after the
              fact.
            </p>
          </Reveal>
          <Reveal delay={0.12}>
            <h2 className="text-4xl font-bold leading-[1.02] tracking-tight text-signal text-glow sm:text-5xl">
              An analytic layer on existing metal.
            </h2>
            <p className="mt-6 max-w-md leading-relaxed text-pale/70">
              Pixel Intelligence bolts onto the cameras already mounted on the
              fence.
              YOLO reads every frame, tracking holds identity steady, and a
              Postgres ledger turns motion into auditable data — without
              replacing a single camera.
            </p>
            <Link
              href="/console"
              className="mt-7 inline-flex items-center gap-2 font-mono text-[11px] tracking-[0.24em] text-signal hover:gap-3 transition-all"
            >
              SEE IT RUN LIVE
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Reveal>
        </div>
      </section>

      {/* architecture */}
      <section className="border-y border-edge bg-abyss/60">
        <div className="mx-auto max-w-[1500px] px-4 py-24 sm:px-6">
          <SectionTag index="02" label="PIPELINE" />
          <Reveal className="mt-8">
            <h2 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
              Frame in. <span className="text-signal">Signal out.</span>
            </h2>
            <p className="mt-5 max-w-xl leading-relaxed text-pale/70">
              The webcam in this prototype stands in for any authorized CCTV or
              RTSP source. Everything downstream — detection, tracking,
              counting, persistence — is source-agnostic.
            </p>
          </Reveal>
          <Reveal className="mt-12" delay={0.1}>
            <ArchitectureDiagram />
          </Reveal>
        </div>
      </section>

      {/* capabilities */}
      <section className="mx-auto max-w-[1500px] px-4 py-24 sm:px-6">
        <SectionTag index="03" label="CAPABILITIES" />
        <div className="mt-8 flex flex-wrap items-end justify-between gap-6">
          <h2 className="max-w-xl text-4xl font-bold tracking-tight sm:text-5xl">
            Built like an instrument, not a demo.
          </h2>
          <div className="flex flex-wrap gap-2">
            {CLASS_LEGEND.map((c) => (
              <span
                key={c.cls}
                className="flex items-center gap-2 border border-edge bg-panel px-2.5 py-1.5 font-mono text-[10px] tracking-[0.1em] text-mist"
                title={c.note}
              >
                <span
                  className="h-1.5 w-1.5 rounded-[1px]"
                  style={{ backgroundColor: GROUP_COLORS[c.cls === "face" ? "face" : c.cls === "person" ? "person" : c.cls === "backpack" ? "object" : "vehicle"] }}
                />
                {c.cls.toUpperCase()}
              </span>
            ))}
          </div>
        </div>
        <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.06}>
              <Panel className="group h-full p-6 transition-all duration-300 hover:-translate-y-1 hover:border-signal/40">
                <div className="flex items-center justify-between">
                  <span className="grid h-10 w-10 place-items-center border border-edge2 bg-abyss text-signal">
                    <c.icon className="h-4.5 w-4.5" />
                  </span>
                  <span className="font-mono text-[9px] tracking-[0.2em] text-mist">
                    {c.tag}
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-bold tracking-tight">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-pale/65">{c.body}</p>
              </Panel>
            </Reveal>
          ))}
        </div>
      </section>

      {/* counting semantics */}
      <section className="border-y border-edge bg-abyss/60">
        <div className="mx-auto max-w-[1500px] px-4 py-24 sm:px-6">
          <SectionTag index="04" label="DETECTION SEMANTICS" />
          <div className="mt-8 grid gap-3 lg:grid-cols-2">
            <Reveal>
              <Panel className="h-full p-8">
                <div className="font-mono text-[10px] tracking-[0.3em] text-mist">
                  CURRENT COUNT
                </div>
                <div className="mt-4 flex items-end gap-2">
                  <span className="font-mono text-7xl font-bold leading-none text-signal text-glow">
                    02
                  </span>
                  <span className="mb-2 font-mono text-xs text-mist">PERSONS VISIBLE</span>
                </div>
                <p className="mt-5 max-w-sm leading-relaxed text-pale/70">
                  A live reading of the frame — rises as subjects enter, falls as
                  they leave. One person standing still for 300 frames is{" "}
                  <span className="text-pale">one tracked ID</span>, not 300
                  detections.
                </p>
                <div className="mt-6 flex h-16 items-end gap-1.5">
                  {[35, 55, 80, 65, 40, 70, 90, 60, 45, 75, 50, 30].map((h, i) => (
                    <span
                      key={i}
                      className="w-full bg-signal/25 transition-all"
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </div>
                <div className="mt-2 font-mono text-[9px] tracking-[0.2em] text-mist">
                  OSCILLATES WITH THE SCENE
                </div>
              </Panel>
            </Reveal>
            <Reveal delay={0.1}>
              <Panel className="h-full p-8">
                <div className="font-mono text-[10px] tracking-[0.3em] text-mist">
                  EVENT COUNT
                </div>
                <div className="mt-4 flex items-end gap-2">
                  <span className="font-mono text-7xl font-bold leading-none text-flare">
                    08
                  </span>
                  <span className="mb-2 font-mono text-xs text-mist">UNIQUE EVENTS LOGGED</span>
                </div>
                <p className="mt-5 max-w-sm leading-relaxed text-pale/70">
                  An append-only ledger keyed by tracking ID. When a subject
                  first crosses the threshold of confidence, one row is written
                  to Postgres — a permanent, auditable record.
                </p>
                <div className="mt-6 flex h-16 items-end gap-1.5">
                  {[10, 22, 35, 42, 55, 66, 74, 82, 88, 93, 97, 100].map((h, i) => (
                    <span
                      key={i}
                      className="w-full bg-flare/25"
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </div>
                <div className="mt-2 font-mono text-[9px] tracking-[0.2em] text-mist">
                  MONOTONIC — ONLY GROWS
                </div>
              </Panel>
            </Reveal>
          </div>
        </div>
      </section>

      {/* roadmap + privacy */}
      <section className="mx-auto max-w-[1500px] px-4 py-24 sm:px-6">
        <div className="grid gap-16 lg:grid-cols-2">
          <div>
            <SectionTag index="05" label="ROADMAP" />
            <h2 className="mt-8 text-4xl font-bold tracking-tight sm:text-5xl">
              From prototype
              <br />
              to perimeter.
            </h2>
            <div className="mt-10 space-y-0.5">
              {ROADMAP.map((r, i) => (
                <Reveal key={r.label} delay={i * 0.05}>
                  <div className="group flex items-center gap-4 border-b border-edge py-4">
                    {r.done ? (
                      <span className="grid h-6 w-6 shrink-0 place-items-center border border-signal/50 bg-signal/10">
                        <Check className="h-3.5 w-3.5 text-signal" />
                      </span>
                    ) : (
                      <span className="grid h-6 w-6 shrink-0 place-items-center border border-edge2">
                        <Circle className="h-2.5 w-2.5 text-mist" />
                      </span>
                    )}
                    <span className={r.done ? "text-pale/85" : "text-mist"}>
                      {r.label}
                    </span>
                    <span className="ml-auto font-mono text-[9px] tracking-[0.22em]">
                      {r.done ? (
                        <span className="text-signal">SHIPPED</span>
                      ) : (
                        <span className="text-mist">PLANNED</span>
                      )}
                    </span>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>

          <div>
            <SectionTag index="06" label="PRIVACY BY DESIGN" />
            <h2 className="mt-8 text-4xl font-bold tracking-tight sm:text-5xl">
              Surveillance
              <br />
              <span className="text-mist">with a conscience.</span>
            </h2>
            <Panel className="mt-10 p-6 sm:p-8" tone="border-signal/40">
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-signal" />
                <span className="font-mono text-[11px] tracking-[0.26em] text-signal">
                  OPERATING CONSTRAINTS
                </span>
              </div>
              <ul className="mt-6 space-y-4">
                {PRIVACY.map((p) => (
                  <li key={p} className="flex gap-3 text-sm leading-relaxed text-pale/75">
                    <StatusDot tone="signal" ping={false} className="mt-1.5 shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-edge bg-abyss/60">
        <div className="mx-auto max-w-[1500px] px-4 py-24 text-center sm:px-6">
          <Reveal>
            <div className="font-mono text-[11px] tracking-[0.34em] text-mist">
              THE GRID IS ALREADY WATCHING
            </div>
            <h2 className="mx-auto mt-5 max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
              Step into the{" "}
              <span className="text-signal text-glow">control room</span>.
            </h2>
          </Reveal>
          <Reveal delay={0.12}>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/console"
                className="group flex items-center gap-3 border border-signal/60 bg-signal/10 px-7 py-4 font-mono text-xs font-bold tracking-[0.24em] text-signal transition-all hover:bg-signal hover:text-ink"
              >
                LAUNCH LIVE CONSOLE
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/analytics"
                className="border border-edge2 px-7 py-4 font-mono text-xs tracking-[0.24em] text-pale/80 transition-colors hover:border-pale/60 hover:text-pale"
              >
                VIEW ANALYTICS
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* footer */}
      <footer className="border-t border-edge">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-6 px-4 py-10 font-mono text-[10px] tracking-[0.16em] text-mist sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <div className="text-[13px] font-bold tracking-[0.3em] text-pale">
              PIXEL INTELLIGENCE
            </div>
            <div className="mt-2">
              SIH 187 / SIH26187 — AI VIDEO ANALYTICS FOR BORDER SURVEILLANCE
            </div>
          </div>
          <div className="max-w-md leading-relaxed">
            PROTOTYPE FOR LEARNING AND SIH DEMONSTRATION. MODELS AND CONTRACTS
            HONOR THE YOLO + OPENCV + REST REFERENCE ARCHITECTURE. NOT FOR
            OPERATIONAL DEPLOYMENT.
          </div>
        </div>
      </footer>
    </main>
  );
}
