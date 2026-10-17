# Community Triage (PRIO-SV) and Visual System

**Feature branch:** `feat/visual-system-and-community-triage`
**Base commit:** `6dc3957`
**Created:** 2026-10-16
**Delivery strategy:** `ask-on-risk` (chain strategy undecided)

---

## Objective

Turn FirstSpot from a point-level infrastructure viewer into a decision-support
system that answers the three questions the Rally LATAM 2026 challenge states
literally: **who to attend first, where to concentrate effort, and what
resources to assign** after a catastrophic event.

## Problem

The current system prioritizes **places** — individual OpenStreetMap points
(schools, hospitals, shelters). That answers "what can I use when I get there",
but not "where do I send the brigade". Responders coordinating under time
pressure need a ranked list of **populated territories**, not a map of buildings.

Three gaps block that today:

1. No population data. There is no way to know how many people a decision affects.
2. No formal prioritization method. Any ranking would be an invented formula,
   indefensible in front of a jury or a real emergency committee.
3. No evidence of human presence at event time. A census says where people
   *sleep*, not where they *were* at 03:00 on a Tuesday.

## Why this approach

The prioritization index mirrors **INFORM Risk** (JRC European Commission +
IASC) rather than inventing weights, and normalizes with the **CDC/ATSDR Social
Vulnerability Index** method. Both are published, auditable, and replicable in
plain SQL. When asked "why those weights?", the answer cites a standard instead
of a preference.

---

## Scope

### In scope

- Census + official cartography ingestion into PostGIS
- `PRIO-SV` community prioritization index at district (ADM3) level
- Resource requirement translation using Sphere Handbook minimums
- Voluntary anonymous location sharing with privacy-by-design safeguards
- Visual system rework toward a matte, dense, professional EOC look
- Offline-first capability and real-time push for inter-agency coordination

### Out of scope

- Vector tiles (MVT) migration — documented as a national scaling path only.
  Current bottleneck is live Overpass ingestion, not DOM rendering.
- Any claim of casualty counts. The system reports *estimated exposed
  population*, never victims.
- Copernicus EMS activation (not self-service for El Salvador).

---

## Constraints

### Legal (non-negotiable)

El Salvador has an **active data protection law**: Decreto Legislativo 144,
*Ley para la Protección de Datos Personales*, published 15-Nov-2024
(DO 219, Tomo 445), in force since ~23-Nov-2024 per Art. 64.

- **Dual legal basis required.** Art. 5-g-1 (consent) covers voluntary capture.
  Art. 5-g-4 / Art. 28-c (vital interest) covers institutional consultation
  after the event, when the person can no longer consent.
- **Art. 3-c excludes public security but NOT civil protection** → the DGPC is
  fully subject to the law.
- **A declared state of emergency grants nothing.** Decreto 777 Art. 24,
  verbatim: *"El decreto de Estado de Emergencia no implica la suspensión de
  las garantías constitucionales."* Design as if it is never declared.

### Engineering (derived from the privacy research)

- **One point per person. Never a trace.** de Montjoye et al., *Scientific
  Reports* 3:1376 (2013): four spatio-temporal points uniquely identify 95% of
  1.5M individuals, and uniqueness decays only with the 1/10 power of
  resolution — lowering precision barely helps. A stored history is a
  surveillance dataset, not a rescue tool.
- Never publish an individual point. Aggregate to H3 cells (r7 ≈ 5.16 km² or
  r8 ≈ 0.74 km²) and suppress cells under threshold *k*.
- Opaque rotating token, no user account. 24h rotation, 14-day hard retention
  (Apple/Google Exposure Notification model). Mandatory `expiry_date` per
  record (PFIF 1.3 pattern).
- Public aggregated view strictly separated from audited institutional query.
  Follow **Ushahidi** (stores PII, never exports it), not Person Finder
  (public by design).
- Explicit disclaimer: registering **does not guarantee rescue**.

### Methodological

- **Fixed min/max normalization bounds per indicator.** Normalizing against the
  current event's range destroys comparability across events and over time.
