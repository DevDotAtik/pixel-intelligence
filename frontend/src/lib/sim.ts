// Shared simulation + classification constants.
// Client-safe: no Node imports allowed in this module.

export type DetectionGroup = "face" | "person" | "vehicle" | "object";

export const CLASS_GROUP: Record<string, DetectionGroup> = {
  face: "face",
  person: "person",
  car: "vehicle",
  truck: "vehicle",
  bus: "vehicle",
  motorbike: "vehicle",
  backpack: "object",
  suitcase: "object",
};

export const GROUP_LABEL: Record<DetectionGroup, string> = {
  face: "Faces",
  person: "Persons",
  vehicle: "Vehicles",
  object: "Objects",
};

export const GROUP_COLORS: Record<DetectionGroup, string> = {
  face: "#ffb224",
  person: "#3ef2a6",
  vehicle: "#4cc9f0",
  object: "#a78bfa",
};

export const GROUP_EVENT: Record<DetectionGroup, string> = {
  face: "FACE_DETECTED",
  person: "PERSON_DETECTED",
  vehicle: "VEHICLE_DETECTED",
  object: "OBJECT_DETECTED",
};

export const EVENT_TYPES = [
  "FACE_DETECTED",
  "PERSON_DETECTED",
  "VEHICLE_DETECTED",
  "OBJECT_DETECTED",
] as const;

export function groupOf(className: string): DetectionGroup {
  return CLASS_GROUP[className] ?? "object";
}

export const VEHICLE_CLASSES = ["car", "truck", "bus", "motorbike"] as const;
export const OBJECT_CLASSES = ["backpack", "suitcase"] as const;

export interface CameraProfile {
  /** Stable camera code — matched against the `cameras` table by code. */
  code: string;
  name: string;
  zone: string;
  image: string;
  streamType: string;
  /** Composition targets for the live simulation. */
  persons: number;
  vehicles: number;
  objects: number;
  /** Normalized y-lanes (0..1 of frame height). */
  personLanes: number[];
  vehicleLanes: number[];
  activity: number;
}

export const CAMERA_PROFILES: CameraProfile[] = [
  {
    code: "CAM-01",
    name: "Fenceline North",
    zone: "Sector 4 · North Ridge",
    image: "/cams/fence.jpg",
    streamType: "webcam",
    persons: 2,
    vehicles: 1,
    objects: 0,
    personLanes: [0.66, 0.73, 0.8],
    vehicleLanes: [0.85],
    activity: 0.85,
  },
  {
    code: "CAM-02",
    name: "Gate Checkpoint 4",
    zone: "Crossing Point · Zeta",
    image: "/cams/checkpoint.jpg",
    streamType: "webcam",
    persons: 2,
    vehicles: 3,
    objects: 1,
    personLanes: [0.6, 0.7],
    vehicleLanes: [0.76, 0.83],
    activity: 1.15,
  },
  {
    code: "CAM-03",
    name: "Watchtower Echo",
    zone: "Sector 7 · Overwatch",
    image: "/cams/watchtower.jpg",
    streamType: "webcam",
    persons: 3,
    vehicles: 0,
    objects: 0,
    personLanes: [0.66, 0.74, 0.82],
    vehicleLanes: [],
    activity: 0.6,
  },
  {
    code: "CAM-04",
    name: "Causeway Freight",
    zone: "Sector 2 · Service Road",
    image: "/cams/road.jpg",
    streamType: "webcam",
    persons: 1,
    vehicles: 3,
    objects: 1,
    personLanes: [0.68],
    vehicleLanes: [0.68, 0.77, 0.85],
    activity: 1.0,
  },
];

export interface ModelInfo {
  key: string;
  file: string;
  task: string;
  classes: string[];
  status: "online" | "unavailable";
  size: string;
  map50: number | null;
  latency: string;
}

export const MODELS: ModelInfo[] = [
  {
    key: "face_model",
    file: "model.pt (compact face)",
    task: "Face Detection",
    classes: ["face"],
    status: "online",
    size: "6.0 MB",
    map50: 0.912,
    latency: "CPU optimized",
  },
  {
    key: "object_model",
    file: "model.pt",
    task: "Face-only model (general classes unavailable)",
    classes: ["FACE"],
    status: "online",
    size: "49.7 MB",
    map50: 0.884,
    latency: "~38 ms",
  },
  {
    key: "plate_model",
    file: "plate_model.pt",
    task: "License Plate OCR",
    classes: [],
    status: "unavailable",
    size: "—",
    map50: null,
    latency: "—",
  },
];

export const RUNTIME_CONFIG = {
  confidenceThreshold: 0.5,
  cameraIndex: 0,
  resolution: "640x480",
  device: "cpu",
  processEveryNFrames: 1,
};
