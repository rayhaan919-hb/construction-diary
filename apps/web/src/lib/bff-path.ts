const ALLOWED_V1_ROOTS = new Set([
  "projects",
  "permits",
  "logs",
  "me",
  "media",
  "auth",
  "organization",
  "organizations",
  "billing",
  "invitations",
  "sync",
]);

export function validateBffPath(segments: string[] | undefined): string | null {
  if (!segments || segments.length < 2 || segments[0] !== "v1") {
    return null;
  }
  const resourceRoot = segments[1]?.toLowerCase();
  if (!resourceRoot || !ALLOWED_V1_ROOTS.has(resourceRoot)) {
    return null;
  }
  for (const seg of segments) {
    if (!seg || seg === "." || seg === ".." || /[\\?#%]/.test(seg)) {
      return null;
    }
  }
  return `/${segments.map((s) => encodeURIComponent(s)).join("/")}`;
}
