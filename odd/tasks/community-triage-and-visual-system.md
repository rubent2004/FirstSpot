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
aggregatable to district (262), municipality (44) and department (14) for the
command view.

**Count correction (verified against the data, 2026-10-16):** earlier research
said 263 districts / 45 municipalities / 17 departments. Those figures counted
the `'Otros'` pseudo-unit, which has no geometry. The real post-D.L. 57/2023
structure is **14 / 44 / 262**. Published secondary summaries routinely inflate
these. Any assertion must use the corrected numbers.

Also: the segment layer has 10,291 features but only **10,290 real segments** —
one is an `idsegmento='0000000000'` national rollup.

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

- [x] **B1** Download script against the ArcGIS REST API. **Commit `51e62e7`.**
  `scripts/download_census.py`, 16 layers pinned by service + layer id +
  expected row count. All 16 resolve live and counts match. Re-download of 3
  layers verified `identical_properties` and `identical_rows` against the
  originals; resumability verified by deleting a file and a cached page.
- [x] **B2** Alembic migration `0003_census_2024`. **Commit `51e62e7`.**
  Applies cleanly, `0002 <-> head` round-trip verified, `alembic check` reports
  no drift. The `census_unit_id` FK on `vulnerable_places` was **not** added —
  it is B4 work and the writer's brief forbade touching existing tables.
- [x] **B3** Ingestion loaders. **Commit `51e62e7`.** Real 570 MB ingest in
  77.7s: 320 / 902 / 50,560 / 10,290 rows, reconciliation exact, re-run
  idempotent, geometry 570 MB -> 15 MB with zero invalid geometries,
  342 cells suppressed with none leaking value or share.

  Test-first observed honestly, 4 REDs: missing module, then two missing
  symbols, then a real `:param::text` bind-parameter failure. 142 tests pass
  (36 pre-existing untouched + 106 new).

### Data defects found during B3 that the research had missed

The research predicted five defects. Ingestion found four more:

1. **`Total_Personas` is defective in the municipality layer too**, not only
   the district layer. Both sum 5,843,393; 255 of 262 district rows disagree
   with `Hombre + Mujer`.
2. **`'15'` and `'RRAA'` are the same row**, not two sentinels (`Dep_id='15'`
   carries `Dep_min='RRAA'`). And a third undocumented family exists:
   `'00'`/`'0000'`/`'000000'` national rollups.
3. **Each department appears twice** in `estructuras_distritos` and
   `viviendas_particulares_distritos` — once correctly coded, once as
   `id_depto='00'`. Worse, the correctly coded dwellings row stores a raw
   count in its `porcentaje` column, not a fraction. Hence `normalize_share`.
4. **Department and district layers split 6 people differently between the
   sexes.** Grand totals agree exactly, so assertions run on the total only.

### Declared gap: construction materials

`material_pared` / `_tec` / `_pis` were **not** ingested. The source CSVs use
unlabelled `r1..rN` columns and the counts disagree with the published
dictionary (`_tec` has 9 columns for 8 categories, `_pis` 9 for 7). Inventing a
mapping would have produced plausible but wrong seismic vulnerability, so the
single most relevant variable for earthquake risk stays a declared gap.

PRIO-SV's V dimension therefore runs on: `poblacion`, `edad_sexo`,
`discapacidad`, `discapacidad_tipo`, `viviendas_particulares`, `estructuras`
and `hogar_parentesco` (which carries the `Monoparentales` variable).

