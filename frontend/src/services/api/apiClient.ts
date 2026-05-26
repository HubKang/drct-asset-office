import { appConfig } from "@/services/config/appConfig";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type ApiRequestOptions = RequestInit & {
  timeoutMs?: number;
};

export async function apiRequest<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  const url = `${appConfig.apiBaseUrl}${path}`;
  const { timeoutMs, ...requestOptions } = options || {};
  const controller = new AbortController();
  const method = requestOptions.method || "GET";
  const timeout = timeoutMs
    ? setTimeout(() => {
        controller.abort();
      }, timeoutMs)
    : null;

  if (import.meta.env.DEV) {
    console.info(
      `[API REQUEST] ${JSON.stringify({
        method,
        path,
        body: requestOptions.body ?? null,
      })}`,
    );
  }

  const isFormData = typeof FormData !== "undefined" && requestOptions.body instanceof FormData;
  const headers: HeadersInit = isFormData
    ? { ...(requestOptions.headers || {}) }
    : {
        "Content-Type": "application/json",
        ...(requestOptions.headers || {}),
      };

  let response: Response;
  try {
    response = await fetch(url, {
      headers,
      ...requestOptions,
      signal: controller.signal,
    });
  } catch (error) {
    if ((error as Error)?.name === "AbortError") {
      throw new ApiError(408, "요청 시간이 초과되었습니다.");
    }
    throw error;
  } finally {
    if (timeout) clearTimeout(timeout);
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      message = data?.detail || message;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (import.meta.env.DEV) {
    console.info(
      `[API RESPONSE] ${JSON.stringify({
        method,
        path,
        status: response.status,
      })}`,
    );
  }

  return (await response.json()) as T;
}
