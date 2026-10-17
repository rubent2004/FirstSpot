"""Phase C3/C4 tests: the Hazard & Exposure dimension and the composed PRIO-SV index.

This module guards four failure modes that C1 and C2 did not have.

**A normalisation that moves a district's score for someone else's reason.** V and
LCC are percentile ranks over a closed set of 262 districts, which is defensible
because the unit set never changes. H&E is **per event**, so a percentile rank
there would let a district appear to improve because a different district got
worse -- two events would be incomparable and a time series would be fiction. H&E
is therefore the one dimension normalised on **fixed declared bounds**, and the
tests pin that adding, removing or re-scoring other districts leaves a district's
intensity and exposure untouched.

**A composition that discards the hazard it exists to respect.** INFORM 2017
Equation 1 is a plain multiplicative geometric mean: a zero in any dimension
zeroes the risk, so a district with no shaking is not prioritised for being poor.
The non-annihilating ``inform_geometric_mean`` rescale -- correct *inside* a
dimension -- destroys that property at the top level, and the evidence is
measured rather than theoretical: see
:data:`~app.modules.prioritization.domain.prio.RESCALED_COMPOSITION_EXCLUSION`.
The tests pin the strict composition and pin the rescaled value as an audit
figure that no ranking reads.

**Two modes that look identical in a payload.** Baseline (V x LCC, no event) and
Event (H&E x V x LCC) answer different questions and must never be confused by a
caller. The tests require the mode, the dimension list and the event identity on
every response, and refuse a baseline index that carries a hazard score or an
event index that does not.

**A number that implies a casualty count.** PAGER is probabilistic and publishes
about 30 minutes after an event, when the extent of shaking is still uncertain.
Nothing here may report deaths, victims or casualties: only *estimated exposed
population*, and the PAGER alert level with its published range, stamped with the
ShakeMap grid time because ShakeMap is revised. The tests assert on the wording.

Network-dependent code runs against the recorded fixtures in
``tests/fixtures/usgs``, captured from the real USGS endpoints. A live call
belongs in a verification run, not in this suite.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import app
from app.modules.hazards.domain.shakemap import (
    CASUALTY_REPORTING_PROHIBITION,
    EXPOSURE_MMI_THRESHOLD,
    MMI_CONTOUR_CONTENT_KEY,
    MMI_GRID_CONTENT_KEY,
    MMI_SCALE_CEILING,
    MMI_SCALE_FLOOR,
    PAGER_ALERT_BANDS,
    SHAKEMAP_REVISION_WARNING,
    ShakeMapError,
    mmi_contour_url,
    pager_alert_band,
    parse_event_summaries,
    parse_mmi_bands,
    parse_shakemap_release,
)
from app.modules.prioritization.domain.hazard import (
    EXPOSURE_THEME,
    HAZARD_DECLARED_GAPS,
    HAZARD_DIMENSION_KEY,
    HAZARD_SCORE_INTERPRETATION,
    HAZARD_VARIABLES,
    INTENSITY_THEME,
    DistrictHazardInput,
    HazardInputError,
    HazardVariableInput,
    hazard_index_variables_for_theme,
    hazard_variables_for_theme,
    rescale_fixed,
    score_hazard,
)
from app.modules.prioritization.domain.prio import (
    BASELINE_DIMENSION_KEYS,
    DGPC_CLASS_BREAKS,
    DGPC_CLASS_SOURCE,
    ECOLOGICAL_FALLACY_WARNING,
    EVENT_DIMENSION_KEYS,
    MAUP_WARNING,
    PRIO_COMPOSITION_RULE,
    RESCALED_COMPOSITION_EXCLUSION,
    TRIAGE_COLOUR_ANALOGY_NOTE,
    DgpcAlertClass,
    DimensionScore,
    PrioCompositionError,
    PrioEvent,
    PrioMode,
    build_prio_index,
    classify_dgpc,
    compose_prio,
    compose_prio_rescaled,
)
from app.modules.prioritization.domain.sphere import (
    FOOD_KCAL_PER_PERSON_PER_DAY,
    PEOPLE_PER_WATER_TAP,
    SHELTER_M2_PER_PERSON,
    SHELTER_M2_PER_PERSON_URBAN_WITH_INTERNAL_SERVICES,
    SPHERE_NOT_A_DELIVERY_TARGET,
    SPHERE_REQUIREMENT_LABEL,
    WATER_LITRES_PER_PERSON_PER_DAY,
    WATER_LITRES_PER_PERSON_PER_DAY_EXTREME_HEAT,
    WATER_POINT_MAXIMUM_DISTANCE_METRES,
    sphere_minimum_requirements,
)
from app.modules.prioritization.infrastructure.hazard_repository import (
    EXPECTED_DISTRICT_COUNT,
    HazardCorpusError,
    HazardRepository,
)

# --------------------------------------------------------------------------- #
# Recorded USGS fixtures
# --------------------------------------------------------------------------- #

FIXTURES = Path(__file__).parent / "fixtures" / "usgs"

COJUTEPEQUE_EVENT_ID = "usp000a9jv"
"""The 13 February 2001 M6.6 earthquake, 5 km S of Cojutepeque.

