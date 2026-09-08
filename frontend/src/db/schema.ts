import {
  bigserial,
  index,
  integer,
  pgTable,
  real,
  serial,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

export const cameras = pgTable("cameras", {
  id: serial("id").primaryKey(),
  code: text("code").notNull().unique(),
  name: text("name").notNull(),
  zone: text("zone").notNull(),
  status: text("status").notNull().default("active"),
  streamType: text("stream_type").notNull().default("webcam"),
  resolution: text("resolution").notNull().default("1280x720"),
  fps: integer("fps").notNull().default(30),
  uptime: real("uptime").notNull().default(99.2),
  image: text("image").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const events = pgTable(
  "events",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    timestamp: timestamp("timestamp", { withTimezone: true })
      .notNull()
      .defaultNow(),
    eventType: text("event_type").notNull(),
    className: text("class_name").notNull(),
    confidence: real("confidence").notNull(),
    trackingId: integer("tracking_id").notNull(),
    cameraId: integer("camera_id")
      .notNull()
      .references(() => cameras.id),
  },
  (t) => [
    index("events_timestamp_idx").on(t.timestamp),
    index("events_camera_idx").on(t.cameraId),
    index("events_class_idx").on(t.className),
  ],
);
