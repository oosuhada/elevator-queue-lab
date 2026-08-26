import { useEffect, useState } from "react";


export interface VisualCapability {
  webgl: boolean;
  lowPower: boolean;
  reason: string | null;
}

function inspectCapability(): VisualCapability {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return { webgl: false, lowPower: true, reason: "browser capability unavailable" };
  }
  if (navigator.userAgent.toLowerCase().includes("jsdom")) {
    return { webgl: false, lowPower: true, reason: "WebGL unavailable in test DOM" };
  }
  const canvas = document.createElement("canvas");
  const webgl = Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  const hardwareConcurrency = navigator.hardwareConcurrency || 8;
  const deviceMemory = Number((navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8);
  const saveData = Boolean((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData);
  const lowPower = hardwareConcurrency <= 4 || deviceMemory <= 4 || saveData;
  const reason = !webgl
    ? "WebGL unavailable"
    : lowPower
      ? "low-power browser profile"
      : null;
  return { webgl, lowPower, reason };
}

export function useVisualCapability(): VisualCapability {
  const [capability, setCapability] = useState<VisualCapability>({ webgl: false, lowPower: true, reason: "checking graphics capability" });
  useEffect(() => setCapability(inspectCapability()), []);
  return capability;
}
