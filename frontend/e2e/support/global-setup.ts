/**
 * Refuse to run against anything but the real stack. A stand-in API on :8000
 * (a mock left running by an earlier session did exactly that) answers the
 * app's calls but not these checks, and the suite stops here instead of
 * passing against fake data.
 */
const BASE = "http://localhost:5173";

async function getJson(path: string): Promise<unknown> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) throw new Error(`${path} answered ${response.status}: is the real stack up? Run \`just up2\`.`);
  return response.json();
}

export default async function globalSetup(): Promise<void> {
  const health = (await getJson("/api/v1/health")) as { status?: string; service?: string };
  if (health.status !== "ok" || health.service !== "FirstSpot API") {
    throw new Error(`/api/v1/health is not the FirstSpot API: ${JSON.stringify(health)}`);
  }
  const index = (await getJson("/api/v1/prioritization/index/districts")) as { districts?: unknown[] };
  const count = index.districts?.length ?? 0;
  if (count < 200) {
    throw new Error(
      `the district index has ${count} districts; load the census and OSM data (just census-ingest, just osm-ingest).`,
    );
  }
}