- Equal weights by design at variable level (CDC SVI); the only declared weight
  is INFORM's 1/3 per dimension.
- Do not use PCA/SoVI for an operational index — Spielman et al. (2020) showed
  rankings do not converge when the set of units changes.
- Declare the spatial assignment rule (intersect vs centroid changes exposed
  counts by orders of magnitude).

---

## The PRIO-SV index

Unit of analysis: **DEGURBA sub-district polygon (902 units at level 2)**,
aggregatable to district (263), municipality (45) and department (17) for the
command view.

Why not census segments: the 10,291 segment polygons carry official geometry
but **zero population attributes**, and the microdata's finest geographic
variable is `DISTO` (6-digit district). Populating segments would require
dasymetric modeling, not a join. DEGURBA is the compromise — it carries real
population, households and dwellings, and is 3.4× finer than district.

```
PRIO = (H&E)^(1/3) × (V)^(1/3) × (LCC)^(1/3)        range 0-10
```

Source: INFORM Concept and Methodology 2017, Equation 1 — *"a multiplicative
equation where each of the dimensions is treated equally"*. Risk is zero if any
dimension is zero, so a district with no shaking is not prioritized for being poor.

| Dimension | Source | Content |
|---|---|---|
| **H&E** Hazard & Exposure | Live APIs | Max MMI per district via zonal statistics over USGS ShakeMap `cont_mi.json`; `log(population in cells with MMI ≥ VI)`, both absolute and relative, arithmetic mean |
| **V** Vulnerability | Census 2024 | Socio-economic (no piped water, no sanitation, no electricity, dirt floor, precarious materials, head without basic education) ⊗ Vulnerable groups (≥65, ≤5, disability, single-parent households, overcrowding) |
| **LCC** Lack of Coping Capacity | OSM + PostGIS | Network distance to nearest hospital / fire station, road density, % population >5 km from primary road, usable shelter presence. **Institutional sub-dimension is a declared gap** — no published subnational DRR capacity indicator exists for El Salvador |

Aggregation inside each dimension: **geometric mean**, equal weights.
Normalization: CDC SVI percentile method (EPL → SPL → RPL), equal weights, no PCA.
Color classes: the four official DGPC alert levels (verde / amarilla / naranja / roja).

### Resource translation (Sphere Handbook 2018)

For each district in red/orange class with `P` estimated exposed population:

- Water: `15 × P` L/day (20 × P in extreme heat); taps `≥ P/250`; water point ≤500 m
- Food: `2100 × P` kcal/day
- Shelter: `3.5 × P` m² (4.5 if urban with internal services)

Presented as **"Sphere minimum requirement"**, never as "resources to deliver".

---

## Data sources (verified)

| Source | Access | Note |
|---|---|---|
| USGS FDSN / ShakeMap / PAGER | **No API key** | `earthquake.usgs.gov/fdsnws/event/1/query` → GeoJSON; ShakeMap `cont_mi.json` for MMI contours |
| GDACS | Free | Query one alert level at a time — requesting all three returns only green |
| NASA FIRMS | Free key | 5000 req/10 min, ~3h latency |
| HDX COD-AB SLV | Free | Use HDX files, **not** the live geoservice (frozen since Feb 2025) |
| Geofabrik SLV | ODbL 1.0 | `el-salvador-latest.osm.pbf`, 33 MB, daily |
| GHS-POP R2023A | Free | Outperformed WorldPop in 24-country validation |
| MARN / DGPC | **No API** | HTML only; parameters explicitly preliminary |

### Census 2024 — acquired and verified

VII Censo de Población y VI de Vivienda 2024 (ONEC/BCR). Population 6,029,976.

**Access method:** `poblacion.bcr.gob.sv` is an **ArcGIS Hub site**, not a
download page. Org `bcrsv`, orgId `xSn1Pefr3M9zkw7Z`, 600 public items
(348 Feature Services) queryable through the ArcGIS REST API — no scraping,
paginable, idempotent. Export with `outSR=4326`.

