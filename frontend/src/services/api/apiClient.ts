import { appConfig } from "@/services/config/appConfig";

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(status: number, message: string, payload?: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
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
    throw new ApiError(
      0,
      "백엔드 검증 API에 연결하지 못했습니다. 백엔드 서버 상태, API 경로, CORS 설정을 확인해 주세요.",
      { cause: error instanceof Error ? error.message : String(error) },
    );
  } finally {
    if (timeout) clearTimeout(timeout);
  }

  if (!response.ok) {
    let payload: unknown = null;
    let bodyText = "";
    try {
      bodyText = await response.text();
      payload = bodyText ? JSON.parse(bodyText) : null;
    } catch {
      payload = bodyText;
    }
    const detail = payload && typeof payload === "object" ? (payload as Record<string, any>).detail : null;
    const rawError = payload && typeof payload === "object" ? (payload as Record<string, any>).raw_error : null;
    const validationMessage = payload && typeof payload === "object" ? (payload as Record<string, any>).validation_message : null;
    const serverMessage = Array.isArray(detail)
      ? "요청 형식이 맞지 않습니다. goal_text, gpt_result_text, parsed_goal 필드를 확인해 주세요."
      : detail && typeof detail === "object"
        ? ((detail as Record<string, any>).message || JSON.stringify(detail))
        : detail;
    const statusMessages: Record<number, string> = {
      404: "GPT 결과 검증 API 경로를 찾을 수 없습니다. 라우터 등록 또는 프론트 API 경로를 확인해 주세요.",
      422: "요청 형식이 맞지 않습니다. goal_text, gpt_result_text, parsed_goal 필드를 확인해 주세요.",
      500: "서버 내부 오류가 발생했습니다. 백엔드 로그를 확인해 주세요.",
    };
    const message = validationMessage || rawError || serverMessage || statusMessages[response.status] || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, payload);
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

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiError(0, "API 응답 JSON을 해석하지 못했습니다.", {
      cause: error instanceof Error ? error.message : String(error),
    });
  }
}
