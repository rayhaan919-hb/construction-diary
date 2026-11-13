export interface ProblemFieldError {
  field?: string;
  message?: string;
}

export interface ProblemPayload {
  type?: string;
  title?: string;
  status?: number;
  code?: string;
  detail?: string;
  errors?: ProblemFieldError[];
}

export class ApiError extends Error {
  status: number;
  code: string;
  title: string;
  detail?: string;
  errors?: ProblemFieldError[];

  constructor(params: {
    status: number;
    code: string;
    title: string;
    detail?: string;
    errors?: ProblemFieldError[];
  }) {
    const fieldMsg =
      params.errors && params.errors.length > 0
        ? params.errors
            .map((e) => [e.field, e.message].filter(Boolean).join(": "))
            .join("; ")
        : undefined;
    const message = params.detail || fieldMsg || params.title || `HTTP ${params.status}`;
    super(message);
    this.name = "ApiError";
    this.status = params.status;
    this.code = params.code;
    this.title = params.title;
    this.detail = params.detail;
    this.errors = params.errors;
  }
}

export async function parseErrorResponse(res: Response): Promise<ApiError> {
  const fallbackTitle = res.statusText || `Request failed (${res.status})`;
  try {
    const text = await res.text();
    if (!text) {
      return new ApiError({
        status: res.status,
        code: "HTTP_ERROR",
        title: fallbackTitle,
      });
    }
    const parsed = JSON.parse(text) as ProblemPayload;
    return new ApiError({
      status: typeof parsed.status === "number" ? parsed.status : res.status,
      code: parsed.code ?? "HTTP_ERROR",
      title: parsed.title ?? fallbackTitle,
      detail: parsed.detail,
      errors: parsed.errors,
    });
  } catch {
    return new ApiError({
      status: res.status,
      code: "HTTP_ERROR",
      title: fallbackTitle,
    });
  }
}

export function getErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return fallback;
}