Chosen as the worked example because it is **inland**: its MMI contours fall over
populated districts rather than over the Pacific, so the zonal statistics have
something to measure. It carries a ShakeMap and no PAGER -- PAGER did not exist
in 2001 -- which makes it the right fixture for the "absent PAGER is published as
absent" path.
"""

LA_LIBERTAD_2019_EVENT_ID = "us70003t2n"
"""The 30 May 2019 M6.6 offshore event, which carries a yellow PAGER alert."""


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def event_query() -> Any:
    return _fixture("event_query_sv.json")


@pytest.fixture(scope="module")
def cojutepeque_detail() -> Any:
    return _fixture(f"event_detail_{COJUTEPEQUE_EVENT_ID}.json")


@pytest.fixture(scope="module")
def cojutepeque_contours() -> Any:
    return _fixture(f"cont_mi_{COJUTEPEQUE_EVENT_ID}.json")


@pytest.fixture(scope="module")
def la_libertad_detail() -> Any:
    return _fixture(f"event_detail_{LA_LIBERTAD_2019_EVENT_ID}.json")


# --------------------------------------------------------------------------- #
# Synthetic districts whose arithmetic is hand-checkable
# --------------------------------------------------------------------------- #

MMI_MAX_KEY = "HE_MMIMAX"
MMI_MEAN_KEY = "HE_MMIMEAN"
EXPOSED_ABSOLUTE_KEY = "HE_EXPABS"
EXPOSED_RELATIVE_KEY = "HE_EXPREL"


def _hazard_district(
    code: str,
    name: str,
    population: int,
    max_mmi: Decimal | None,
    exposed: Decimal,
    *,
    mean_mmi: Decimal | None = None,
) -> DistrictHazardInput:
    """Build one district's H&E inputs directly in the published units.

    ``HE_MMIMAX`` has no universe -- a maximum is not a ratio -- so its numerator
    *is* its rate. ``HE_MMIMEAN`` is person-MMI over population, mirroring the
    person-metres convention LCC established. Both exposure variables share one
    numerator and differ only in the universe they are divided by, which is the
    whole point of computing the absolute and the relative form.
    """
    weighted = (
        None
        if (mean_mmi if mean_mmi is not None else max_mmi) is None
        else (mean_mmi if mean_mmi is not None else max_mmi) * Decimal(population)
    )
    return DistrictHazardInput(
        district_code=code,
        district_name=name,
        population=population,
        variables=(
            HazardVariableInput(
                variable=MMI_MAX_KEY, numerator=max_mmi, denominator=None
            ),
            HazardVariableInput(
                variable=MMI_MEAN_KEY,
                numerator=weighted,
                denominator=Decimal(population),
            ),
            HazardVariableInput(
                variable=EXPOSED_ABSOLUTE_KEY, numerator=exposed, denominator=None
            ),
            HazardVariableInput(
                variable=EXPOSED_RELATIVE_KEY,
                numerator=exposed,
                denominator=Decimal(population),
            ),
        ),
    )


def _three_districts() -> list[DistrictHazardInput]:
    """An unshaken district, a lightly shaken one and a severely shaken one."""
    return [
        _hazard_district("000001", "Unshaken", 10_000, None, Decimal(0)),
        _hazard_district("000002", "Light", 10_000, Decimal("5.0"), Decimal(0)),
        _hazard_district("000003", "Severe", 10_000, Decimal("9.0"), Decimal(10_000)),
    ]


# --------------------------------------------------------------------------- #
# The fixed bounds, which are the whole methodological point of this dimension
# --------------------------------------------------------------------------- #


class TestFixedBoundsAreFixed:
    """Normalising against an event's own range would destroy comparability."""

    def test_mmi_four_is_the_declared_floor_and_scores_zero(self) -> None:
        assert MMI_SCALE_FLOOR == Decimal(4)
        assert rescale_fixed(Decimal(4), MMI_SCALE_FLOOR, MMI_SCALE_CEILING) == 0

    def test_mmi_ten_is_the_declared_ceiling_and_scores_ten(self) -> None:
        assert MMI_SCALE_CEILING == Decimal(10)
        assert rescale_fixed(Decimal(10), MMI_SCALE_FLOOR, MMI_SCALE_CEILING) == 10

    def test_a_value_below_the_floor_clamps_to_zero_rather_than_going_negative(
        self,
    ) -> None:
        assert rescale_fixed(Decimal(2), MMI_SCALE_FLOOR, MMI_SCALE_CEILING) == 0

    def test_a_value_above_the_ceiling_clamps_to_ten(self) -> None:
        assert rescale_fixed(Decimal(12), MMI_SCALE_FLOOR, MMI_SCALE_CEILING) == 10

    def test_the_midpoint_of_the_declared_range_scores_five(self) -> None:
        assert rescale_fixed(Decimal(7), MMI_SCALE_FLOOR, MMI_SCALE_CEILING) == 5

    def test_the_exposure_threshold_is_mmi_six(self) -> None:
        assert EXPOSURE_MMI_THRESHOLD == Decimal(6)

    def test_every_index_variable_declares_both_of_its_fixed_bounds(self) -> None:
        for variable in HAZARD_VARIABLES:
            assert variable.fixed_floor is not None, variable.key
            assert variable.fixed_ceiling is not None, variable.key
            assert variable.fixed_ceiling > variable.fixed_floor, variable.key

    def test_a_district_score_is_unchanged_when_the_input_set_changes(self) -> None:
        """The property that disqualifies a percentile rank for this dimension.

        A percentile is relative to its unit set, so with CDC normalisation a
        district's H&E would move when an unrelated district was added, removed
        or re-shaken. Here it must not: the bounds are constants, so the only
        thing that can change a district's intensity is its own shaking.
        """
        severe = _hazard_district(
            "000003", "Severe", 10_000, Decimal("9.0"), Decimal(10_000)
        )
        alone = score_hazard([severe])
        with_others = score_hazard(_three_districts())
        extra = score_hazard(
            [
                *_three_districts(),
                _hazard_district(
                    "000004", "Worse", 500_000, Decimal("10.0"), Decimal(500_000)
                ),
            ]
        )

        def score_of(ranking: Any, code: str) -> Decimal | None:
            return next(
                d.score for d in ranking.districts if d.district_code == code
            )

        assert score_of(alone, "000003") == score_of(with_others, "000003")
        assert score_of(alone, "000003") == score_of(extra, "000003")

    def test_a_single_district_is_not_scored_at_the_median(self) -> None:
        """A percentile over one unit is 0.5 by definition; a fixed bound is not.

        This is the cheapest possible detector of a percentile rank sneaking back
        into this dimension.
        """
        ranking = score_hazard(
            [_hazard_district("000001", "Only", 1_000, Decimal(10), Decimal(1_000))]
        )
        # log10(1+1000)/log10(1+5.9M) is 4.4 on the fixed national ceiling, so
        # the score is not 10; it must be neither the median 5 nor rank-derived.
        assert ranking.districts[0].score > 9
        assert ranking.districts[0].score != 5

    def test_the_fixed_bounds_rationale_is_published_with_the_ranking(self) -> None:
        ranking = score_hazard(_three_districts())
        assert "comparab" in ranking.fixed_bounds_rationale.lower()
        assert ranking.uses_percentile_normalisation is False


class TestHazardVariableCatalogue:
    """Every input behind an H&E score is declared, exactly as in V and LCC."""

    def test_variable_keys_are_unique(self) -> None:
        keys = [variable.key for variable in HAZARD_VARIABLES]
        assert len(keys) == len(set(keys))

    def test_every_variable_belongs_to_one_of_the_two_sub_dimensions(self) -> None:
        for variable in HAZARD_VARIABLES:
            assert variable.theme in (INTENSITY_THEME, EXPOSURE_THEME), variable.key

    def test_the_intensity_sub_dimension_carries_the_maximum_mmi(self) -> None:
        keys = {v.key for v in hazard_index_variables_for_theme(INTENSITY_THEME)}
        assert keys == {MMI_MAX_KEY}

    def test_the_exposure_sub_dimension_carries_both_absolute_and_relative(
        self,
    ) -> None:
        keys = {v.key for v in hazard_index_variables_for_theme(EXPOSURE_THEME)}
        assert keys == {EXPOSED_ABSOLUTE_KEY, EXPOSED_RELATIVE_KEY}

    def test_the_mean_mmi_is_published_but_outside_the_index(self) -> None:
        mean = next(v for v in HAZARD_VARIABLES if v.key == MMI_MEAN_KEY)
        assert mean.in_index is False
        assert mean.exclusion_reason

    def test_every_context_variable_states_why_it_is_excluded(self) -> None:
        for variable in HAZARD_VARIABLES:
            if not variable.in_index:
                assert variable.exclusion_reason, variable.key

    def test_the_absolute_exposure_variable_declares_its_log_transform(self) -> None:
        absolute = next(
            v for v in HAZARD_VARIABLES if v.key == EXPOSED_ABSOLUTE_KEY
        )
        assert "log" in absolute.measure.lower()

    def test_the_relative_exposure_variable_is_not_log_transformed(self) -> None:
        relative = next(
            v for v in HAZARD_VARIABLES if v.key == EXPOSED_RELATIVE_KEY
        )
        assert "log" not in relative.measure.lower()
        assert "share" in relative.measure.lower()

    def test_the_contour_discretisation_is_a_declared_gap(self) -> None:
        subjects = " ".join(gap.subject for gap in HAZARD_DECLARED_GAPS).lower()
        assert "contour" in subjects

    def test_flood_is_a_declared_gap_rather_than_a_silent_absence(self) -> None:
        subjects = " ".join(gap.subject for gap in HAZARD_DECLARED_GAPS).lower()
        assert "flood" in subjects

    def test_every_declared_gap_states_its_consequence_for_the_score(self) -> None:
        for gap in HAZARD_DECLARED_GAPS:
            assert gap.reason and gap.consequence, gap.subject

    def test_the_score_is_declared_as_per_event_and_absolute(self) -> None:
        assert "event" in HAZARD_SCORE_INTERPRETATION.lower()
        assert HAZARD_DIMENSION_KEY == "hazard_and_exposure"