- [x] **B4** Spatial attachment of `vulnerable_places` to census units and
  areal-weighted exposed-population estimate. **Commit `1c1c46b`.**
  *Route: delegated writer (multi-file).*
  Verified: 207 tests pass (142 pre-existing + 65 new), `alembic upgrade head`
  applies, `alembic check` reports no drift, `0003 <-> 0004` round-trip clean.
  Backfill from scratch attached 1,425 places; the second run reported
  `attached=0 detached=0`, so it is idempotent.

  `census_unit_id` is cached in the column and resolved with `ST_Intersects`,
  never per query. The on-demand endpoint
  `GET /places/{id}/population-exposure?radius_meters=` recomputes for any
  radius in 12–31 ms; the dispatch queue reads the cached 500 m estimate.

  **EPSG:5399 does not exist.** The research named it as "SIRGAS-ES2007", but
  it is absent from PROJ's `crs_view` and from PostGIS `spatial_ref_sys`, and
  the SIRGAS-ES2007.8 codes that do exist (5391 / 5392 / 5393) are geodetic
  only — there is no projected metric member. Area math uses **EPSG:32616**
  (WGS 84 / UTM zone 16N), which shares the WGS 84 datum with the stored
  `GEOGRAPHY`, so the transform needs no datum shift and no PROJ "ballpark"
  fallback. Measured on the westernmost DEGURBA unit — the worst case for a
  zone whose central meridian is 87°W — the areal weight differs from the
  geodesic weight by 1.5e-6 relative. EPSG:5460 (El Salvador Lambert) is
  metric and national but sits on the 1935 Ocotepeque datum.

  Declared spatial assignment rule: **intersection with areal weighting**.
  Centroid containment would report a whole sub-district or zero; plain
  intersection would assign a whole sub-district to any polygon merely
  touching the buffer.
- [x] **B5** `disclosure.py` moved to `app/core/privacy.py`. **Commit `69d1337`.**
  *Route: inline (pure move plus re-point).*
  Public API unchanged; `SuppressionPolicy(minimum_units=5,
  label="k-anonymity k=5")` verified as the Phase D path.

  **Incident:** the file rename was swept into `5f9abe1` (an A4 map-viewer
  commit) without its import re-points, leaving HEAD importing
  `app.modules.census.domain.disclosure` from both `loaders.py` and the census
  test module after that path had ceased to exist. `69d1337` repairs it. Cause:
  two writers on one branch at the same time, which is what single-threaded
  writes exist to prevent.
- [x] **B6** `just census-download`, `just census-ingest` and `just
  census-attach`. **Commit `cc4190a`.** *Route: inline (1 file).*
  Verified by running `just census-download --dry-run` against the real corpus.

### Phase C — PRIO-SV index

- [x] **C1** Vulnerability dimension. **Commits `8363739`, `dcf81cb`,
  `4877b2a`, `dcae80b`.** Verified: 304 tests pass (207 pre-existing + 97 new),
  `alembic check` clean. No migration needed — the index recomputes per
  request (66 ms query + 36 ms pipeline over 262 districts).

  **Validated against real geography, which is the check that mattered.**
  Top: Cacaopera, Victoria, Yamabal, Lislique — Morazán, Cabañas and La Unión,
  the poorest departments in every published Salvadoran poverty map. Bottom:
  Nuevo Cuscatlán and Antiguo Cuscatlán, the wealthiest districts in the
  country. The index is not inverted.

  Fully auditable: every score exposes its per-variable `E`, `universe`, `EP`
  and `EPL`, plus theme `SPL`/`RPL` and both the CDC and INFORM compositions.

  Index variables, built from inspected `category` values — vulnerable groups:
  `EP_AGE65`, `EP_AGE5`, `EP_DISABL`, `EP_SNGPNT`, `EP_CROWD`. Socioeconomic:
  `EP_RURAL` alone. Published but deliberately outside the index:
  `EP_DISPERSED` (nested inside `EP_RURAL`, would double-weight) and
  `EP_VACANT` (direction indefensible — empty dwellings mark both no local
  livelihood and remittance income).

### C1 limitations that must be stated whenever these scores are shown

1. **Urban poverty is invisible.** Apopa ranks 258 and Delgado 255 despite
   documented deprivation, because they are not rural. This is the direct cost
   of having no published socioeconomic variables at district level.