Downloaded: 37 files, 570 MB in `data/census/raw/` (gitignored, must be
regenerable by script).

**Geographic key** — zero-padded nested strings, concatenated hierarchy:
`id_depto "01"` (2) → `id_mun "0101"` (4) → `id_distrito "010101"` (6) →
`idsegmento "0101010001"` (10). This is the DIGESTYC/BCR-CNR code, **not**
ISO 3166-2:SV; a 14-row mapping table is needed to interoperate.

Reconciliation verified: 5,922,921 georeferenced + 107,055 (`id_depto='15'`,
"Otros", no geometry) = 6,029,976 exactly.

#### Data gotchas — must be handled in ingestion

- **`Total_Personas` in `distritos_poblacion_edad_sexo.geojson` is wrong**
  (sums 5,843,393). Use `Hombre + Mujer` (5,922,921) or the age bands.
- Filter sentinels: `id_depto='15'` ("Otros") and `'AAA'` / `'RRAA'`
  aggregate-total rows.
- **Construction quality exists only at department level** (14 rows) — the
  single most relevant variable for seismic risk is the most aggregated one.
  District-level requires processing the 1.66 GB microdata.
- Geometry ships at full precision (DEGURBA 162 MB, segments 164 MB).
  `ST_SimplifyPreserveTopology` and ~6-decimal rounding before serving.

#### Statistical secrecy — binding constraint

No license is published (`licenseInfo` empty on every item). The applicable
regime is legal, not contractual: **Ley Especial de Estadística y Censos
(D.L. 904), Arts. 24, 25, 33 and 35** — statistical secrecy, aggregate-only
dissemination, and a **minimum threshold of 3 units per published cell**.

Any derived cell with fewer than 3 units must be suppressed before exposure
through an API. Attribute as "BCR/ONEC, CPV 2024".

**Note the convergence:** this threshold and the k-anonymity suppression
required for voluntary location (Phase D) are the same mechanism. Build one
suppression layer and apply it to both.

---

## Visual system

Derived from RustGIS `crates/ui-egui/src/theme.rs`. RustGIS has **no CSS** — it
is egui painted to a WASM canvas — so every value was hand-translated.

**Accent decision (user, 2026-10-16):** signal lime `#88d623` stays as **brand
only** (logo, splash, header). Operational UI uses blue (`#5B8DF6` dark /
`#2563EB` light), freeing green for exclusive semantic use. Under pressure an
operator must not confuse "selected" with "all clear".

Four rules that produce the matte look:

1. **Zero gradients.** Every surface is one flat color.
2. **Elevation is a 1px border, never a shadow.** Shadows only on genuinely
   floating elements: menus, dialogs, toasts, map popups.
3. **Narrow lightness band.** Dark surfaces span `#12151A → #262C34` (~20
   values). Current tokens span 15→67 and are green-tinted — that is why it
   does not read as matte.
4. **Mute the basemap at the source.** Use Positron / Dark Matter tiles.
   A CSS `grayscale()` filter produces the washed-out look.

Density: 22px control height, 6×5 gaps, 12.5px body. Element Plus defaults to
32px — overrides are required or the shell stays twice as loose.

---

## Tasks

Route and trigger evidence recorded per task. Checked off only after observed
verification.

### Phase A — Visual system

- [x] **A1** Rebuild `frontend/src/style.css` token system: neutral narrow-band
  surfaces, brand/operational accent split, full geometry and typography scale.
  Keep existing token names (`--eoc-bg-canvas`, etc.) so no component breaks.
  *Route: inline (1 file, fully specified).*
  **Commit `1316693`.** Verified: `pnpm build` (vue-tsc + vite) passes;
  `pnpm vitest run` 34/34 passing. CSS 450→456 KB (overrides added),
  JS unchanged at 1,332 KB — splitting is task E4.