class TestHazardScoring:
    """The two sub-dimensions, and how a size-dominated exposure is avoided."""

    def test_an_unshaken_district_scores_exactly_zero(self) -> None:
        ranking = score_hazard(_three_districts())
        unshaken = next(
            d for d in ranking.districts if d.district_code == "000001"
        )
        assert unshaken.score == 0
        assert unshaken.shaken is False

    def test_a_shaken_district_with_nobody_above_mmi_six_still_scores(self) -> None:
        """Shaking at MMI V over 10,000 people is not "no hazard".

        Inside a dimension the INFORM rescale is correct: exposure 0 must not
        annihilate a real intensity. The annihilating zero belongs at the top
        level, where it means "nothing happened here".
        """
        ranking = score_hazard(_three_districts())
        light = next(d for d in ranking.districts if d.district_code == "000002")
        assert light.score > 0
        assert light.shaken is True

    def test_the_severely_shaken_district_outranks_the_lightly_shaken_one(
        self,
    ) -> None:
        ranking = score_hazard(_three_districts())
        ordered = [d.district_code for d in ranking.districts]
        assert ordered.index("000003") < ordered.index("000002")
        assert ordered.index("000002") < ordered.index("000001")

    def test_the_exposure_theme_is_the_arithmetic_mean_of_its_two_variables(
        self,
    ) -> None:
        ranking = score_hazard(_three_districts())
        severe = next(d for d in ranking.districts if d.district_code == "000003")
        theme = next(t for t in severe.themes if t.theme == EXPOSURE_THEME)
        parts = [
            v.score
            for v in severe.variables
            if v.in_index and v.variable.startswith("HE_EXP")
        ]
        assert len(parts) == 2
        assert theme.score == sum(parts) / len(parts)

    def test_a_large_district_does_not_win_on_size_alone(self) -> None:
        """The reason both exposure forms exist and are averaged.

        A metropolis with a tenth of its people above MMI VI must not outrank a
        village with all of them above it on the absolute count alone. The
        relative form is what prevents San Salvador winning by being large.
        """
        metropolis = _hazard_district(
            "000010", "Metropolis", 300_000, Decimal("6.5"), Decimal(30_000)
        )
        village = _hazard_district(
            "000011", "Village", 3_000, Decimal("6.5"), Decimal(3_000)
        )
        ranking = score_hazard([metropolis, village])
        scores = {d.district_code: d.score for d in ranking.districts}

        absolute = {
            d.district_code: next(
                v.score for v in d.variables if v.variable == EXPOSED_ABSOLUTE_KEY
            )
            for d in ranking.districts
        }
        assert absolute["000010"] > absolute["000011"]
        assert scores["000011"] > scores["000010"]

    def test_the_intensity_score_of_mmi_seven_is_five(self) -> None:
        ranking = score_hazard(
            [_hazard_district("000001", "Seven", 1_000, Decimal(7), Decimal(0))]
        )
        theme = next(
            t for t in ranking.districts[0].themes if t.theme == INTENSITY_THEME
        )
        assert theme.score == 5

    def test_a_fully_exposed_district_scores_ten_on_the_relative_variable(
        self,
    ) -> None:
        ranking = score_hazard(
            [_hazard_district("000001", "All", 5_000, Decimal(8), Decimal(5_000))]
        )
        relative = next(
            v
            for v in ranking.districts[0].variables
            if v.variable == EXPOSED_RELATIVE_KEY
        )
        assert relative.score == 10

    def test_more_exposed_people_never_lowers_the_score(self) -> None:
        def score(exposed: int) -> Decimal:
            ranking = score_hazard(
                [
                    _hazard_district(
                        "000001", "D", 10_000, Decimal(8), Decimal(exposed)
                    )
                ]
            )
            return ranking.districts[0].score

        assert score(0) < score(1_000) < score(5_000) < score(10_000)

    def test_the_ranking_counts_its_shaken_and_exposed_districts(self) -> None:
        ranking = score_hazard(_three_districts())
        assert ranking.scored_unit_count == 3
        assert ranking.shaken_unit_count == 2
        assert ranking.exposed_unit_count == 1

    def test_tied_districts_share_one_score_and_one_rank(self) -> None:
        ranking = score_hazard(
            [
                _hazard_district("000001", "A", 5_000, Decimal(7), Decimal(5_000)),
                _hazard_district("000002", "B", 5_000, Decimal(7), Decimal(5_000)),
            ]
        )
        assert {d.rank for d in ranking.districts} == {1}

    def test_a_duplicate_district_code_is_refused(self) -> None:
        with pytest.raises(HazardInputError, match="duplicate"):
            score_hazard(
                [
                    _hazard_district("000001", "A", 10, Decimal(7), Decimal(0)),
                    _hazard_district("000001", "A again", 10, Decimal(7), Decimal(0)),
                ]
            )

    def test_a_variable_missing_from_a_district_is_refused(self) -> None:
        broken = DistrictHazardInput(
            district_code="000001",
            district_name="Broken",
            population=100,
            variables=(
                HazardVariableInput(
                    variable=MMI_MAX_KEY, numerator=Decimal(7), denominator=None
                ),
            ),
        )
        with pytest.raises(HazardInputError, match="missing declared variable"):
            score_hazard([broken])

    def test_an_empty_district_set_produces_an_empty_ranking(self) -> None:
        ranking = score_hazard([])
        assert ranking.districts == ()
        assert ranking.scored_unit_count == 0

    def test_exposure_above_the_district_population_is_refused(self) -> None:
        """More people exposed than live there is an upstream defect, not a 110%."""
        with pytest.raises(HazardInputError, match="exceeds"):
            score_hazard(
                [
                    _hazard_district(
                        "000001", "D", 1_000, Decimal(8), Decimal(1_500)
                    )
                ]
            )


# --------------------------------------------------------------------------- #
# The composed index
# --------------------------------------------------------------------------- #


