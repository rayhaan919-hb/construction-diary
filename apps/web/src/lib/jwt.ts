/**
 * Edge-safe JWT expiration and optional HS256 cryptographic signature verifier.
 */
export interface JwtClaims {
  sub?: string;
  exp?: number;
  type?: string;
  must_change_password?: boolean;
}

function decodeBase64UrlToBytes(input: string): Uint8Array {
  const base64 = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function parseJwtClaims(token: string): JwtClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || !parts[1]) return null;
    const jsonBytes = decodeBase64UrlToBytes(parts[1]);
    const json = new TextDecoder().decode(jsonBytes);
    const payload = JSON.parse(json) as JwtClaims;
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

export function parseJwtExp(token: string): number | null {
  const claims = parseJwtClaims(token);
  if (!claims) return null;
  return typeof claims.exp === "number" && Number.isFinite(claims.exp)
    ? claims.exp
    : null;
}

export function isJwtExpiredOrExpiring(
  token: string | undefined,
  skewSeconds = 30
): boolean {
  if (!token) return true;
  const exp = parseJwtExp(token);
  if (exp === null) return true;
  const nowSec = Math.floor(Date.now() / 1000);
  return exp <= nowSec + skewSeconds;
}

export async function verifyJwtHs256Signature(
  token: string,
  secret: string
): Promise<boolean> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
      return false;
    }
    const headerBytes = decodeBase64UrlToBytes(parts[0]);
    const header = JSON.parse(new TextDecoder().decode(headerBytes)) as {
      alg?: string;
    };
    if (header.alg !== "HS256") return false;

    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"]
    );

    const signingInput = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
    const signatureBytes = decodeBase64UrlToBytes(parts[2]);
    const sigCopy = new Uint8Array(signatureBytes.length);
    sigCopy.set(signatureBytes);
    const inputCopy = new Uint8Array(signingInput.length);
    inputCopy.set(signingInput);
    return await crypto.subtle.verify("HMAC", key, sigCopy, inputCopy);
  } catch {
    return false;
  }
}