2. **No district can reach 10.** 102 of 262 districts share a rural share of
   exactly 1.0, so the single-variable socioeconomic theme saturates at
   RPL 0.8065. Observed maximum is 9.27. **Pinned as a test**, so ingesting a
   real socioeconomic variable will fail it — that failure is the wanted signal.
3. **No construction quality anywhere in V.** Adobe and reinforced concrete
   score identically. For a seismic prioritization tool this is the most
   consequential gap.
4. **Ageing wealthy districts rank low.** Antiguo Cuscatlán has the country's
   highest 65+ share (17.72%) and ranks 261. Correct for a relative index, but
   it conceals a real evacuation-assistance need.
5. **57 districts have at least one input summed over a withheld cell.** Worst
   relative case: San Isidro Labrador, `EP_AGE65` short by at most 12 of 586
   (2.048%). Zero districts withheld entirely. Published as lower bounds.
6. **Relative rank only.** A 10 means "ranked most vulnerable of 262 by this
   method" — not poverty, not damage, not casualties, and not comparable to
   another country.

### New data defect found during C1

**`estructuras` is unusable as a structure count.** Values are near-constant
per district (35,816-94,223) across districts whose population ranges
586-330,543, and sum to **17,215,235 nationally against 1,839,322 private
dwellings**. Excluded from the index.

Also excluded: crowding by rooms (rooms not published; proxied by persons per
household) and homeless/collective dwellings (withheld in 82 and 27 districts
respectively — ranking 180 districts against a variable 82 cannot report would
be dishonest).
- [x] **C2** Lack-of-coping-capacity dimension from OSM via PostGIS.
  *Route: delegated writer (multi-file).*
  Verified: 385 tests pass (304 pre-existing + 81 new), `alembic upgrade head`
  applies, `alembic check` reports no drift, `0004 <-> 0005` round-trip clean.
  Real national ingest: 2,072 facilities + 2,506 primary ways + 902 cached
  polygons in 75s; re-run reported identical counts, so it is idempotent.
  The index itself answers in **27 ms query + 17 ms pipeline** over 262
  districts, because the geometry is cached at ingest, not per request.

### C2: distance is geodesic, and that is declared everywhere

**pgRouting was not installed and could not be, so no distance here is a route.**
It is absent from `pg_available_extensions` in the pinned
`postgis/postgis:16-3.4-alpine` image, Alpine's package repository does not
carry it, and the image is declared in `docker-compose.yml` — outside the task's
authorised edit surface. Every distance is therefore `ST_Distance` on the
`GEOGRAPHY` column: **true metres on the WGS 84 ellipsoid, and a lower bound on
travel distance.**

That is carried in the names, not only in prose: columns are
`geodesic_metres_to_nearest_*`, the measure string says "a LOWER BOUND on travel
distance, never travel distance itself", `distance_basis` is a **top-level** API
field rather than buried in the methodology block, and the methodology publishes
`uses_network_routing: false` beside `uses_principal_components: false`.

The understatement is **not a constant factor**: it is largest in mountainous and
river-cut districts, which are exactly the districts this dimension exists to
find. Network routing is recorded as open work and the road geometry is already
stored for it.

### C2 indicator list, each verified against the real extract

| Variable | In index | Backing data |
|---|---|---|
| `LCC_HEALTHDIST` | **yes** | 184 hospitals + 518 clinics nationally; 262 distinct district values |
| `LCC_ROADDIST` | **yes** | 2,506 motorway/trunk/primary ways, 2,043 km; 262 distinct values |
| `LCC_HEALTHFAR` | no | share beyond 5 km; excluded as the same concept as `LCC_HEALTHDIST` |
| `LCC_ROADFAR` | no | same concept as `LCC_ROADDIST` |
| `LCC_SHELTER` | no | excluded on measured evidence (below) |
| `LCC_FIREDIST` | no | excluded on measured evidence (below) |

The two index variables correlate **0.18** over the 262 districts, so neither is
a disguised copy of the other — two collinear variables would have been an
undeclared double weight.

### Why the national extract was not optional

