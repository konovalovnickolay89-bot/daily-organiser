const base = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ErrorPayload = {
  detail?: unknown;
} | null;

function messageFrom(payload: ErrorPayload, status: number): string {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (payload && Array.isArray(payload.detail)) return "That could not be saved.";
  if (status === 0) return "The house log is not reachable.";
  return "The house log could not be reached.";
}

export type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  const init = { ...options, headers } as RequestInit;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, init);
  } catch {
    throw new ApiError("The house log is not reachable.", 0);
  }

  if (response.status === 204) return null as T;

  const text = await response.text();
  let payload: ErrorPayload = null;
  if (text) {
    try {
      payload = JSON.parse(text) as ErrorPayload;
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    throw new ApiError(messageFrom(payload, response.status), response.status);
  }
  return payload as T;
}
