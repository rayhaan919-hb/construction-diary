const ARABIC_URDU_RE = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/;

const MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/**
 * Formats a YYYY-MM-DD project-local date string without browser timezone shift.
 */
export function formatDateShort(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
  if (!match) return isoDate;
  const year = Number(match[1]);
  const monthIdx = Number(match[2]) - 1;
  const day = Number(match[3]);
  const month = MONTHS_SHORT[monthIdx];
  if (!month || day < 1 || day > 31) return isoDate;
  return `${String(day).padStart(2, "0")} ${month} ${year}`;
}

export function formatTimeInZone(isoDateTime: string, timeZone: string): string {
  try {
    const dt = new Date(isoDateTime);
    if (Number.isNaN(dt.getTime())) return isoDateTime;
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone,
    }).format(dt);
  } catch {
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }).format(new Date(isoDateTime));
  }
}

export function formatDateTimeInZone(isoDateTime: string, timeZone: string): string {
  try {
    const dt = new Date(isoDateTime);
    if (Number.isNaN(dt.getTime())) return isoDateTime;
    const datePart = new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone,
    }).format(dt);
    const timePart = formatTimeInZone(isoDateTime, timeZone);
    return `${datePart} · ${timePart}`;
  } catch {
    return isoDateTime;
  }
}

export function getTodayInTimezone(timeZone: string): string {
  const now = new Date();
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  } catch {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  }
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || ms < 0) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function formatCountdown(daysToExpiry: number): string {
  if (daysToExpiry < 0) {
    return `${Math.abs(daysToExpiry)}d overdue`;
  }
  if (daysToExpiry === 0) {
    return "Expires today";
  }
  if (daysToExpiry === 1) {
    return "1d left";
  }
  return `${daysToExpiry}d left`;
}

export function getTextDirection(
  lang: string | null | undefined,
  text?: string | null
): "rtl" | "ltr" {
  if (lang === "ur" || lang === "ar") return "rtl";
  if (text && ARABIC_URDU_RE.test(text)) return "rtl";
  return "ltr";
}

export function getLanguageLabel(lang: string | null | undefined): string {
  switch (lang) {
    case "ur":
      return "Urdu";
    case "ar":
      return "Arabic";
    case "en":
      return "English";
    case "mixed":
      return "Mixed";
    case "unknown":
      return "Unknown";
    default:
      return "Transcript";
  }
}