The existing Overpass corpus covers **24 of 262 districts, and 21 have a
hospital or clinic**. Computing distance-to-care against it gives a national mean
of **27.8 km and a maximum of 65.0 km**, against **3.8 km and 20.3 km** on the
national extract. The 27.8 km figure measures how far a district is from the
seven zones that were queried, and it would have ranked districts *plausibly* —
worst for the remote ones — for entirely the wrong reason. The Geofabrik extract
(ODbL 1.0, pinned file rather than live API) is what makes the dimension a
measurement rather than a map of our own ingestion.

### Two indicators rejected on measured evidence, not taste

1. **Fire stations.** The extract holds **18 nationally**, and the departments of
   **Santa Ana and Cabañas hold zero** — Santa Ana is the second city with about
   a quarter of a million people and certainly has a station. Only 12 of 262
   districts contain one, and the worst district measures 60 km. Including it
   would have scored Santa Ana as having no fire response at all.
2. **Shelter per capita.** 1,199 mapped schools against MINED's roughly 5,100
   centros escolares (~23%); 32 districts show zero, and **25 of those 32 are in
   the two most rural quartiles**, so the incompleteness is concentrated exactly
   where the index would read it as a finding. Dividing by population then
   *inverts* the direction: the density correlates **+0.18** with rural share
   while the raw count correlates **−0.35**, so rural villages would score as
   well sheltered because 1,900 people share one mapped school.

Both are still computed, cached and published as context variables so the
exclusions are checkable, and both carry their numbers in `exclusion_reason`.

### C2: fire stations were deliberately NOT added to `PlaceCategory`

The brief authorised extending the taxonomy if it stayed contained. It does not.
A fire station is a **responder asset, not a vulnerable place**: it needs no
`priority_score`, and it fits none of the four `VulnerabilityGroup` axes, so
adding it would have required a fifth group, which cascades into `GROUP_COLORS`
in `frontend/src/api/client.ts` — outside the authorised surface and already
flagged in A3. Fire stations are therefore ingested into the new
`osm_coping_facility` table, where they are nationally complete-as-mapped,
available to the map, and depended on by no score.

### C2 limitations that must be stated whenever these scores are shown

1. **LCC is infrastructure only.** The institutional sub-dimension carries zero
   variables because no published subnational DRR capacity indicator exists for
   El Salvador. It is published with a null score rather than imputed at the
   median, so INFORM's geometric mean reduces to the identity and **the LCC
   score IS the infrastructure score**. Pinned as a test, so a real
   institutional indicator will break it — that failure is the wanted signal.
2. **Every distance is a lower bound on travel distance**, understating exactly
   the districts the index is meant to find.
3. **A short distance means a facility is NEARBY, never that care is
   AVAILABLE.** OSM records the tag, not whether the hospital has power, staff
   or a standing roof after the event.
4. **Road classification is functional, not structural.** A district scores well
   for being near a road that may be unpaved, or that may be the first road a
   landslide closes.
5. **Shelter capacity is unmeasured**, so Sphere shelter minimums in C4 compute
   a *requirement* and must never be compared against an available-capacity
   figure, because none exists.
6. **Relative rank only**, among these 262 districts, by this method.

### C2 ranking: validated, with one documented divergence

Worst (rank 1 = worst coping capacity): **Jucuarán** (Usulután), **San Pablo
Tacachico** (La Libertad), **Cinquera** (Cabañas), **San Fernando**
(Chalatenango), **Jutiapa** (Cabañas), **Ojos de Agua** (Chalatenango),
**Lislique** (La Unión), **Tejutepeque**, **Victoria** (Cabañas), **Tacuba**
(Ahuachapán). Best: **Antiguo Cuscatlán**, **San Salvador**, **Colón**, El
Refugio, Turín, Santo Tomás, Sonzacate, Soyapango, San Rafael Obrajuelo,
Ilopango.