class TestPrioComposition:
    """INFORM 2017 Equation 1, taken literally, including its annihilating zero."""

    def test_equal_dimension_scores_compose_to_that_score(self) -> None:
        assert compose_prio([Decimal(6), Decimal(6), Decimal(6)]) == 6

    def test_a_zero_dimension_zeroes_the_product(self) -> None:
        assert compose_prio([Decimal(0), Decimal(10), Decimal(10)]) == 0
        assert compose_prio([Decimal(10), Decimal(0), Decimal(10)]) == 0
        assert compose_prio([Decimal(10), Decimal(10), Decimal(0)]) == 0

    def test_the_composition_is_the_cube_root_of_the_product(self) -> None:
        composed = compose_prio([Decimal(1), Decimal(2), Decimal(4)])
        assert abs(composed - Decimal(2)) < Decimal("1e-20")

    def test_the_two_dimension_baseline_is_the_square_root_of_the_product(
        self,
    ) -> None:
        assert compose_prio([Decimal(4), Decimal(9)]) == 6

    def test_the_rescaled_composition_does_not_zero_on_a_zero(self) -> None:
        """Published for audit, and never read by a ranking. See the exclusion."""
        rescaled = compose_prio_rescaled([Decimal(0), Decimal(10), Decimal(10)])
        assert rescaled > 8

    def test_the_rescaled_composition_is_excluded_with_measured_evidence(
        self,
    ) -> None:
        exclusion = RESCALED_COMPOSITION_EXCLUSION.lower()
        assert "victoria" in exclusion
        assert "lislique" in exclusion

    def test_the_composition_rule_cites_inform_equation_one(self) -> None:
        assert "equation 1" in PRIO_COMPOSITION_RULE.lower()

    def test_a_score_outside_the_range_is_refused(self) -> None:
        with pytest.raises(PrioCompositionError):
            compose_prio([Decimal(11), Decimal(5)])
        with pytest.raises(PrioCompositionError):
            compose_prio([Decimal(-1), Decimal(5)])

    def test_an_empty_dimension_set_is_refused(self) -> None:
        with pytest.raises(PrioCompositionError):
            compose_prio([])


def _event() -> PrioEvent:
    return PrioEvent(
        event_id="test", magnitude=None, place="fixture", latitude=Decimal(13),
        longitude=Decimal(-89), depth_km=None,
        occurred_at_iso="2001-02-13T14:22:05+00:00", grid_processed_at_iso=None,
        shakemap_version=None, shakemap_declared_max_mmi=None,
        contour_max_mmi=None, contour_interval=None, pager_level=None,
        pager_band_label=None, pager_response_implication=None,
    )


class TestBaselineAndEventModesAreNeverInterchangeable:
    """A caller must always be able to tell which index it received."""

    def _dimension(self, key: str, score: Decimal | None) -> DimensionScore:
        return DimensionScore(dimension=key, score=score, rank=None)

    def test_baseline_declares_two_dimensions_and_names_them(self) -> None:
        assert BASELINE_DIMENSION_KEYS == ("vulnerability", "lack_of_coping_capacity")

    def test_event_declares_three_dimensions_with_hazard_first(self) -> None:
        assert EVENT_DIMENSION_KEYS == (
            HAZARD_DIMENSION_KEY,
            "vulnerability",
            "lack_of_coping_capacity",
        )

    def test_a_baseline_index_carries_no_hazard_dimension(self) -> None:
        index = build_prio_index(
            mode=PrioMode.BASELINE,
            districts=[
                (
                    "000001",
                    "D",
                    1_000,
                    (
                        self._dimension("vulnerability", Decimal(4)),
                        self._dimension("lack_of_coping_capacity", Decimal(9)),
                    ),
                )
            ],
        )
        assert index.mode is PrioMode.BASELINE
        assert index.dimension_keys == BASELINE_DIMENSION_KEYS
        assert index.event is None
        assert index.districts[0].score == 6

    def test_a_baseline_index_refuses_a_hazard_score(self) -> None:
        with pytest.raises(PrioCompositionError, match="baseline"):
            build_prio_index(
                mode=PrioMode.BASELINE,
                districts=[
                    (
                        "000001",
                        "D",
                        1_000,
                        (
                            self._dimension(HAZARD_DIMENSION_KEY, Decimal(5)),
                            self._dimension("vulnerability", Decimal(4)),
                            self._dimension("lack_of_coping_capacity", Decimal(9)),
                        ),
                    )
                ],
            )

    def test_an_event_index_refuses_a_missing_hazard_dimension(self) -> None:
        with pytest.raises(PrioCompositionError, match="event"):
            build_prio_index(
                mode=PrioMode.EVENT,
                districts=[
                    (
                        "000001",
                        "D",
                        1_000,
                        (
                            self._dimension("vulnerability", Decimal(4)),
                            self._dimension("lack_of_coping_capacity", Decimal(9)),
                        ),
                    )
                ],
            )

    def test_the_baseline_mode_states_what_question_it_answers(self) -> None:
        index = build_prio_index(
            mode=PrioMode.BASELINE,
            districts=[
                (
                    "000001",
                    "D",
                    1_000,
                    (
                        self._dimension("vulnerability", Decimal(4)),
                        self._dimension("lack_of_coping_capacity", Decimal(9)),
                    ),
                )
            ],
        )
        assert "structural" in index.mode_meaning.lower()
        assert "no active" in index.mode_meaning.lower()

    def test_a_district_zeroed_by_hazard_says_so(self) -> None:
        index = build_prio_index(
            mode=PrioMode.EVENT,
            event=_event(),
            districts=[
                (
                    "000001",
                    "D",
                    1_000,
                    (
                        self._dimension(HAZARD_DIMENSION_KEY, Decimal(0)),
                        self._dimension("vulnerability", Decimal(9)),
                        self._dimension("lack_of_coping_capacity", Decimal(9)),
                    ),
                )
            ],
        )
        district = index.districts[0]
        assert district.score == 0
        assert district.zeroed_by == (HAZARD_DIMENSION_KEY,)
        assert "shak" in (district.zero_reason or "").lower()

    def test_a_district_zeroed_by_a_percentile_floor_says_which_dimension(
        self,
    ) -> None:
        """Zero from a percentile floor means "ranked best of 262", never "none".

        Antiguo Cuscatlán's LCC is exactly 0 because it ranks 262nd of 262 on
        coping capacity, so INFORM's annihilating zero takes its composed score
        to 0 in every event. The number is defensible -- it is last in a relative
        ranking -- but it must not be confused with "this district was not
        shaken", so the reason names the dimension responsible.
        """
        index = build_prio_index(
            mode=PrioMode.EVENT,
            event=_event(),
            districts=[
                (
                    "050301",
                    "Antiguo Cuscatlán",
                    135_000,
                    (
                        self._dimension(HAZARD_DIMENSION_KEY, Decimal("1.33")),
                        self._dimension("vulnerability", Decimal("0.34")),
                        self._dimension("lack_of_coping_capacity", Decimal(0)),
                    ),
                )
            ],
        )
        district = index.districts[0]
        assert district.score == 0
        assert district.zeroed_by == ("lack_of_coping_capacity",)
        assert "percentile" in (district.zero_reason or "").lower()

    def test_a_withheld_dimension_withholds_the_composed_score(self) -> None:
        index = build_prio_index(
            mode=PrioMode.BASELINE,
            districts=[
                (
                    "000001",
                    "D",
                    1_000,
                    (
                        self._dimension("vulnerability", None),
                        self._dimension("lack_of_coping_capacity", Decimal(9)),
                    ),
                )
            ],
        )
        district = index.districts[0]
        assert district.score is None
        assert district.withheld is True
        assert district.alert_class is None
        assert district.rank is None

    def test_the_class_distribution_is_published_with_the_index(self) -> None:
        index = build_prio_index(
            mode=PrioMode.BASELINE,
            districts=[
                (
                    "000001",
                    "Red",
                    1_000,
                    (
                        self._dimension("vulnerability", Decimal(9)),
                        self._dimension("lack_of_coping_capacity", Decimal(9)),
                    ),
                ),
                (
                    "000002",
                    "Green",
                    1_000,
                    (
                        self._dimension("vulnerability", Decimal(1)),
                        self._dimension("lack_of_coping_capacity", Decimal(1)),
                    ),
                ),
            ],
        )
        assert index.class_distribution[DgpcAlertClass.ROJA] == 1
        assert index.class_distribution[DgpcAlertClass.VERDE] == 1


