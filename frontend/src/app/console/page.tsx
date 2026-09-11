import { ConsoleClient } from "@/components/console/console-client";

export default async function ConsolePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const cam = typeof sp.cam === "string" ? sp.cam : undefined;
  return <ConsoleClient initialCamCode={cam} />;
}