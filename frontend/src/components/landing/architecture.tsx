import {
  BarChart3,
  Braces,
  Camera,
  LayoutDashboard,
  LocateFixed,
  ScanSearch,
  Sigma,
  Sparkles,
} from "lucide-react";
import { Panel } from "@/components/ui";

const NODES = [
  { icon: Camera, title: "CAMERA", sub: "webcam today · RTSP-ready", tag: "SRC" },
  { icon: ScanSearch, title: "OPENCV", sub: "frame ingestion pipeline", tag: "ING" },
  { icon: Sparkles, title: "YOLOv8m", sub: "face + object models", tag: "CNN" },
  { icon: LocateFixed, title: "TRACKING", sub: "persistent track IDs", tag: "TRK" },
  { icon: Sigma, title: "COUNTING", sub: "current vs event counts", tag: "CNT" },
  { icon: BarChart3, title: "ANALYTICS", sub: "rates, history, leaders", tag: "ANA" },
  { icon: Braces, title: "REST API", sub: "JSON contracts · /api/*", tag: "API" },
  { icon: LayoutDashboard, title: "DASHBOARD", sub: "this command surface", tag: "UI" },
];

export function ArchitectureDiagram() {
  return (
    <div className="relative">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {NODES.map((n, i) => (
          <Panel
            key={n.title}
            className="group bg-abyss p-4 transition-colors duration-300 hover:border-signal/40"
          >
            <div className="flex items-center justify-between">
              <span className="grid h-9 w-9 place-items-center border border-edge2 bg-panel text-signal transition-transform duration-500 group-hover:-rotate-6">
                <n.icon className="h-4 w-4" />
              </span>
              <span className="font-mono text-[9px] tracking-[0.3em] text-mist">
                {String(i + 1).padStart(2, "0")}·{n.tag}
              </span>
            </div>
            <div className="mt-4 font-mono text-sm font-bold tracking-[0.14em] text-pale">
              {n.title}
            </div>
            <div className="mt-1 font-mono text-[10px] leading-relaxed text-mist">
              {n.sub}
            </div>
          </Panel>
        ))}
      </div>
      <div className="mt-4 hidden items-center gap-4 sm:flex">
        <span className="font-mono text-[9px] tracking-[0.3em] text-mist">FRAME</span>
        <span className="flow-line h-[2px] flex-1 opacity-70" />
        <span className="font-mono text-[9px] tracking-[0.3em] text-signal">
          JSON IN &lt; 40 MS
        </span>
      </div>
    </div>
  );
}