- [x] **A2** Apply density overrides to Element Plus and the app shell
  (header 34px, status bar 26px, table header 24px, panel ranges).
  *Route: delegated writer (multi-file).*
  **Commit `2f0b08b`.** Verified: vue-tsc exit 0, vitest 34/34, build passing.
  Parent spot check re-ran vitest and build independently — both pass.
  Audited: 0 gradients and 0 hardcoded hex across App.vue, GeoRibbon and
  InstitutionAccessDialog.

  Two real bugs surfaced and were fixed along the way:
  - Accent fills used `--eoc-text-inverse`, which inverts per theme and
    therefore rendered dark text on blue in dark mode. Now `--eoc-on-accent`.
  - The `beacon-pulse` keyframe was declared in SyncHeaderBar's *scoped* style
    but consumed by HazardTelemetryStrip. It worked only because CSS keyframes
    ignore scoping — a latent coupling bug. Now global.

  Root cause of the large diff: `GeoRibbon.vue` carried a private 19-variable
  `--ribbon-*` palette shadowing the design tokens. Deleting that alias layer
  also removed its entire duplicated dark-mode block as dead weight.

- [x] **A3** Map treatment: Positron/Dark Matter basemaps, translucent floating
  controls at 75–92% alpha with 1px strong border, restyled Leaflet controls,
  legends and popups. *Route: delegated writer.*
  **Commit `8a9f2dc`.** Verified: vue-tsc exit 0, vitest 34/34, build passing.
  Audited: `rg 'filter:\s*(grayscale|saturate)'` returns 0 — muting comes from
  the tile source, not a filter.

  Known constraint: 23 literal hex values remain in this component and
  **cannot** be tokenized. Leaflet renders `L.circle` and `L.circleMarker` onto
  a canvas, and canvas does not resolve CSS custom properties. Only `divIcon`
  markup can use `var()`.

  Visual debt left open:
  - The heat gradient stays saturated (`#3b82f6 -> #ef4444`) because
    `updateHeatLayer` was out of scope. The legend bar mirrors it deliberately,
    so both move together or not at all.
  - `GROUP_COLORS` lives in `frontend/src/api/client.ts`, outside the authorized
    surface, so group fills keep their saturated hues.
- [ ] **A4** Decompose `VulnerabilityHeatmapCanvas.vue` (1871 lines) into
  composables. **Must run after A3 and before C5** — C5 adds the community
  triage layer to this same component, and past ~2500 lines it stops being
  refactorable at all. Sequence it so no writer is inside the file.

  Target split, container-presentational applied to Vue: the `.vue` file keeps
  only template, props/emits and orchestration; all Leaflet logic moves to
  `frontend/src/modules/map-viewer/composables/`:

  | Composable | Owns | Current lines |
  |---|---|---|
  | `useLeafletMap` | init, lifecycle, basemap switching, theme reaction | — |
  | `useMapMarkers` | `renderSinglePlaceMarker`, divIcon/circleMarker | ~360-461 |
  | `useHeatLayer` | `leaflet.heat` wiring | ~515-565 |
  | `useMarkerClustering` | proximity clustering, `CLUSTER_RADIUS_PX` | ~659-750 |
  | `useHazardLayer` | hazard overlays and radar circles | — |

  Hard requirement: **pure refactor, zero behavior change.** The 34 tests must
  pass untouched before and after. If a test needs editing, the refactor
  changed behavior and is wrong. Extract one composable per commit so each
  step is independently revertable.

### Phase B — Census ingestion

- [ ] **B1** Download script against the ArcGIS REST API (org `bcrsv`,
  orgId `xSn1Pefr3M9zkw7Z`, `outSR=4326`) so `data/census/raw/` is fully
  regenerable. Idempotent, resumable, with per-layer row-count assertions.
- [ ] **B2** Alembic migration `0003`: `census_admin_unit` (hierarchy, CNR
  SIRGAS geometry, simplified), `census_population_unit` (DEGURBA, 902 rows,
  GIST index), `census_indicator` (long/EAV so new releases need no migration),
  `census_segment` (geometry-only context). Add `census_unit_id` FK to
  `vulnerable_places`.
