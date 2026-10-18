import type { Call, Turn } from "./types";

const EASTERN = "America/New_York";

export function formatPhone(raw: string | null): string {
  if (!raw) return "Unknown number";
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) {
    return `(${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return raw;
}

function easternParts(iso: string): Intl.DateTimeFormatPart[] | null {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    timeZone: EASTERN,
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h12",
  }).formatToParts(date);
}

function part(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((item) => item.type === type)?.value ?? "";
}

export function formatClock(iso: string): string {
  const parts = easternParts(iso);
  if (!parts) return "—";
  const minute = part(parts, "minute").padStart(2, "0");
  return `${part(parts, "hour")}:${minute} ${part(parts, "dayPeriod").toUpperCase()}`;
}

export function formatDay(iso: string): string {
  const parts = easternParts(iso);
  if (!parts) return "";
  const today = easternParts(new Date().toISOString());
  if (
    today &&
    part(parts, "month") === part(today, "month") &&
    part(parts, "day") === part(today, "day")
  ) {
    return "Today";
  }
  return `${part(parts, "weekday")}`;
}

export function callerTitle(call: Call): string {
  const spoken = asTranscript(call.transcript)
    .filter((turn) => turn.role === "caller")
    .map((turn) => turn.text)
    .join(" ");
  const blob = `${spoken} ${call.summary ?? ""}`.toLowerCase();
  if (blob.includes("chase")) return "Chase fraud";
  if (blob.includes("harbor") || blob.includes("pharmacy")) return "Harbor Drugs";
  if (blob.includes("dental") || blob.includes("dentist")) return "Bayshore Dental";
  if (blob.includes("microsoft") || blob.includes("remote access")) return "Microsoft support";
  if (blob.includes("warranty")) return "Warranty call";
  if (blob.includes("ignore all") || blob.includes("admin mode") || blob.includes("screening robot")) {
    return "Injection attempt";
  }
  if (blob.includes("hung up") || blob.includes("hidden number") || blob.includes("no words")) {
    return "Hidden number";
  }
  if (blob.includes("mom")) return "“Mom”";
  if (blob.includes("national grid")) return "National Grid";
  if (blob.includes("irs")) return "IRS";
  if (blob.includes("bank of america")) return "Bank of America";
  return "Unknown caller";
}

export function formatWhen(iso: string): string {
  const parts = easternParts(iso);
  if (!parts) return "Unknown time";
  const minute = part(parts, "minute").padStart(2, "0");
  return `${part(parts, "weekday")} ${part(parts, "hour")}:${minute} ${part(parts, "dayPeriod").toUpperCase()}`;
}

export function formatRunAt(iso: string | undefined): string {
  if (!iso) return "Not recorded";
  const parts = easternParts(iso);
  if (!parts) return iso;
  const minute = part(parts, "minute").padStart(2, "0");
  return `${part(parts, "month")} ${part(parts, "day")}, ${part(parts, "hour")}:${minute} ${part(parts, "dayPeriod").toUpperCase()}`;
}

export function asStrings(value: unknown): string[] {
  if (typeof value === "string") {
    try {
      return asStrings(JSON.parse(value));
    } catch {
      return value ? [value] : [];
    }
  }
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === "string") return item;
    if (item && typeof item === "object") {
      const record = item as Record<string, unknown>;
      if (typeof record.label === "string") return record.label;
      if (typeof record.name === "string") return record.name;
      if (typeof record.text === "string") return record.text;
    }
    return JSON.stringify(item);
  });
}

export function asTranscript(value: unknown): Turn[] {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(parsed)) return [];
  return parsed.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const role = record.role === "caller" || record.role === "agent" ? record.role : null;
    const text = typeof record.text === "string" ? record.text : null;
    if (!role || !text) return [];
    return [{ role, text }];
  });
}

export function normalizeCall(raw: Call): Call {
  return {
    ...raw,
    transcript: asTranscript(raw.transcript),
    reasons: asStrings(raw.reasons),
    tactics: asStrings(raw.tactics),
    imessage_sent: Boolean(raw.imessage_sent),
  };
}

export function sortCalls(calls: Call[]): Call[] {
  return [...calls].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
}

export function previewLine(call: Call): string {
  if (call.summary) return call.summary;
  const caller = asTranscript(call.transcript).find((turn) => turn.role === "caller");
  return caller?.text ?? "No transcript yet.";
}

export function percent(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const points = value > 1 ? value : value * 100;
  return `${Math.round(points)}%`;
}

export function percentPoints(value: number | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  return Math.round(value > 1 ? value : value * 100);
}

export function challengeTurnIndex(call: Call): number {
  const transcript = asTranscript(call.transcript);
  const asked = call.challenge_asked?.trim().toLowerCase();
  if (!asked) return -1;
  const snippet = asked.slice(0, 48);
  return transcript.findIndex(
    (turn) =>
      turn.role === "agent" &&
      (turn.text.toLowerCase().includes(snippet) || asked.includes(turn.text.trim().toLowerCase())),
  );
}
