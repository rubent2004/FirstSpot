// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY
import type {
  GetHeatmapDataParams,
  HealthResponse,
  HeatmapResponse,
  ListPrioritizedPlacesParams,
  PlaceRead,
  PlaceTriageUpdate,
  PredefinedZoneRead,
  SyncPlacesResponse,
  SyncZoneRequest,
} from "./types.gen";

export interface ApiClientConfig {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

const defaultConfig: Required<ApiClientConfig> = {
  baseUrl: import.meta.env?.VITE_API_BASE_URL ?? "",
  fetchImpl: (...args: Parameters<typeof fetch>) => globalThis.fetch(...args),
};

function buildUrl(
  baseUrl: string,
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
): string {
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const fullPath = `${normalizedBase}${path}`;
  if (!query) return fullPath;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${fullPath}?${qs}` : fullPath;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
  query?: Record<string, string | number | boolean | null | undefined>,
  config: ApiClientConfig = {},
): Promise<T> {
  const baseUrl = config.baseUrl ?? defaultConfig.baseUrl;
  const fetchFn = config.fetchImpl ?? defaultConfig.fetchImpl;
  const url = buildUrl(baseUrl, path, query);

  const response = await fetchFn(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (errBody?.detail) {
        detail = String(errBody.detail);
      }
    } catch {
      // Ignore JSON parse errors on error payloads
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function getHealthStatus(
  config?: ApiClientConfig,
): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health", { method: "GET" }, undefined, config);
}

export async function listPredefinedZones(
  config?: ApiClientConfig,
): Promise<Array<PredefinedZoneRead>> {
  return requestJson<Array<PredefinedZoneRead>>("/api/v1/zones", { method: "GET" }, undefined, config);
}

export async function syncPlacesFromOverpass(
  body: SyncZoneRequest,
  config?: ApiClientConfig,
): Promise<SyncPlacesResponse> {
  return requestJson<SyncPlacesResponse>(
    "/api/v1/places/sync",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    undefined,
    config,
  );
}

export async function listPrioritizedPlaces(
  params?: ListPrioritizedPlacesParams,
  config?: ApiClientConfig,
): Promise<Array<PlaceRead>> {
  return requestJson<Array<PlaceRead>>(
    "/api/v1/places",
    { method: "GET" },
    params ? { ...params } : undefined,
    config,
  );
}

export async function getHeatmapData(
  params?: GetHeatmapDataParams,
  config?: ApiClientConfig,
): Promise<HeatmapResponse> {
  return requestJson<HeatmapResponse>(
    "/api/v1/places/heatmap",
    { method: "GET" },
    params ? { ...params } : undefined,
    config,
  );
}

export async function getPlaceById(
  placeId: string,
  config?: ApiClientConfig,
): Promise<PlaceRead> {
  return requestJson<PlaceRead>(
    `/api/v1/places/${encodeURIComponent(placeId)}`,
    { method: "GET" },
    undefined,
    config,
  );
}

export async function updatePlaceTriage(
  placeId: string,
  body: PlaceTriageUpdate,
  config?: ApiClientConfig,
): Promise<PlaceRead> {
  return requestJson<PlaceRead>(
    `/api/v1/places/${encodeURIComponent(placeId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
    undefined,
    config,
  );
}
