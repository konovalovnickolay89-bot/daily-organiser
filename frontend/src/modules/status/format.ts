import type { XMeter } from "../../api/types";

export function formatBytes(value: number | null): string {
  if (value === null || value < 0) return "Unknown";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatXLine(meter: XMeter | null | undefined): string {
  if (!meter?.enabled) return "Off";
  if (meter.attention === "auth") return "Reconnect";
  if (!meter.connected) return "Not connected";
  if (meter.backing_off && meter.credits_remaining === 0) return "Credits spent";
  if (meter.backing_off) return "Backing off";
  const credits = meter.credits_remaining;
  const rate = meter.rate_remaining;
  if (credits != null && rate != null) return `${credits} credits · ${rate} left`;
  if (credits != null) return `${credits} credits`;
  if (rate != null) return `${rate} left`;
  return "Not yet";
}

export function formatHouseTime(iso: string | null): string {
  if (!iso) return "Not yet";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Not yet";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
