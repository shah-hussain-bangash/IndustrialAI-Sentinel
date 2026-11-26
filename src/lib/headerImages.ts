import type { Page } from "../types";

// Local, licensed industrial photographs; decorative context, never a live site feed.
export const headerImages: Record<
  Page,
  { file: string; position: string; caption: string }
> = {
  conditions: {
    file: "process-machinery",
    position: "center 45%",
    caption: "Industrial equipment review workspace",
  },
  team: {
    file: "refinery-twilight",
    position: "center 60%",
    caption: "Connected industrial operations",
  },
  organization: {
    file: "refinery-modern",
    position: "center 62%",
    caption: "Industrial sites and operating areas",
  },
  overview: {
    file: "refinery-modern",
    position: "center 56%",
    caption: "Energy infrastructure",
  },
  assets: {
    file: "pump-installation",
    position: "center 82%",
    caption: "Pumps and rotating equipment",
  },
  monitor: {
    file: "compressor-room",
    position: "center 53%",
    caption: "Industrial compressor installation",
  },
  sensors: {
    file: "process-machinery",
    position: "center 45%",
    caption: "Process equipment and instrumentation",
  },
  intelligence: {
    file: "refinery-twilight",
    position: "center 60%",
    caption: "Process infrastructure at twilight",
  },
  knowledge: {
    file: "process-machinery",
    position: "center 65%",
    caption: "Industrial machinery and pipework",
  },
  reliability: {
    file: "pump-installation",
    position: "center 90%",
    caption: "Industrial pumps and motors",
  },
  orders: {
    file: "compressor-room",
    position: "center 68%",
    caption: "Equipment maintenance environment",
  },
  activity: {
    file: "refinery-night",
    position: "center 54%",
    caption: "Energy operations at night",
  },
  settings: {
    file: "refinery-modern",
    position: "center 72%",
    caption: "Industrial operating infrastructure",
  },
  production: {
    file: "refinery-night",
    position: "center 58%",
    caption: "Connected industrial operations",
  },
};
