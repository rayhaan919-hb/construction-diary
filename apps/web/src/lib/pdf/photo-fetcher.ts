import sharp from "sharp";
import { getApiBaseUrl } from "@/lib/config";
import type { SiteLog } from "@/lib/types";

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
      const res = await fetch(serverUrl, {
        signal: controller.signal,
        cache: "no-store",
      });
      if (!res.ok) return null;
      raw = Buffer.from(await res.arrayBuffer());
    }
    if (raw.byteLength === 0) return null;

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
 * Unavailable or invalid photos are gracefully skipped so PDF export always succeeds.
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
  const settled = await Promise.all(
    jobs.map(async ({ photoId, url }) => {
      const dataUri = await fetchAndCompressPhoto(url);
      return { photoId, dataUri };
    })
  );

  for (const item of settled) {
    if (item.dataUri) {
      results.set(item.photoId, item.dataUri);
    }
  }
  return results;
}