Chalatenango dominates the worst 40 (10 districts, most of any department),
La Unión contributes 4 and Cabañas 4 of the worst 10; San Salvador (8) and La
Libertad (7) dominate the best 40. The index is not inverted.

**The divergence: Morazán is NOT among the worst, contrary to the brief's
expectation** — it places 5 districts in the best 40, mean rank 165 of 262. The
cause is measurable: Morazán holds the **highest mapped primary-care density in
the country, 2.36 hospitals or clinics per 10,000 inhabitants** against Cabañas's
0.56, across 26 districts averaging only 50.6 km². Its mean population-weighted
distance to care is **2.23 km — shorter than San Salvador's own 2.36 km**.

So the index ranks Cabañas and Chalatenango worse than Morazán, and that
differentiation among three poor rural departments is what an infrastructure
-access measure *should* produce if the infrastructure genuinely differs. Morazán
topping the **V** dimension while scoring mid-table on **LCC** is not a
contradiction — it is the reason INFORM composes three dimensions instead of one.

**Unverified:** the plausible real-world explanation is MINSAL's post-2009 ECOS
Familiares / FOSALUD rural health-post expansion, which targeted Morazán
heavily. I could not check that against a MINSAL establishment register, because
none is published per district. Confirming it — or finding that Morazán is
simply mapped more intensively — is open work and is pinned as a test so an
inversion cannot be absorbed silently.

### C2 open work

- **Network routing.** Install pgRouting (needs `docker-compose.yml`, so the
  image must change — Alpine does not carry it; the Debian `postgis/postgis:16-3.4`
  image plus `postgresql-16-pgrouting` does), then
  `pgr_createTopology` over the already-ingested `osm_road_segment` geometry and
  republish the two distance variables as network distance. The extract reader
  and the road table are built for it; nothing else has to change.
- Verify Morazán's health-facility density against a MINSAL register.
- Obtain the DGPC fire-station list to promote `LCC_FIREDIST` unchanged.
- The three new tables are **migration-owned, not ORM-mapped**, matching the
  prioritization module's existing raw-`text()` read paths. Registering them in
  `alembic/env.py` needs that file in scope; `alembic check` is clean either way
  because `include_object` skips reflected tables absent from the metadata.
- [x] **C3** Hazard & exposure dimension. **Commit `e884cb9`.** USGS ShakeMap
  client, zonal statistics, fixed bounds MMI 4->0 / 10->10. 511 tests pass.
- [x] **C4** Composed index + Sphere translation. **Commit `e884cb9`.**
  Validated on the real 2001-02-13 M6.6 event: top 10 all in La Paz, Cuscatlan
  and Usulutan around the epicentre. Baseline (V x LCC) and event modes are
  explicit in every response; mixing them raises an error.

  **Methodological deviation to defend:** top-level composition is the plain
  geometric mean, NOT INFORM's [1,10] rescale. Tested on the real event, the
  rescale ranked Lislique (never shaken, H&E=0) second and put 40 districts in
  red versus 6. The rescaled score is still published as
  `inform_rescaled_score`; no ranking reads it.

  **Known limits:** a percentile-floor zero means "ranked best of 262", not "no
  risk" (Antiguo Cuscatlan LCC=0 so PRIO=0 in any event); ShakeMap contours
  understate peak MMI by up to 0.5; earthquake only (flood/GDACS is a declared
  gap); never casualty counts.
- [x] **C5** Frontend community triage view. **Commits `e875280`, `a2b238c`.**
  104 tests pass. No district choropleth: the API exposes no district geometry
  or centroid, so districts are a ranked list plus class filters. Not yet
  looked at in a browser.
- [x] **C6** Exports (commits `a30b26c`, `22b749a`; `write-excel-file` in a
  lazy 71 KB chunk, PDF via print stylesheet). Excel (district ranking + Sphere needs), PDF report and a
  printable map of priority districts. Client-side, no server round trip.

