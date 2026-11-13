import { ApiError, parseErrorResponse } from "./problem";

export async function bffFetch<T>(
  apiPath: string,
  init: RequestInit = {}
): Promise<T> {
  const normalized = apiPath.startsWith("/") ? apiPath : `/${apiPath}`;
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`/api/bff${normalized}`, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError({
      status: 503,
      code: "NETWORK_ERROR",
      title: "Network error",
      detail:
        err instanceof Error
          ? err.message
          : "Unable to communicate with server",
    });
  }

  if (res.status === 401) {
    const apiErr = await parseErrorResponse(res);
    if (typeof window !== "undefined") {
      window.location.assign("/login");
    }
    throw apiErr;
  }

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
