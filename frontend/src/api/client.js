const base = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageFrom(payload, status) {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (payload && Array.isArray(payload.detail)) return "That could not be saved.";
  if (status === 0) return "The house log is not reachable.";
  return "The house log could not be reached.";
}

export async function request(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  const init = { ...options, headers };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(`${base}${path}`, init);
  } catch {
    throw new ApiError("The house log is not reachable.", 0);
  }

  if (response.status === 204) return null;

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    throw new ApiError(messageFrom(payload, response.status), response.status);
  }
  return payload;
}
