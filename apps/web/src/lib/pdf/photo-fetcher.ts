import dns from "node:dns/promises";
import net from "node:net";
import sharp from "sharp";
import { getApiBaseUrl } from "@/lib/config";
import type { SiteLog } from "@/lib/types";

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const CONCURRENCY_LIMIT = 4;

/**
 * Rewrites localhost signed media URLs to API_BASE_URL when running inside
 * containerized networks (e.g. Docker Compose where API_BASE_URL=http://api:8000).
 */
export function resolveServerMediaUrl(signedUrl: string): string {
  try {
    const target = new URL(signedUrl);
    const apiBase = new URL(getApiBaseUrl());
    const isLocalHost =
      target.hostname === "localhost" || target.hostname === "127.0.0.1";
    if (isLocalHost && target.pathname.startsWith("/v1/media/")) {
      return `${apiBase.origin}${target.pathname}${target.search}`;
    }
    return signedUrl;
  } catch {
    return signedUrl;
  }
}

function isPrivateOrDisallowedIp(ip: string): boolean {
  if (net.isIPv4(ip)) {
    const parts = ip.split(".").map(Number);
    if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return true;
    const [a, b] = parts;
    if (a === undefined || b === undefined) return true;
    if (a === 0 || a === 10 || a === 127) return true;
    if (a === 169 && b === 254) return true; // Cloud metadata / link-local
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
    return false;
  }
  if (net.isIPv6(ip)) {
    const lower = ip.toLowerCase();
    if (lower.startsWith("::ffff:")) {
      const mapped = lower.slice(7);
      if (net.isIPv4(mapped)) {
        return isPrivateOrDisallowedIp(mapped);
      }
      return true;
    }
    if (lower === "::" || lower === "::1") return true;
    if (lower.startsWith("fe80:") || lower.startsWith("fc") || lower.startsWith("fd")) {
      return true;
    }
    return false;
  }
  return false;
}

async function resolvesToPrivateOrDisallowedIp(host: string): Promise<boolean> {
  if (net.isIP(host)) {
    return isPrivateOrDisallowedIp(host);
  }
  try {
    const records = await dns.lookup(host, { all: true });
    if (records.length === 0) return true;
    return records.some((entry) => isPrivateOrDisallowedIp(entry.address));
  } catch {
    return true;
  }
}

export function isSafeMediaFetchUrl(resolvedUrl: string): boolean {
  try {
    const url = new URL(resolvedUrl);
    const apiBase = new URL(getApiBaseUrl());
    // Allow internal calls explicitly targeting our configured API_BASE_URL /v1/media/*
    if (url.origin === apiBase.origin && url.pathname.startsWith("/v1/media/")) {
      return true;
    }
    if (url.protocol !== "https:") {
      return false;
    }
    const host = url.hostname.toLowerCase();
    if (
      host === "localhost" ||
      host.endsWith(".local") ||
      host.endsWith(".internal") ||
      host === "metadata.google.internal"
    ) {
      return false;
    }
    if (net.isIP(host) && isPrivateOrDisallowedIp(host)) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

const DATA_IMAGE_RE = /^data:image\/[a-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)$/i;

async function fetchAndCompressPhoto(signedUrl: string): Promise<string | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);

  try {
    let raw: Buffer;
    const dataMatch = DATA_IMAGE_RE.exec(signedUrl);
    if (dataMatch?.[1]) {
      raw = Buffer.from(dataMatch[1], "base64");
    } else {
      const serverUrl = resolveServerMediaUrl(signedUrl);
      if (!isSafeMediaFetchUrl(serverUrl)) {
        return null;
      }
      const parsed = new URL(serverUrl);
      const apiBase = new URL(getApiBaseUrl());
      if (parsed.origin !== apiBase.origin) {
        if (await resolvesToPrivateOrDisallowedIp(parsed.hostname)) {
          return null;
        }
      }
      const res = await fetch(serverUrl, {
        signal: controller.signal,
        cache: "no-store",
        redirect: "error",
      });
      if (!res.ok) return null;
      const contentLenHeader = res.headers.get("content-length");
      if (contentLenHeader && Number(contentLenHeader) > MAX_PHOTO_BYTES) {
        return null;
      }
      raw = Buffer.from(await res.arrayBuffer());
    }
    if (raw.byteLength === 0 || raw.byteLength > MAX_PHOTO_BYTES) return null;

    const compressed = await sharp(raw)
      .rotate()
      .resize({ width: 360, height: 270, fit: "inside", withoutEnlargement: true })
      .jpeg({ quality: 75, mozjpeg: true })
      .toBuffer();

    return `data:image/jpeg;base64,${compressed.toString("base64")}`;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Fetches and compresses thumbnails for all uploaded photos in a day's logs.
 * Bounded concurrency avoids saturating sharp workers or socket pools.
 */
export async function fetchCompressedLogPhotos(
  logs: SiteLog[]
): Promise<Map<string, string>> {
  const jobs: Array<{ photoId: string; url: string }> = [];
  for (const log of logs) {
    for (const photo of log.photos ?? []) {
      if (photo.url) {
        jobs.push({ photoId: photo.id, url: photo.url });
      }
    }
  }

  const results = new Map<string, string>();
  let nextIdx = 0;

  async function worker(): Promise<void> {
    while (nextIdx < jobs.length) {
      const current = jobs[nextIdx++];
      if (!current) continue;
      const dataUri = await fetchAndCompressPhoto(current.url);
      if (dataUri) {
        results.set(current.photoId, dataUri);
      }
    }
  }

  const workers = Array.from(
    { length: Math.min(CONCURRENCY_LIMIT, jobs.length) },
    () => worker()
  );
  await Promise.all(workers);
  return results;
}
