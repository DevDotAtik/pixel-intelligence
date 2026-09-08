import { ConsoleClient } from "@/components/console/console-client";
import { CAMERA_PROFILES } from "@/lib/sim";

export default async function ConsolePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const cam = typeof sp.cam === "string" ? sp.cam : undefined;
  const idx = CAMERA_PROFILES.findIndex((p) => p.code === cam);
  return <ConsoleClient initialCam={idx >= 0 ? idx : 0} />;
}
