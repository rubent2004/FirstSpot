import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const openapiPath = resolve(__dirname, "../../backend/openapi.json");
const outputDir = resolve(__dirname, "../src/api/generated");

const rawSchema = readFileSync(openapiPath, "utf-8");
const openapi = JSON.parse(rawSchema);

if (!String(openapi.openapi || "").startsWith("3.1")) {
  throw new Error(`Expected OpenAPI 3.1 schema, got ${openapi.openapi}`);
}

const schemas = openapi.components?.schemas ?? {};

function resolveSchemaType(prop) {
  if (!prop) return "unknown";
  if (prop.$ref) {
    return prop.$ref.split("/").pop();
  }
  if (Array.isArray(prop.anyOf)) {
    const unionParts = prop.anyOf.map((item) =>
      item.type === "null" ? "null" : resolveSchemaType(item),
    );
    return unionParts.join(" | ");
  }
  if (Array.isArray(prop.enum)) {
    return prop.enum.map((v) => JSON.stringify(v)).join(" | ");
  }
  if (prop.type === "string") return "string";
  if (prop.type === "integer" || prop.type === "number") return "number";
  if (prop.type === "boolean") return "boolean";
  if (prop.type === "array") {
    if (Array.isArray(prop.prefixItems) && prop.prefixItems.length > 0) {
      const tupleItems = prop.prefixItems.map((item) => resolveSchemaType(item));
      return `[${tupleItems.join(", ")}]`;
    }
    return `Array<${resolveSchemaType(prop.items)}>`;
  }
  if (prop.type === "object") {
    if (prop.additionalProperties) {
      const valType =
        typeof prop.additionalProperties === "object"
          ? resolveSchemaType(prop.additionalProperties)
          : "unknown";
      return `Record<string, ${valType}>`;
    }
    return "Record<string, unknown>";
  }
  return "unknown";
}

const typeBlocks = [
  "// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY",
  `export const OPENAPI_VERSION = ${JSON.stringify(openapi.openapi)} as const;`,
  "",
];

const ignoredSchemas = new Set(["HTTPValidationError", "ValidationError"]);

for (const [schemaName, schemaDef] of Object.entries(schemas)) {
  if (ignoredSchemas.has(schemaName)) continue;

  if (Array.isArray(schemaDef.enum)) {
    const union = schemaDef.enum.map((v) => JSON.stringify(v)).join(" | ");
    typeBlocks.push(`export type ${schemaName} = ${union};`);
    typeBlocks.push("");
    continue;
  }

  const requiredSet = new Set(schemaDef.required ?? []);
  const props = schemaDef.properties ?? {};
  typeBlocks.push(`export interface ${schemaName} {`);
  for (const [propName, propDef] of Object.entries(props)) {
    const isRequired = requiredSet.has(propName);
    const tsType = resolveSchemaType(propDef);
    typeBlocks.push(`  ${propName}${isRequired ? "" : "?"}: ${tsType};`);
  }
  typeBlocks.push("}");
  typeBlocks.push("");
}

const discoveredOperations = [];
for (const [pathKey, pathItem] of Object.entries(openapi.paths ?? {})) {
  for (const [method, opDef] of Object.entries(pathItem)) {
    if (typeof opDef === "object" && opDef !== null && opDef.operationId) {
      discoveredOperations.push({
        operationId: opDef.operationId,
        method: method.toUpperCase(),
        path: pathKey,
      });
    }
  }
}

discoveredOperations.sort((a, b) => a.operationId.localeCompare(b.operationId));

typeBlocks.push("export const OPENAPI_OPERATION_IDS = [");
for (const op of discoveredOperations) {
  typeBlocks.push(`  ${JSON.stringify(op.operationId)},`);
}
typeBlocks.push("] as const;");
typeBlocks.push("");
typeBlocks.push(
  "export type OpenApiOperationId = (typeof OPENAPI_OPERATION_IDS)[number];",
);
typeBlocks.push("");
typeBlocks.push("export interface ListPrioritizedPlacesParams {");
typeBlocks.push("  zone_name?: string | null;");
typeBlocks.push("  category?: PlaceCategory | null;");
typeBlocks.push("  vulnerability_group?: VulnerabilityGroup | null;");
typeBlocks.push("  attention_status?: AttentionStatus | null;");
typeBlocks.push("  min_urgency?: number | null;");
typeBlocks.push("  search?: string | null;");
typeBlocks.push("  latitude?: number | null;");
typeBlocks.push("  longitude?: number | null;");
typeBlocks.push("  radius_meters?: number | null;");
typeBlocks.push("  limit?: number;");
typeBlocks.push("}");
typeBlocks.push("");
typeBlocks.push("export interface GetHeatmapDataParams {");
typeBlocks.push("  zone_name?: string | null;");
typeBlocks.push("  category?: PlaceCategory | null;");
typeBlocks.push("  vulnerability_group?: VulnerabilityGroup | null;");
typeBlocks.push("  include_attended?: boolean;");
typeBlocks.push("}");
typeBlocks.push("");

const sdkContent = `// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY
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
  const fullPath = \`\${normalizedBase}\${path}\`;
  if (!query) return fullPath;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? \`\${fullPath}?\${qs}\` : fullPath;
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
    let detail = \`HTTP \${response.status}\`;
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
    \`/api/v1/places/\${encodeURIComponent(placeId)}\`,
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
    \`/api/v1/places/\${encodeURIComponent(placeId)}\`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
    undefined,
    config,
  );
}
`;

const indexContent = `// AUTO-GENERATED FROM ../backend/openapi.json — DO NOT EDIT MANUALLY
export * from "./types.gen";
export * from "./sdk.gen";
`;

mkdirSync(outputDir, { recursive: true });
writeFileSync(resolve(outputDir, "types.gen.ts"), typeBlocks.join("\n"), "utf-8");
writeFileSync(resolve(outputDir, "sdk.gen.ts"), sdkContent, "utf-8");
writeFileSync(resolve(outputDir, "index.ts"), indexContent, "utf-8");

console.log(
  `Generated OpenAPI 3.1 TypeScript SDK (${discoveredOperations.length} operations) in ${outputDir}`,
);
