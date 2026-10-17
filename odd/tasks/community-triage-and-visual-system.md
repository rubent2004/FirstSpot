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

Unit of analysis: **district (ADM3, ~262-266 units)**, aggregatable to
municipality for command view.

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

Census 2024 (ONEC/BCR): population 6,029,976; 2,270,170 dwellings;
1,841,206 occupied; 1,920,668 households.

**Raw downloads live in `data/census/raw/` (~570 MB) and are gitignored.**
They must be regenerable by a documented script.

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

- [ ] **A1** Rebuild `frontend/src/style.css` token system: neutral narrow-band
  surfaces, brand/operational accent split, full geometry and typography scale.
  Keep existing token names (`--eoc-bg-canvas`, etc.) so no component breaks.
  *Route: inline (1 file, fully specified).*
- [ ] **A2** Apply density overrides to Element Plus and the app shell
  (header 34px, status bar 26px, table header 24px, panel ranges).
  *Route: delegated writer (multi-file).*
- [ ] **A3** Map treatment: Positron/Dark Matter basemaps, translucent floating
  controls at 75–92% alpha with 1px strong border, restyled Leaflet controls,
  legends and popups. *Route: delegated writer.*

### Phase B — Census ingestion

- [ ] **B1** Document and script the raw download so `data/census/raw/` is
  regenerable. *Blocked on: census agent inventory report.*
- [ ] **B2** Alembic migration: `districts` (geometry from CNR SIRGAS),
  `census_indicators`, `population_grid`. Join key audited against HDX COD-AB —
  census 2024 uses 44 municipalities / 262 districts after the 2023 reform while
  COD-AB reports 266. **Audit non-matching codes before demonstrating anything.**
- [ ] **B3** Ingestion module with idempotent loaders and row-count assertions.

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

Nothing implemented yet. Research phase complete for legal, visual and
methodological framing; census inventory pending.

## Next step

A1 — rebuild the token system.