- [ ] **C7** End-to-end Playwright suite, run once the UI polish lands. Real
  browser against the running stack (`just up2`). Cover: district list and
  detail, baseline/event mode, export dialog (xlsx/csv download, print views),
  current-view print for an in-coverage zone (Sonsonate) and an
  outside-coverage zone (Escuintla, Guatemala), print section toggles and
  presets, a full export run for the Acajutla zone (key `acajutla`, Sonsonate,
  in census coverage: current-view map PDF with sections, xlsx and csv, each
  file opened and checked for zone title, mode, timestamp, limits line and
  BCR/ONEC attribution, no suppressed values, null never exported as 0;
  artifacts kept for human review), keyboard-only navigation, axe accessibility scan, and visual
  screenshots at 1920px and 390px in both themes. Also assert no tile request
  hits a key-gated provider (the CARTO incident).

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

Phase A visual work complete (A1-A3). Phase B ingestion complete (B1-B3).

| Commit | Task | Verified |
|---|---|---|
| `6dc3957` | checkpoint of pre-existing work on `main` | — |
| `1316693` | **A1** design token system | build + 34 tests |
| `8a9f2dc` | **A3** map treatment | vue-tsc, 34 tests, build |
| `2f0b08b` | **A2** shell density | vue-tsc, 34 tests, build, spot check |
| `26a82c3` | dead colour literals removed | 34 tests, vue-tsc |
| `9c0d037` | **basemap fix** — CARTO now needs a key | 34 tests, live tiles |
| `51e62e7` | **B1-B3** census ingestion | 142 tests, real 570 MB ingest |
| `69d1337` | **B5** suppression policy in `app/core` | 207 tests |
| `1c1c46b` | **B4** place-census attachment + exposure | 207 tests, alembic check, backfill |
| `cc4190a` | **B6** census justfile recipes | `just census-download --dry-run` |
| `b1aa8c5` | **C1** completion record | — |
| _this_ | **C2** LCC dimension (geodesic, declared gaps) | 385 tests, alembic check, real ingest, ranking |

### What the exposure estimates actually look like

At the declared 500 m default radius, over 1,425 attached places: minimum 52,
median 4,694, maximum 8,809, 504 distinct values, and 548 places whose buffer
spans more than one DEGURBA unit. 56 places are outside census coverage and
hold a **null** estimate, never a zero.

The median sits far above the national mean density (5,922,921 people over
~21,000 km² is 282/km², so an average 500 m buffer would hold ~222 people)
because OSM places — schools, hospitals, pharmacies — are overwhelmingly inside
dense DEGURBA classes. That is a selection effect of where places are, not an
inflated estimator.

**Consequence of the uniform-density assumption, worth stating plainly:** when a
buffer falls entirely inside one DEGURBA unit, the estimate is
`density × buffer area` and is therefore *spatially flat within that unit*. The
twelve highest estimates are all 8,809 because they share unit 060108
"Ciudades": 134,596 people over 11.923 km² is 11,288/km², and a 500 m buffer of
0.785 km² predicts 8,866. The estimate discriminates between dense and sparse
units, not between locations inside one unit. Buffers that cross a unit boundary
do vary by location.

### Vulnerable-rate denominator decision

All three rates (65+, under 5, disability) share one denominator: the district's
published total resident population (`topic='poblacion'`), which reconciles
exactly to 5,922,921. Two findings forced this:

- 88 `edad_sexo` district cells are withheld under D.L. 904, so the age-band sum
  (5,922,778) is 143 people short of the population total. Numerator and
  denominator are deliberately *not* both drawn from the bands; the age rates
  are instead marginally conservative by 0.0024%.
- The census publishes its own `share` beside the disability count, but against
  an unstated denominator worth about 96% of resident population (district
  010101: 4,127 / 0.03381 implies 122,061 against 127,301 residents). Using it
  would overstate by ~4%, so it is not used as the multiplier.

### Incident: the CARTO basemap failure