class TestDgpcAlertClasses:
    """Four colours, because El Salvador's national standard publishes four."""

    def test_there_are_exactly_four_classes(self) -> None:
        assert len(DGPC_CLASS_BREAKS) == 4
        assert {b.alert_class for b in DGPC_CLASS_BREAKS} == set(DgpcAlertClass)

    def test_the_class_names_are_the_dgpc_spanish_alert_levels(self) -> None:
        assert [b.alert_class.value for b in DGPC_CLASS_BREAKS] == [
            "verde",
            "amarilla",
            "naranja",
            "roja",
        ]

    def test_the_breaks_cover_zero_to_ten_without_a_gap_or_an_overlap(self) -> None:
        ordered = sorted(DGPC_CLASS_BREAKS, key=lambda b: b.floor)
        assert ordered[0].floor == 0
        assert ordered[-1].ceiling == 10
        for lower, upper in zip(ordered, ordered[1:]):
            assert lower.ceiling == upper.floor, (lower, upper)

    def test_the_cut_points_are_informs_own_published_class_breaks(self) -> None:
        assert "inform" in DGPC_CLASS_SOURCE.lower()
        assert "dgpc" in DGPC_CLASS_SOURCE.lower()

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (Decimal(0), DgpcAlertClass.VERDE),
            (Decimal("3.4"), DgpcAlertClass.VERDE),
            (Decimal("3.5"), DgpcAlertClass.AMARILLA),
            (Decimal("4.9"), DgpcAlertClass.AMARILLA),
            (Decimal("5.0"), DgpcAlertClass.NARANJA),
            (Decimal("6.4"), DgpcAlertClass.NARANJA),
            (Decimal("6.5"), DgpcAlertClass.ROJA),
            (Decimal(10), DgpcAlertClass.ROJA),
        ],
    )
    def test_a_score_lands_in_its_declared_class(
        self, score: Decimal, expected: DgpcAlertClass
    ) -> None:
        assert classify_dgpc(score) is expected

    def test_the_medical_triage_analogy_is_labelled_as_an_analogy(self) -> None:
        note = TRIAGE_COLOUR_ANALOGY_NOTE.lower()
        assert "analogy" in note
        assert "inform" in note
        assert "start" in note or "salt" in note


class TestTheWarningsThatTravelWithEveryScore:
    """A number read without these is read wrongly."""

    def test_the_ecological_fallacy_is_stated(self) -> None:
        warning = ECOLOGICAL_FALLACY_WARNING.lower()
        assert "territor" in warning
        assert "not people" in warning or "not individual" in warning

    def test_the_ecological_fallacy_warns_about_the_green_district(self) -> None:
        assert "green" in ECOLOGICAL_FALLACY_WARNING.lower()

    def test_the_modifiable_areal_unit_problem_is_stated(self) -> None:
        warning = MAUP_WARNING.lower()
        assert "unit" in warning
        assert "scale" in warning


# --------------------------------------------------------------------------- #
# Sphere minimum requirements
# --------------------------------------------------------------------------- #


class TestSphereArithmeticIsExact:
    """These numbers get read off a screen under time pressure."""

    def test_the_published_constants_are_the_sphere_2018_figures(self) -> None:
        assert WATER_LITRES_PER_PERSON_PER_DAY == 15
        assert WATER_LITRES_PER_PERSON_PER_DAY_EXTREME_HEAT == 20
        assert PEOPLE_PER_WATER_TAP == 250
        assert WATER_POINT_MAXIMUM_DISTANCE_METRES == 500
        assert FOOD_KCAL_PER_PERSON_PER_DAY == 2100
        assert SHELTER_M2_PER_PERSON == Decimal("3.5")
        assert SHELTER_M2_PER_PERSON_URBAN_WITH_INTERNAL_SERVICES == Decimal("4.5")

    def test_water_is_fifteen_litres_per_person_per_day(self) -> None:
        requirement = sphere_minimum_requirements(10_000)
        assert requirement.water_litres_per_day == 150_000

    def test_extreme_heat_water_is_twenty_litres_per_person_per_day(self) -> None:
        requirement = sphere_minimum_requirements(10_000)
        assert requirement.water_litres_per_day_extreme_heat == 200_000

    def test_food_is_twenty_one_hundred_kcal_per_person_per_day(self) -> None:
        requirement = sphere_minimum_requirements(10_000)
        assert requirement.food_kcal_per_day == 21_000_000

    def test_shelter_is_three_and_a_half_square_metres_per_person(self) -> None:
        requirement = sphere_minimum_requirements(10_000)
        assert requirement.shelter_area_m2 == Decimal(35_000)

    def test_urban_shelter_with_internal_services_is_four_and_a_half(self) -> None:
        requirement = sphere_minimum_requirements(
            10_000, urban_with_internal_services=True
        )
        assert requirement.shelter_area_m2 == Decimal(45_000)
        assert "4.5" in requirement.shelter_basis

    def test_taps_round_up_because_the_standard_is_a_maximum_per_tap(self) -> None:
        """One tap per 250 people means 251 people need two taps, not 1.004."""
        assert sphere_minimum_requirements(250).water_taps_minimum == 1
        assert sphere_minimum_requirements(251).water_taps_minimum == 2
        assert sphere_minimum_requirements(500).water_taps_minimum == 2
        assert sphere_minimum_requirements(9_443).water_taps_minimum == 38

    def test_a_single_person_still_needs_one_tap(self) -> None:
        assert sphere_minimum_requirements(1).water_taps_minimum == 1

    def test_nobody_exposed_requires_nothing(self) -> None:
        requirement = sphere_minimum_requirements(0)
        assert requirement.water_litres_per_day == 0
        assert requirement.food_kcal_per_day == 0
        assert requirement.shelter_area_m2 == 0
        assert requirement.water_taps_minimum == 0

    def test_a_negative_exposed_population_is_refused(self) -> None:
        with pytest.raises(ValueError):
            sphere_minimum_requirements(-1)

    def test_the_figures_are_labelled_a_minimum_requirement(self) -> None:
        assert SPHERE_REQUIREMENT_LABEL == "Sphere minimum requirement"
        requirement = sphere_minimum_requirements(100)
        assert requirement.label == SPHERE_REQUIREMENT_LABEL

    def test_the_figures_are_never_labelled_resources_to_deliver(self) -> None:
        requirement = sphere_minimum_requirements(100)
        rendered = " ".join(
            [requirement.label, requirement.caveat, requirement.source]
        ).lower()
        assert "to deliver" not in rendered
        assert "resources to deliver" not in rendered

    def test_the_published_criticism_of_sphere_as_a_target_is_carried(self) -> None:
        caveat = SPHERE_NOT_A_DELIVERY_TARGET.lower()
        assert "planning target" in caveat
        assert "capacity" in caveat

    def test_the_requirement_never_compares_itself_to_available_capacity(
        self,
    ) -> None:
        """C2 declared shelter capacity unmeasured, so no comparison is possible."""
        requirement = sphere_minimum_requirements(100)
        assert "capacity" in requirement.caveat.lower()


