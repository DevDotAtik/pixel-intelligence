import {
  ArrowRight,
  CarFront,
  Check,
  Circle,
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

const GROUPS: Record<string, keyof typeof GROUP_COLORS> = {
  face: "face",
  person: "person",
  plate: "plate",
  car: "vehicle",
  truck: "vehicle",
  backpack: "object",
};

const MARQUEE = [
  "FACE DETECTION",
  "FACE-NAME RECOGNITION",
  "PERSON + CLOTHING",
  "DIRECTION TRACKING",
  "PLATE LOCATOR",
  "SUBJECT TIMELINE",
  "BORDER SECTORS",
  "MONGO PERSISTENCE",
];

const CAPABILITIES = [
  {
    icon: ScanFace,
    title: "Face Detection",
    body: "A compact face checkpoint (model.pt or yolov8m-face.pt) flags faces at 320px inference, sized for a CPU-only machine.",
    tag: "MODEL · face",
  },
  {
    icon: PersonStanding,
    title: "Person + Clothing",
    body: "Person runs out of the box in FACE→BODY fallback — face box scaled to a body, with a clothing colour classifier and direction per subject. Drop in yolov8n.pt for real boxes.",
    tag: "MODEL · fallback ready",
  },
  {
    icon: ShieldCheck,
    title: "Face-Name Recognition",
    body: "People enrolled through the Register page get a 64-dim CPU embedding; the live feed and analytics timeline show their name on match.",
    tag: "ALGO · 64-dim + cosine",
  },
  {
    icon: LocateFixed,
    title: "Deduplicated Sightings",
    body: "One subject reappearing is one sighting in MongoDB — opened when first seen, updated while present, closed when gone. No duplicate rows.",
    tag: "STORE · mongo sightings",
  },
  {
    icon: CarFront,
    title: "Plate Locator",
    body: "OpenCV morphology finds plate candidates without any model weights. OCR is optional — without tesseract, plate_text is null.",
    tag: "MODEL · opencv",
  },
  {
    icon: LineChart,
    title: "Live Analytics",
    body: "Subject timeline, per-class counts, hourly rhythms and confidence histograms computed on demand from the Mongo ledger.",
    tag: "VIEW · /api/stats",
  },
];

const ROADMAP: Array<{ label: string; done: boolean }> = [
  { label: "Face detection over authorized webcam", done: true },
  { label: "Face-name recognition for registered people", done: true },
  { label: "Person + clothing in FACE→BODY fallback", done: true },
  { label: "Tracking IDs and deduplicated subject sightings", done: true },
  { label: "MongoDB subject timeline (no Postgres)", done: true },
  { label: "Real person/vehicle boxes via yolov8n.pt", done: false },
  { label: "Plate OCR with tesseract", done: false },
  { label: "RTSP / CCTV stream ingest (replace webcam source)", done: false },
  { label: "Intrusion zones, line-crossing and loitering logic", done: false },
];

const PRIVACY = [
  "Process only authorized camera feeds — never covert monitoring.",
  "Frames processed in memory; raw video is never stored by default.",
  "Face-name recognition only for consented people enrolled through the Register page — no cloud, all local.",
  "Event logs carry metadata only: time, class, confidence, identity, camera.",
  "Logging is configurable and streams stay private in development.",
  "API hardened for production: HTTPS, scoped CORS, validated uploads.",
];

const CLASS_LEGEND = [
  { cls: "face", note: "model.pt" },
  { cls: "person", note: "face→body fallback" },
  { cls: "plate", note: "opencv locator" },
  { cls: "car", note: "needs yolov8n.pt" },
  { cls: "truck", note: "needs yolov8n.pt" },
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
              YOLO reads every frame, tracking holds identity steady, the
              registry matches names where consent exists, and a MongoDB
              subject timeline turns motion into auditable data — without
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
                  style={{ backgroundColor: GROUP_COLORS[GROUPS[c.cls]] }}
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
                  A deduplicated log keyed by subject. When a subject first
                  crosses the threshold, one sighting is opened in MongoDB —
                  updated while present, closed when gone. One reappearance,
                  one audit row.
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