A3 shipped CARTO Dark Matter / Positron as the default basemaps. CARTO now
requires an API key and **answers HTTP 200 with a ~2 KB "API KEY REQUIRED"
placeholder tile** instead of failing. No status-code check, no test and no
build step could detect it — the map rendered placeholder text across every
tile and only a human looking at the screen caught it.

Replaced with Esri World Light/Dark Gray Canvas, which need no key and pair
each Base layer with its Reference overlay. Esri serves `{z}/{y}/{x}`,
inverting y and x relative to OSM and CARTO.

**Lesson worth keeping: a tile provider that degrades with HTTP 200 is
invisible to automated verification. Visual surfaces need a human check.**

## Next step

Phase B is complete (B1–B6). The backend now serves a real exposed-population
estimate per place.

**The frontend has not been updated and still shows `0 pers.`** The dispatch
queue reads `estimated_vulnerable_count`, which is the institution-entered
field and is deliberately unchanged. The census estimate arrives in two new
additive fields on `PlaceRead` — `census_unit_id` and `population_exposure` —
plus the new `GET /places/{id}/population-exposure` endpoint.
`backend/openapi.json` is regenerated, so `pnpm --dir frontend run
generate:api` (or `just codegen`) will pick them up. Wiring the queue column to
`population_exposure.estimated_exposed_population` is a frontend task.

Then **C1-C4** for the PRIO-SV index itself. A4 is in progress on this branch.

## Open decisions

- **Chain strategy undecided.** Forecast across phases A-E far exceeds the
  ~400 authored-line delivery budget. Before the branch grows further, choose
  `stacked-to-main` or `feature-branch-chain`.
- **`frontend-gis/`** — a second Vue 3 + Leaflet workspace exists, committed in
  `6dc3957` but unexplained. Confirm whether it is the intended target of the
  visual work or an abandoned experiment, before investing further in
  `frontend/`.

## UI/UX evidence (fetched 2026-10-17)

Design rules for the console derive from these. Items not listed as verified
must not be cited publicly.

- **RustGIS** (local, `crates/ui-egui/src`): zero explanatory paragraphs by
  default (help lives in tooltips, `ribbon.rs`); one left pane, right pane
  closed until requested, at most one right pane (`lib.rs:363-372`,
  `panes.rs:34`); no legend on the map, legend behind a per-layer chevron
  (`panes.rs:800-808`); one-line empty states with at most two actions
  (`panes.rs:349-381`); collapsible ribbon, command search as escape hatch.
- **Verified citations:** Endsley 1995, DOI 10.1518/001872095779049543
  ("direct presentation of higher level SA needs"); Shneiderman 1996,
  DOI 10.1109/VL.1996.545307; Hick 1952, DOI 10.1080/17470215208416600;
  Hyman 1953, DOI 10.1037/h0056940; Cowan 2001, DOI 10.1017/S0140525X01003922
  (about 4 chunks); NN/g progressive disclosure (Nielsen 2006) and data tables
  (Laubheimer 2022); WCAG 2.2 SC 1.3.1, 1.4.1, 1.4.3, 1.4.10, 1.4.11, 2.4.11,
  2.5.8; Sendelbach & Funk 2013, DOI 10.1097/NCI.0b013e3182a903f9;
  ISO 22324 (2015, replaced by 2022): red = act now, yellow = prepare,
  green = safe, grey = no information available.
- **Do not cite as stated:** "grey background, colour only for abnormal" is
  ASM Consortium / Hollifield practice, not ISA-101 text. Choice overload is
  conditional (Scheibehenne et al. 2010, DOI 10.1086/651235, mean effect near
  zero).
- **Export pattern** (Felt, Power BI, Metabase, ArcGIS Experience Builder
  compact mode): an export entry point on the element itself; a small option
  set (format, filtered/all, formatted/raw); advanced options folded at most
  one level deep.
- **List-map linkage** (ArcGIS Dashboards actions): list selection pans/flashes
  the map; map extent can filter the list. Blocked here until the API exposes
  district geometry.