# --------------------------------------------------------------------------- #
# USGS ShakeMap and PAGER, against recorded fixtures
# --------------------------------------------------------------------------- #


class TestShakeMapParsing:
    """Recorded USGS payloads, so the suite never depends on the network."""

    def test_the_event_query_yields_the_recorded_salvadoran_events(
        self, event_query: Any
    ) -> None:
        summaries = parse_event_summaries(event_query)
        by_id = {summary.event_id: summary for summary in summaries}
        assert COJUTEPEQUE_EVENT_ID in by_id
        cojutepeque = by_id[COJUTEPEQUE_EVENT_ID]
        assert cojutepeque.magnitude == Decimal("6.6")
        assert "Cojutepeque" in cojutepeque.place
        assert cojutepeque.has_shakemap is True

    def test_an_event_summary_carries_its_epicentre_and_depth(
        self, event_query: Any
    ) -> None:
        cojutepeque = next(
            s
            for s in parse_event_summaries(event_query)
            if s.event_id == COJUTEPEQUE_EVENT_ID
        )
        assert Decimal("13") < cojutepeque.latitude < Decimal("14")
        assert Decimal("-90") < cojutepeque.longitude < Decimal("-88")
        assert cojutepeque.depth_km is not None

    def test_an_event_summary_carries_a_timezone_aware_origin_time(
        self, event_query: Any
    ) -> None:
        for summary in parse_event_summaries(event_query):
            assert summary.occurred_at.tzinfo is not None

    def test_the_contour_product_url_is_the_declared_content_key(
        self, cojutepeque_detail: Any
    ) -> None:
        url = mmi_contour_url(cojutepeque_detail)
        assert url.endswith("cont_mi.json")
        assert MMI_CONTOUR_CONTENT_KEY == "download/cont_mi.json"
        assert MMI_GRID_CONTENT_KEY == "download/grid.xml"

    def test_an_event_without_a_shakemap_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(ShakeMapError, match="ShakeMap"):
            mmi_contour_url({"properties": {"products": {}}})

    def test_the_contours_parse_into_bands_at_and_above_mmi_four(
        self, cojutepeque_contours: Any
    ) -> None:
        bands = parse_mmi_bands(cojutepeque_contours)
        values = [band.mmi for band in bands]
        assert values == [
            Decimal("4.0"),
            Decimal("4.5"),
            Decimal("5.0"),
            Decimal("5.5"),
            Decimal("6.0"),
            Decimal("6.5"),
            Decimal("7.0"),
        ]

    def test_bands_below_the_declared_floor_are_dropped(
        self, cojutepeque_contours: Any
    ) -> None:
        bands = parse_mmi_bands(cojutepeque_contours)
        assert all(band.mmi >= MMI_SCALE_FLOOR for band in bands)
        assert len(cojutepeque_contours["features"]) > len(bands)

    def test_only_closed_rings_become_a_band(self, cojutepeque_contours: Any) -> None:
        """An open contour clipped by the grid edge bounds no area at all."""
        bands = parse_mmi_bands(cojutepeque_contours)
        for band in bands:
            for ring in band.geometry["coordinates"]:
                assert len(ring) >= 4, band.mmi
                assert ring[0] == ring[-1], band.mmi

    def test_a_degenerate_two_point_ring_is_dropped(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {"value": 5.0, "units": "mmi"},
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [
                            [[-89.0, 13.0], [-88.9, 13.1], [-89.0, 13.0]],
                            [
                                [-89.0, 13.0],
                                [-88.9, 13.0],
                                [-88.9, 13.1],
                                [-89.0, 13.0],
                            ],
                        ],
                    },
                }
            ],
        }
        bands = parse_mmi_bands(payload)
        assert len(bands) == 1
        assert bands[0].ring_count == 1

    def test_a_contour_file_with_no_usable_band_is_refused(self) -> None:
        with pytest.raises(ShakeMapError, match="no closed"):
            parse_mmi_bands({"type": "FeatureCollection", "features": []})

    def test_the_release_carries_the_shakemap_grid_timestamp(
        self, cojutepeque_detail: Any, cojutepeque_contours: Any
    ) -> None:
        """ShakeMap is revised, so a figure without its grid time is undated."""
        release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
        assert release.grid_processed_at is not None
        assert release.grid_processed_at.tzinfo is not None
        assert release.event_id == COJUTEPEQUE_EVENT_ID

    def test_the_release_publishes_the_shakemaps_own_declared_maximum(
        self, cojutepeque_detail: Any, cojutepeque_contours: Any
    ) -> None:
        """The contour ceiling understates the peak; publishing both shows it.

        ShakeMap declares maxmmi 7.504 for this event while the highest drawn
        contour is 7.0, so a max taken from the contours is short by up to one
        contour interval. Both numbers travel together so the gap is visible.
        """
        release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
        assert release.declared_max_mmi == Decimal("7.504")
        assert max(band.mmi for band in release.bands) == Decimal("7.0")
        assert release.contour_interval == Decimal("0.5")

    def test_an_event_with_no_pager_publishes_the_absence(
        self, cojutepeque_detail: Any, cojutepeque_contours: Any
    ) -> None:
        """PAGER did not exist in 2001. An absent alert is not a green one."""
        release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
        assert release.pager is None

    def test_a_pager_alert_is_published_with_its_range_and_never_a_count(
        self, la_libertad_detail: Any, cojutepeque_contours: Any
    ) -> None:
        release = parse_shakemap_release(la_libertad_detail, cojutepeque_contours)
        assert release.pager is not None
        assert release.pager.level == "yellow"
        assert release.pager.lower_bound == 1
        assert release.pager.upper_bound == 99
        assert "1-99" in release.pager.band_label


