/**
 * Production-grade HTTP API Transport Layer.
 *
 * Enforces:
 * 1. Strict decoupling from UI presentation components.
 * 2. Proper error wrapping and status propagation.
 * 3. NO hardcoded mock responses in production builds.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly body: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...rest } = options;

  let url = endpoint;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      searchParams.append(key, String(value));
    }
    url += (url.includes("?") ? "&" : "?") + searchParams.toString();
  }

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    ...rest,
  });

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = await response.text();
    }
    throw new ApiError(response.status, response.statusText, errorBody);
  }

  return response.json() as Promise<T>;
}