- [ ] **B3** Ingestion loaders with the gotchas enforced: reject
  `Total_Personas`, filter `id_depto='15'` and `'AAA'`/`'RRAA'` sentinels,
  simplify geometry, assert the 5,922,921 + 107,055 = 6,029,976 reconciliation.
- [ ] **B4** Spatial attachment of `vulnerable_places` to census units
  (`ST_Intersects`, cached in a column — not computed per query) and
  areal-weighted population estimate around each place. Use EPSG:5399
  (SIRGAS-ES2007) for area math; `location` is `GEOGRAPHY`, so buffers are
  already in meters.

### Phase C — PRIO-SV index

- [ ] **C1** Vulnerability dimension in SQL: CDC SVI percentile pipeline over
  census indicators. Regression-test geometric means against the INFORM
  Honduras workbook.
- [ ] **C2** Lack-of-coping-capacity dimension from OSM via PostGIS/pgRouting.
- [ ] **C3** Hazard & exposure dimension: USGS ShakeMap client, zonal statistics,
  fixed-bound normalization.
- [ ] **C4** Index composition endpoint + Sphere resource translation.
- [ ] **C5** Frontend community triage view: ranked district list, DGPC color
  classes, drill-down to places, uncertainty labeling.

### Phase D — Voluntary location

- [ ] **D1** Privacy design document: dual legal basis mapped per operation,
  retention schedule, revocation flow, threat model.
- [ ] **D2** Public capture flow: consent screen, opaque rotating token,
  single point, mandatory expiry, "does not guarantee rescue" disclaimer.
- [ ] **D3** Aggregated public view: H3 cells with k-suppression.
- [ ] **D4** Audited institutional query, strictly separated from the public view.

### Phase E — Field resilience

- [ ] **E1** Service worker + IndexedDB: cache base cartography and last known
  priority snapshot.
- [ ] **E2** Outbox queue for triage and notes captured without signal.
- [ ] **E3** SSE channel in FastAPI. **Note: the existing 2-minute
  `setInterval` only refreshes hazards — place activities never auto-refresh at
  all.** This closes a functional hole, not just latency.
- [ ] **E4** Code splitting. Real weight is Element Plus (440 KB CSS) and
  `VulnerabilityHeatmapCanvas.vue` (1871 lines, loads Leaflet), not the dialogs.

---

## Acceptance criteria

- PRIO-SV reproduces INFORM's geometric-mean behavior, validated against the
  INFORM Honduras workbook.
- Every district join is audited; non-matching codes are reported, not silently dropped.
- No individual location point is ever exposed through a public endpoint.
- The UI never reports victim counts — only estimated exposed population with
  its ShakeMap timestamp.
- Initial JS bundle under 400 KB.

## Applicable checks

- Backend: `uv run pytest` in `backend/`
- Frontend: `pnpm vitest run`, `pnpm vue-tsc -b`
- Build: `pnpm build`, inspect `dist/assets` sizes

## Progress

Research complete across all four lines: legal/privacy framing, visual
language, prioritization methodology, and census inventory.

- `6dc3957` — checkpoint of pre-existing uncommitted work on `main`
- `1316693` — **A1 done**: design token system rebuilt and verified

Census data acquired (37 files, 570 MB) with the access method, geographic key,
data defects and statistical-secrecy constraint all documented above.

## Next step

A2 + A3 — apply density and map treatment across the shell, as one delegated
writer. Then B1-B4 for census ingestion.

## Open decisions

- **Chain strategy undecided.** Forecast across phases A-E far exceeds the
  ~400 authored-line delivery budget. Before the branch grows further, choose
  `stacked-to-main` or `feature-branch-chain`.
- **`frontend-gis/`** — a second Vue 3 + Leaflet workspace exists, committed in
  `6dc3957` but unexplained. Confirm whether it is the intended target of the
  visual work or an abandoned experiment, before investing further in
  `frontend/`.