class TestNoCasualtyClaimIsEverPublished:
    """The one thing this system must never say."""

    def test_the_four_pager_bands_carry_the_published_thresholds(self) -> None:
        bands = {band.level: band for band in PAGER_ALERT_BANDS}
        assert bands["green"].lower_bound == 0 and bands["green"].upper_bound == 0
        assert bands["yellow"].lower_bound == 1 and bands["yellow"].upper_bound == 99
        assert bands["orange"].lower_bound == 100
        assert bands["orange"].upper_bound == 999
        assert bands["red"].lower_bound == 1000
        assert bands["red"].upper_bound is None

    def test_an_unknown_pager_level_is_not_invented(self) -> None:
        assert pager_alert_band("chartreuse") is None

    def test_the_prohibition_names_what_may_not_be_reported(self) -> None:
        prohibition = CASUALTY_REPORTING_PROHIBITION.lower()
        for forbidden in ("casualt", "victim", "death"):
            assert forbidden in prohibition
        assert "exposed population" in prohibition

    def test_the_prohibition_explains_why_pager_is_not_a_count(self) -> None:
        prohibition = CASUALTY_REPORTING_PROHIBITION.lower()
        assert "probabilistic" in prohibition

    def test_the_revision_warning_requires_the_grid_timestamp(self) -> None:
        warning = SHAKEMAP_REVISION_WARNING.lower()
        assert "revis" in warning
        assert "timestamp" in warning or "grid time" in warning

    def test_no_published_hazard_field_is_named_after_a_casualty(self) -> None:
        """A field name is read more often than a disclaimer."""
        ranking = score_hazard(_three_districts())
        names = {variable.key for variable in HAZARD_VARIABLES}
        names |= {theme.theme for theme in ranking.districts[0].themes}
        rendered = " ".join(names).lower()
        for forbidden in ("fatal", "death", "casualt", "victim", "dead"):
            assert forbidden not in rendered

    def test_the_hazard_interpretation_refuses_the_damage_reading(self) -> None:
        interpretation = HAZARD_SCORE_INTERPRETATION.lower()
        assert "casualt" in interpretation
        assert "damage" in interpretation


# --------------------------------------------------------------------------- #
# Live corpus: the index against the real 262 districts
# --------------------------------------------------------------------------- #


