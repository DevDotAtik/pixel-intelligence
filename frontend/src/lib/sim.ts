// Shared simulation + classification constants.
// Client-safe: no Node imports allowed in this module.

export type DetectionGroup = "face" | "person" | "vehicle" | "object" | "plate";

export const CLASS_GROUP: Record<string, DetectionGroup> = {
  face: "face",
  person: "person",
  car: "vehicle",
  truck: "vehicle",
  bus: "vehicle",
  motorbike: "vehicle",
  backpack: "object",
  suitcase: "object",
  plate: "plate",
};

export const GROUP_LABEL: Record<DetectionGroup, string> = {
  face: "Faces",
  person: "Persons",
  vehicle: "Vehicles",
  object: "Objects",
  plate: "Plates",
};

export const GROUP_COLORS: Record<DetectionGroup, string> = {
  face: "#ffb224",
  person: "#3ef2a6",
  vehicle: "#4cc9f0",
  object: "#a78bfa",
  plate: "#ff6b6b",
};

export const GROUP_EVENT: Record<DetectionGroup, string> = {
  face: "FACE_DETECTED",
  person: "PERSON_DETECTED",
  vehicle: "VEHICLE_DETECTED",
  object: "OBJECT_DETECTED",
  plate: "PLATE_DETECTED",
};

export const EVENT_TYPES = [
  "FACE_DETECTED",
  "PERSON_DETECTED",
  "VEHICLE_DETECTED",
  "OBJECT_DETECTED",
  "PLATE_DETECTED",
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
    name: "Live Webcam",
    zone: "Workstation",
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
    zone: "Crossing Point",
    image: "/cams/checkpoint.jpg",
    streamType: "rtsp",
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
    zone: "Sector 7",
    image: "/cams/watchtower.jpg",
    streamType: "rtsp",
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
    zone: "Sector 2",
    image: "/cams/road.jpg",
    streamType: "rtsp",
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
  name: string;
  classes: string[];
  exists: boolean;
  note?: string;
}

/** 1:1 match with the backend MODEL_REGISTRY keys. */
export const MODELS: ModelInfo[] = [
  {
    key: "face",
    name: "Face Detection",
    classes: ["face"],
    exists: true,
  },
  {
    key: "person",
    name: "Person + Clothing Analyst",
    classes: ["person", "car", "truck", "bus", "motorbike"],
    exists: false,
    note: "Uses face→body fallback when no person model is installed.",
  },
  {
    key: "plate",
    name: "License Plate",
    classes: ["plate"],
    exists: false,
    note: "Uses OpenCV plate locator when no plate model is installed.",
  },
];

export const RUNTIME_CONFIG = {
  confidenceThreshold: 0.5,
  cameraIndex: 0,
  resolution: "640x480",
  device: "cpu",
  processEveryNFrames: 3,
};

/** Model key → color for the model-select dropdown badges. */
export const MODEL_COLORS: Record<string, string> = {
  face: "#ffb224",
  person: "#3ef2a6",
  plate: "#ff6b6b",
};