async def _session() -> AsyncSession:
    """Open a session against the live PostGIS container."""
    engine = create_async_engine(settings.database_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return maker()


async def _require_corpus(session: AsyncSession) -> None:
    """Skip when the census and OSM corpora have not been ingested."""
    try:
        units = await session.scalar(
            text("SELECT count(*) FROM census_population_unit WHERE dug_level = 2")
        )
        access = await session.scalar(text("SELECT count(*) FROM osm_unit_access"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"The PRIO-SV corpus is not reachable: {exc}")
    if not units or not access:
        pytest.skip("The corpus is empty; run 'just census-ingest' and 'just osm-ingest'")


class TestLiveZonalStatistics:
    """The MMI bands against the 902 real DEGURBA polygons."""

    async def test_the_zonal_pass_returns_one_input_per_district(
        self, cojutepeque_contours: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            inputs = await HazardRepository(session).district_inputs(bands)
            assert len(inputs) == EXPECTED_DISTRICT_COUNT
            assert len({d.district_code for d in inputs}) == EXPECTED_DISTRICT_COUNT
        finally:
            await session.close()

    async def test_the_districts_around_the_epicentre_are_the_most_shaken(
        self, cojutepeque_contours: Any
    ) -> None:
        """The 2001-02-13 event was centred 5 km south of Cojutepeque.

        It devastated Cuscatlán, San Vicente and La Paz, and the highest MMI
        bands have to fall there. If a department on the far side of the country
        reaches the top band, the zonal statistics are joining the wrong geometry.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            inputs = await HazardRepository(session).district_inputs(bands)
            ranking = score_hazard(inputs)
            top = [d for d in ranking.districts if d.score is not None][:20]
            departments = {d.district_code[:2] for d in top}
            assert departments <= {"06", "07", "08", "10", "11"}, departments
        finally:
            await session.close()

    async def test_an_unshaken_district_is_published_as_a_zero_not_a_hole(
        self, cojutepeque_contours: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            ranking = score_hazard(
                await HazardRepository(session).district_inputs(bands)
            )
            unshaken = [d for d in ranking.districts if not d.shaken]
            assert unshaken
            for district in unshaken:
                assert district.score == 0
                assert district.max_mmi is None
                assert district.estimated_exposed_population == 0
        finally:
            await session.close()

    async def test_nobody_is_exposed_below_the_mmi_six_threshold(
        self, cojutepeque_contours: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            ranking = score_hazard(
                await HazardRepository(session).district_inputs(bands)
            )
            for district in ranking.districts:
                if district.max_mmi is not None and district.max_mmi < Decimal(6):
                    assert district.estimated_exposed_population == 0, (
                        district.district_name
                    )
        finally:
            await session.close()

    async def test_the_exposed_population_never_exceeds_the_district_population(
        self, cojutepeque_contours: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            ranking = score_hazard(
                await HazardRepository(session).district_inputs(bands)
            )
            for district in ranking.districts:
                assert district.estimated_exposed_population <= (
                    district.population or 0
                ), district.district_name
        finally:
            await session.close()

    async def test_bands_outside_the_country_shake_nobody(self) -> None:
        """A contour over the Pacific must not produce exposure on land."""
        session = await _session()
        try:
            await _require_corpus(session)
            offshore = parse_mmi_bands(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "properties": {"value": 9.0, "units": "mmi"},
                            "geometry": {
                                "type": "MultiLineString",
                                "coordinates": [
                                    [
                                        [-95.0, 5.0],
                                        [-94.0, 5.0],
                                        [-94.0, 6.0],
                                        [-95.0, 6.0],
                                        [-95.0, 5.0],
                                    ]
                                ],
                            },
                        }
                    ],
                }
            )
            inputs = await HazardRepository(session).district_inputs(offshore)
            ranking = score_hazard(inputs)
            assert ranking.shaken_unit_count == 0
            assert all(district.score == 0 for district in ranking.districts)
        finally:
            await session.close()


class TestLiveComposedIndex:
    """The three dimensions on one geography, which is what C4 exists for."""

    async def test_the_baseline_index_matches_the_verified_v_and_lcc_rankings(
        self,
    ) -> None:
        """Baseline is V x LCC, so its top must come from those two rankings.

        C1 found Cacaopera, Victoria, Yamabal and Lislique worst on V; C2 found
        Jucuarán, San Pablo Tacachico, Cinquera and San Fernando worst on LCC.
        The composed structural top has to be drawn from the departments both
        agreed on -- Cabañas, Chalatenango, La Unión and San Miguel's north.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            index = await PrioRepository(session).baseline_index()
            assert index.mode is PrioMode.BASELINE
            assert index.event is None
            top = [d for d in index.districts if d.score is not None][:10]
            names = {d.district_name for d in top}
            assert "Lislique" in names
            assert "Victoria" in names
            departments = {d.district_code[:2] for d in top}
            assert departments <= {"04", "05", "09", "10", "12", "13", "14"}, departments
        finally:
            await session.close()

    async def test_the_event_index_is_dominated_by_the_shaken_districts(
        self, cojutepeque_contours: Any, cojutepeque_detail: Any
    ) -> None:
        """The check that matters: hazard has to beat structural disadvantage.

        Under the strict INFORM composition a district outside the shaking
        footprint scores zero however poor it is, so every district in the event
        top 20 must be one the event actually reached.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
            index = await PrioRepository(session).event_index(release)
            assert index.mode is PrioMode.EVENT
            top = [d for d in index.districts if d.score is not None][:20]
            for district in top:
                assert district.max_mmi is not None, district.district_name
                assert district.max_mmi >= Decimal(6), district.district_name
            departments = {d.district_code[:2] for d in top}
            assert departments <= {"06", "07", "08", "10", "11"}, departments
        finally:
            await session.close()

    async def test_the_event_top_district_is_not_a_far_away_one(
        self, cojutepeque_contours: Any, cojutepeque_detail: Any
    ) -> None:
        """A far district outranking the epicentre means the hazard was discarded.

        This is the regression the non-annihilating rescale produced: Victoria
        (Cabañas, MMI 4.5) and Lislique (La Unión, never shaken) led its ranking.
        Both must sit below every red district under the shipped composition.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
            index = await PrioRepository(session).event_index(release)
            by_name = {d.district_name: d for d in index.districts}
            red = [
                d
                for d in index.districts
                if d.alert_class is DgpcAlertClass.ROJA
            ]
            assert red
            worst_red = min(d.score for d in red)
            assert by_name["Lislique"].score == 0
            assert by_name["Victoria"].score < worst_red
        finally:
            await session.close()

    async def test_exactly_one_district_is_zeroed_by_a_percentile_floor(
        self, cojutepeque_contours: Any, cojutepeque_detail: Any
    ) -> None:
        """Pinned so a normalisation change cannot absorb this silently.

        Antiguo Cuscatlán's LCC is exactly 0 -- it ranks 262nd of 262 on coping
        capacity -- so INFORM's annihilating zero takes its composed score to 0
        in any event. If a future corpus gives a second district an exact zero,
        or takes this one away, that is a change in what the index can express
        and has to be re-read rather than inherited.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
            index = await PrioRepository(session).event_index(release)
            floored = [
                d
                for d in index.districts
                if d.zeroed_by and HAZARD_DIMENSION_KEY not in d.zeroed_by
            ]
            assert [d.district_name for d in floored] == ["Antiguo Cuscatlán"]
            assert floored[0].zeroed_by == ("lack_of_coping_capacity",)
        finally:
            await session.close()

    async def test_every_red_and_orange_district_carries_its_sphere_minimums(
        self, cojutepeque_contours: Any, cojutepeque_detail: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
            index = await PrioRepository(session).event_index(release)
            triggered = [
                d
                for d in index.districts
                if d.alert_class
                in (DgpcAlertClass.ROJA, DgpcAlertClass.NARANJA)
            ]
            assert triggered
            for district in triggered:
                assert district.sphere is not None, district.district_name
                exposed = district.sphere.exposed_population
                assert exposed == district.estimated_exposed_population
                assert district.sphere.water_litres_per_day == 15 * exposed
                assert district.sphere.food_kcal_per_day == 2100 * exposed
        finally:
            await session.close()

    async def test_a_green_district_carries_no_sphere_figure(
        self, cojutepeque_contours: Any, cojutepeque_detail: Any
    ) -> None:
        """Sphere minimums are published for the classes that trigger them."""
        session = await _session()
        try:
            await _require_corpus(session)
            from app.modules.prioritization.infrastructure.prio_repository import (
                PrioRepository,
            )

            release = parse_shakemap_release(cojutepeque_detail, cojutepeque_contours)
            index = await PrioRepository(session).event_index(release)
            green = [
                d for d in index.districts if d.alert_class is DgpcAlertClass.VERDE
            ]
            assert green
            assert all(d.sphere is None for d in green)
        finally:
            await session.close()


class TestPrioApi:
    """The published contract, including the mode a caller must never guess."""

    async def _client(self) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        )

    async def _skip_without_corpus(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
        finally:
            await session.close()

    async def test_the_index_defaults_to_the_baseline_mode_and_says_so(self) -> None:
        await self._skip_without_corpus()
        async with await self._client() as client:
            response = await client.get("/api/v1/prioritization/index/districts")
            assert response.status_code == 200
            payload = response.json()
            assert payload["mode"] == "baseline"
            assert payload["dimension_keys"] == list(BASELINE_DIMENSION_KEYS)
            assert payload["event"] is None
            assert len(payload["districts"]) == EXPECTED_DISTRICT_COUNT

    async def test_the_index_publishes_the_warnings_a_reader_needs(self) -> None:
        await self._skip_without_corpus()
        async with await self._client() as client:
            response = await client.get("/api/v1/prioritization/index/districts")
            payload = response.json()
            assert payload["ecological_fallacy"] == ECOLOGICAL_FALLACY_WARNING
            assert payload["modifiable_areal_unit_problem"] == MAUP_WARNING
            assert payload["methodology"]["composition_rule"] == PRIO_COMPOSITION_RULE
            assert payload["alert_classes"]
            assert payload["class_distribution"]

    async def test_an_unknown_district_audit_is_a_404(self) -> None:
        await self._skip_without_corpus()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/index/districts/999999"
            )
            assert response.status_code == 404

    async def test_the_audit_endpoint_exposes_every_dimension_behind_one_score(
        self,
    ) -> None:
        await self._skip_without_corpus()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/index/districts/010101"
            )
            assert response.status_code == 200
            payload = response.json()
            keys = {d["dimension"] for d in payload["dimensions"]}
            assert keys == set(BASELINE_DIMENSION_KEYS)
            assert payload["methodology"]["uses_principal_components"] is False
            assert payload["declared_gaps"]

    async def test_the_hazard_endpoint_requires_an_event(self) -> None:
        await self._skip_without_corpus()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/hazard-exposure/districts"
            )
            assert response.status_code == 422

    async def test_the_openapi_contract_declares_the_new_operation_ids(self) -> None:
        schema = app.openapi()
        paths = schema["paths"]
        assert (
            paths["/api/v1/prioritization/index/districts"]["get"]["operationId"]
            == "listDistrictPrioIndex"
        )
        assert (
            paths["/api/v1/prioritization/index/districts/{district_code}"]["get"][
                "operationId"
            ]
            == "getDistrictPrioIndexAudit"
        )
        assert (
            paths["/api/v1/prioritization/hazard-exposure/districts"]["get"][
                "operationId"
            ]
            == "listDistrictHazardExposure"
        )
        assert (
            paths["/api/v1/prioritization/hazard-exposure/events"]["get"][
                "operationId"
            ]
            == "listHazardExposureEvents"
        )


class TestHazardRepositoryRefusals:
    """A wrong unit set is worse than an error, exactly as in V and LCC."""

    async def test_an_empty_band_list_is_refused(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            with pytest.raises(HazardCorpusError, match="band"):
                await HazardRepository(session).district_inputs([])
        finally:
            await session.close()

    async def test_a_restricted_district_set_is_refused(
        self, cojutepeque_contours: Any
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            bands = parse_mmi_bands(cojutepeque_contours)
            with pytest.raises(HazardCorpusError, match="districts"):
                await HazardRepository(session).district_inputs(
                    bands, district_codes=["010101"]
                )
        finally:
            await session.close()
