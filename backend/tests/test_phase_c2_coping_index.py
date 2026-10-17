"""Phase C2 tests: the Lack of Coping Capacity dimension of the PRIO-SV index.

Like the C1 suite, this module pins the *method* rather than a number, and for the
same reason: the only defensible part of an operational prioritisation index is
that it cites CDC/ATSDR SVI 2022 and INFORM 2017 rather than a preference. LCC
adds three failure modes C1 did not have, and most of this file exists to guard
them.

**A distance that lies about what it measures.** pgRouting is not installed and
cannot be installed inside the pinned ``postgis/postgis:16-3.4-alpine`` image, so
every distance here is geodesic -- true metres on the WGS 84 ellipsoid, and a
**lower bound on travel distance**. In a disaster the hospital 2 km away as the
crow flies can be 40 minutes away if the bridge fell, so a geodesic metre
published as a travel metre is an actively dangerous number. The tests therefore
assert on the *wording* of the published measure and basis: they require the
phrase "lower bound" and they forbid the claim of network or travel distance.

**A sub-dimension scored as if it were covered.** The institutional
sub-dimension is a declared gap -- no published subnational DRR capacity
indicator exists for El Salvador -- so it carries zero variables and no score.
The tests pin that LCC is consequently *infrastructure only* and that its score
equals the infrastructure score exactly. That identity is the wanted alarm: the
day a real institutional indicator is ingested, these tests fail, which is how a
silent half-measured dimension is prevented from surviving a refactor.

**An indicator that measures OpenStreetMap instead of the territory.** Two
candidate indicators were computed against the real national extract and
rejected on measured evidence, not taste, and the catalogue records both with the
numbers that disqualified them. The tests assert those exclusions stay declared,
because the cheapest way to break this index is to promote a context variable
into the index without re-reading why it was excluded.
"""

from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.privacy import SuppressionPolicy
from app.main import app
from app.modules.ingestion.domain.osm_extract import (
    OSM_SNAPSHOT_LICENCE,
    PRIMARY_ROAD_CLASS,
    CopingFacilityKind,
    OsmFacility,
    OsmRoad,
    classify_coping_facility,
    classify_road_class,
)
from app.modules.prioritization.domain.coping import (
    COPING_DECLARED_GAPS,
    COPING_VARIABLES,
    DISTANCE_BASIS,
    INFRASTRUCTURE_THEME,
    INSTITUTIONAL_THEME,
    LCC_DIMENSION_KEY,
    LCC_SCORE_INTERPRETATION,
    METRES_PER_PERSON,
    CopingInputError,
    DistrictCoping,
    DistrictCopingInput,
    CopingVariableInput,
    coping_index_variables_for_theme,
    coping_variables_for_theme,
    score_coping,
)
from app.modules.prioritization.infrastructure.coping_repository import (
    EXPECTED_DISTRICT_COUNT,
    CopingCorpusError,
    CopingRepository,
)

# --------------------------------------------------------------------------- #
# Fixtures: synthetic districts whose arithmetic is hand-checkable
# --------------------------------------------------------------------------- #

HEALTH_KEY = "LCC_HEALTHDIST"
ROAD_KEY = "LCC_ROADDIST"


def _district(
    code: str,
    name: str,
    population: int,
    health_metres: Decimal | None,
    road_metres: Decimal | None,
    *,
    far_health: Decimal | None = Decimal(0),
    far_road: Decimal | None = Decimal(0),
    shelter_count: Decimal | None = Decimal(1),
    fire_metres: Decimal | None = Decimal(1000),
) -> DistrictCopingInput:
    """Build one district input, expressing each distance as person-metres.

    ``E`` for a distance variable is population times metres, and its universe is
    the population, so ``EP`` is metres per person. Writing the fixture this way
    keeps the test honest about what the repository actually supplies: a weighted
    sum and its weight, never a pre-divided average.
    """
    people = Decimal(population)

    def person_metres(metres: Decimal | None) -> Decimal | None:
        return None if metres is None else metres * people

    return DistrictCopingInput(
        district_code=code,
        district_name=name,
        population=population,
        variables=(
            CopingVariableInput(
                variable=HEALTH_KEY,
                numerator=person_metres(health_metres),
                denominator=people,
            ),
            CopingVariableInput(
                variable=ROAD_KEY,
                numerator=person_metres(road_metres),
                denominator=people,
            ),
            CopingVariableInput(
                variable="LCC_HEALTHFAR",
                numerator=None if far_health is None else far_health * people,
                denominator=people,
            ),
            CopingVariableInput(
                variable="LCC_ROADFAR",
                numerator=None if far_road is None else far_road * people,
                denominator=people,
            ),
            CopingVariableInput(
                variable="LCC_SHELTER",
                numerator=shelter_count,
                denominator=people,
            ),
            CopingVariableInput(
                variable="LCC_FIREDIST",
                numerator=person_metres(fire_metres),
                denominator=people,
            ),
        ),
    )


def _three_districts() -> list[DistrictCopingInput]:
    """Three districts evenly separated on both index variables."""
    return [
        _district("010101", "Near", 1000, Decimal(500), Decimal(200)),
        _district("010102", "Middle", 1000, Decimal(5000), Decimal(2000)),
        _district("010103", "Far", 1000, Decimal(20000), Decimal(15000)),
    ]


def _by_code(ranking: Any, code: str) -> DistrictCoping:
    """Find one district in a ranking, failing loudly when it is absent."""
    match = next(
        (district for district in ranking.districts if district.district_code == code),
        None,
    )
    assert match is not None, f"district {code} missing from the ranking"
    return match


# --------------------------------------------------------------------------- #
# The distance basis: the one thing that must never be misread
# --------------------------------------------------------------------------- #


class TestDistanceIsDeclaredAsALowerBound:
    """Geodesic distance must be published as a lower bound on travel distance."""

    def test_the_distance_basis_declares_itself_a_lower_bound(self) -> None:
        assert "lower bound" in DISTANCE_BASIS.lower()

    def test_the_distance_basis_says_it_is_geodesic_rather_than_planar(self) -> None:
        assert "geodesic" in DISTANCE_BASIS.lower()

    def test_the_distance_basis_never_claims_to_be_travel_or_network_distance(
        self,
    ) -> None:
        """The failure mode that matters most: a straight line sold as a route.

        The basis may *mention* network routing in order to disclaim it, so the
        assertion is on the claim, not on the vocabulary: no sentence may assert
        that this is travel or network distance.
        """
        lowered = DISTANCE_BASIS.lower()
        assert "not travel distance" in lowered or "not a travel distance" in lowered
        assert "pgrouting" in lowered

    def test_every_distance_variable_names_its_measure_as_a_lower_bound(self) -> None:
        distance_variables = [
            variable
            for variable in COPING_VARIABLES
            if variable.measure == METRES_PER_PERSON
        ]
        assert distance_variables, "the dimension declares no distance variable"
        for variable in distance_variables:
            assert "lower bound" in variable.measure.lower(), variable.key

    def test_the_metres_measure_distinguishes_itself_from_a_percentage(self) -> None:
        assert "metre" in METRES_PER_PERSON.lower()
        assert "lower bound" in METRES_PER_PERSON.lower()


# --------------------------------------------------------------------------- #
# The variable catalogue and its declared exclusions
# --------------------------------------------------------------------------- #


class TestCopingVariableCatalogue:
    """The declared variable list, its directions, and its measured exclusions."""

    def test_variable_keys_are_unique(self) -> None:
        keys = [variable.key for variable in COPING_VARIABLES]
        assert len(keys) == len(set(keys))

    def test_every_variable_belongs_to_one_of_the_two_sub_dimensions(self) -> None:
        for variable in COPING_VARIABLES:
            assert variable.theme in (INFRASTRUCTURE_THEME, INSTITUTIONAL_THEME)

    def test_the_infrastructure_sub_dimension_carries_both_access_variables(
        self,
    ) -> None:
        keys = {
            variable.key
            for variable in coping_index_variables_for_theme(INFRASTRUCTURE_THEME)
        }
        assert keys == {HEALTH_KEY, ROAD_KEY}

    def test_the_institutional_sub_dimension_carries_no_variable_at_all(self) -> None:
        """A declared gap is an empty sub-dimension, not an imputed one."""
        assert coping_variables_for_theme(INSTITUTIONAL_THEME) == ()
        assert coping_index_variables_for_theme(INSTITUTIONAL_THEME) == ()

    def test_every_variable_declares_its_direction(self) -> None:
        for variable in COPING_VARIABLES:
            assert isinstance(variable.higher_is_worse, bool), variable.key

    def test_the_shelter_proxy_is_declared_lower_is_worse(self) -> None:
        """More shelter per capita is *better*, so its ranking is reversed.

        Direction belongs on the record rather than in a reviewer's memory: this
        is the only variable in either dimension whose high values are good.
        """
        shelter = next(v for v in COPING_VARIABLES if v.key == "LCC_SHELTER")
        assert shelter.higher_is_worse is False

    def test_every_context_variable_states_why_it_is_excluded(self) -> None:
        for variable in COPING_VARIABLES:
            if not variable.in_index:
                assert variable.exclusion_reason, variable.key

    def test_the_fire_station_exclusion_cites_the_missing_departments(self) -> None:
        """The exclusion must carry its evidence, not an opinion.

        Santa Ana is the country's second city and Cabañas a whole department;
        both hold zero ``amenity=fire_station`` in the national extract, which is
        what disqualifies the variable.
        """
        fire = next(v for v in COPING_VARIABLES if v.key == "LCC_FIREDIST")
        assert fire.in_index is False
        assert "Santa Ana" in fire.exclusion_reason
        assert "Cabañas" in fire.exclusion_reason

    def test_the_shelter_exclusion_cites_its_measured_incompleteness(self) -> None:
        shelter = next(v for v in COPING_VARIABLES if v.key == "LCC_SHELTER")
        assert shelter.in_index is False
        assert "1,199" in shelter.exclusion_reason

    def test_the_threshold_shares_are_excluded_as_duplicate_concepts(self) -> None:
        """Publishing both a mean distance and a threshold share double-weights it."""
        for key in ("LCC_HEALTHFAR", "LCC_ROADFAR"):
            variable = next(v for v in COPING_VARIABLES if v.key == key)
            assert variable.in_index is False
            assert variable.exclusion_reason


class TestInstitutionalGapIsVisible:
    """The institutional gap must be visible in the output, never imputed."""

    def test_the_institutional_gap_is_declared(self) -> None:
        subjects = " ".join(gap.subject for gap in COPING_DECLARED_GAPS)
        assert "institutional" in subjects.lower()

    def test_every_declared_gap_states_its_consequence_for_the_score(self) -> None:
        for gap in COPING_DECLARED_GAPS:
            assert gap.subject and gap.reason and gap.consequence

    def test_the_absence_of_network_routing_is_a_declared_gap(self) -> None:
        text_blob = " ".join(
            f"{gap.subject} {gap.reason} {gap.consequence}"
            for gap in COPING_DECLARED_GAPS
        ).lower()
        assert "pgrouting" in text_blob

    def test_the_institutional_theme_is_published_with_no_score(self) -> None:
        ranking = score_coping(_three_districts())
        district = _by_code(ranking, "010101")
        institutional = next(
            theme for theme in district.themes if theme.theme == INSTITUTIONAL_THEME
        )
        assert institutional.score is None
        assert institutional.percentile_rank is None
        assert institutional.variable_count == 0
        assert institutional.declared_gap is True

    def test_the_dimension_score_equals_the_infrastructure_score(self) -> None:
        """Pinned on purpose, as C1 pinned its saturation ceiling.

        With one scored sub-dimension INFORM's composition is algebraically the
        identity, so LCC *is* the infrastructure score today. Ingesting a real
        institutional indicator must break this test -- that failure is the
        wanted signal that the dimension stopped being half-measured.

        The tolerance is not slack, it is the arithmetic. The composition
        rescales [0, 10] onto [1, 10] and back, which multiplies by 9/10 and
        then by 10/9; 1/9 is non-terminating in base 10, so an arbitrary
        ``RPL`` round-trips to within one unit in the last place of the Decimal
        context rather than bit-exactly. Measured over the real 262 districts,
        42 of them differ in the raw Decimal by at most 1E-27 and **none differ
        at the six decimal places actually published**. Asserting bit-equality
        would therefore pass only for fixtures whose scores land on clean values
        -- which is exactly what this fixture does, and why asserting it that
        way would have been a test that claims more than it checks.
        """
        ranking = score_coping(_three_districts())
        for district in ranking.districts:
            infrastructure = next(
                theme
                for theme in district.themes
                if theme.theme == INFRASTRUCTURE_THEME
            )
            assert infrastructure.score is not None
            assert district.score is not None
            assert abs(district.score - infrastructure.score) < Decimal("1E-20")

    def test_the_identity_holds_at_published_precision(self) -> None:
        """At the precision a caller actually receives, the identity is exact."""
        quantum = Decimal("0.000001")
        ranking = score_coping(
            _three_districts()
            + [_district("010104", "Odd", 7, Decimal(1234), Decimal(567))]
        )
        for district in ranking.districts:
            if district.score is None:
                continue
            infrastructure = next(
                theme
                for theme in district.themes
                if theme.theme == INFRASTRUCTURE_THEME
            )
            assert infrastructure.score is not None
            assert district.score.quantize(quantum) == infrastructure.score.quantize(
                quantum
            )

    def test_the_ranking_declares_that_only_one_sub_dimension_is_measured(self) -> None:
        ranking = score_coping(_three_districts())
        assert ranking.scored_theme_count == 1
        assert ranking.declared_gap_theme_count == 1


# --------------------------------------------------------------------------- #
# The CDC pipeline, over a distance rather than a share
# --------------------------------------------------------------------------- #


class TestCopingScoring:
    """The seven CDC steps applied to a population-weighted distance."""

    def test_three_evenly_separated_districts_score_zero_five_and_ten(self) -> None:
        ranking = score_coping(_three_districts())
        assert _by_code(ranking, "010103").score == Decimal(10)
        assert _by_code(ranking, "010102").score == Decimal(5)
        assert _by_code(ranking, "010101").score == Decimal(0)

    def test_the_ranking_is_ordered_worst_coping_capacity_first(self) -> None:
        ranking = score_coping(_three_districts())
        codes = [district.district_code for district in ranking.districts]
        assert codes == ["010103", "010102", "010101"]
        assert ranking.districts[0].rank == 1

    def test_a_distance_variable_publishes_metres_per_person_as_its_rate(self) -> None:
        """``EP`` is person-metres over people, which is a mean distance."""
        ranking = score_coping(_three_districts())
        district = _by_code(ranking, "010102")
        health = next(v for v in district.variables if v.variable == HEALTH_KEY)
        assert health.estimate == 5_000_000
        assert health.universe == 1000
        assert health.rate == Decimal(5000)

    def test_a_longer_distance_ranks_worse_than_a_shorter_one(self) -> None:
        ranking = score_coping(_three_districts())
        far = _by_code(ranking, "010103")
        near = _by_code(ranking, "010101")
        assert far.score > near.score

    def test_more_shelter_per_capita_ranks_better_than_less(self) -> None:
        """The reversed direction has to actually reverse the percentile."""
        districts = [
            _district("010101", "Few", 1000, Decimal(1000), Decimal(1000),
                      shelter_count=Decimal(1)),
            _district("010102", "Many", 1000, Decimal(1000), Decimal(1000),
                      shelter_count=Decimal(50)),
        ]
        ranking = score_coping(districts)
        few = _by_code(ranking, "010101")
        many = _by_code(ranking, "010102")
        few_shelter = next(v for v in few.variables if v.variable == "LCC_SHELTER")
        many_shelter = next(v for v in many.variables if v.variable == "LCC_SHELTER")
        assert few_shelter.percentile > many_shelter.percentile

    def test_the_theme_percentile_sum_is_the_sum_of_its_variable_percentiles(
        self,
    ) -> None:
        ranking = score_coping(_three_districts())
        for district in ranking.districts:
            if district.score is None:
                continue
            infrastructure = next(
                theme
                for theme in district.themes
                if theme.theme == INFRASTRUCTURE_THEME
            )
            expected = sum(
                (
                    variable.percentile
                    for variable in district.variables
                    if variable.in_index and variable.percentile is not None
                ),
                Decimal(0),
            )
            assert infrastructure.percentile_sum == expected

    def test_tied_districts_share_one_score_and_one_rank(self) -> None:
        districts = [
            _district("010101", "A", 1000, Decimal(1000), Decimal(1000)),
            _district("010102", "B", 1000, Decimal(1000), Decimal(1000)),
        ]
        ranking = score_coping(districts)
        assert len({district.score for district in ranking.districts}) == 1
        assert {district.rank for district in ranking.districts} == {1}

    def test_an_empty_district_set_produces_an_empty_ranking(self) -> None:
        ranking = score_coping([])
        assert ranking.districts == ()
        assert ranking.scored_unit_count == 0

    def test_a_duplicate_district_code_is_refused(self) -> None:
        districts = _three_districts()
        districts.append(_district("010101", "Clone", 1, Decimal(1), Decimal(1)))
        with pytest.raises(CopingInputError, match="duplicate"):
            score_coping(districts)

    def test_a_variable_missing_from_a_district_is_refused(self) -> None:
        districts = _three_districts()
        broken = DistrictCopingInput(
            district_code="010104",
            district_name="Incomplete",
            population=100,
            variables=(
                CopingVariableInput(
                    variable=HEALTH_KEY,
                    numerator=Decimal(100),
                    denominator=Decimal(100),
                ),
            ),
        )
        districts.append(broken)
        with pytest.raises(CopingInputError, match="missing declared variable"):
            score_coping(districts)

    def test_the_score_is_declared_as_a_relative_rank_and_nothing_else(self) -> None:
        assert "relative" in LCC_SCORE_INTERPRETATION.lower()
        assert "262" in LCC_SCORE_INTERPRETATION

    def test_the_dimension_key_names_the_lack_of_coping_capacity(self) -> None:
        assert LCC_DIMENSION_KEY == "lack_of_coping_capacity"


class TestCopingRankingStability:
    """Percentile ranking must move ranks without touching measured inputs."""

    def test_adding_a_district_changes_ranks_but_not_raw_inputs(self) -> None:
        """The property Spielman et al. (2020) showed PCA rankings violate."""
        before = score_coping(_three_districts())
        after = score_coping(
            _three_districts()
            + [_district("010104", "Extreme", 1000, Decimal(99000), Decimal(99000))]
        )
        before_far = _by_code(before, "010103")
        after_far = _by_code(after, "010103")

        before_health = next(
            v for v in before_far.variables if v.variable == HEALTH_KEY
        )
        after_health = next(v for v in after_far.variables if v.variable == HEALTH_KEY)
        assert before_health.estimate == after_health.estimate
        assert before_health.rate == after_health.rate
        assert before_far.score != after_far.score

    def test_the_scored_unit_count_is_published_with_the_ranking(self) -> None:
        ranking = score_coping(_three_districts())
        assert ranking.scored_unit_count == 3
        assert ranking.withheld_unit_count == 0


class TestSuppressionNeverSurfaces:
    """A suppressed input must never appear, and must not be scored as a zero."""

    def test_a_district_missing_a_distance_gets_no_score(self) -> None:
        districts = _three_districts()
        districts.append(
            _district("010104", "Unmeasured", 1000, None, Decimal(1000))
        )
        ranking = score_coping(districts)
        unmeasured = _by_code(ranking, "010104")
        assert unmeasured.score is None
        assert unmeasured.rank is None
        assert unmeasured.withheld is True
        assert unmeasured.withheld_reason

    def test_a_withheld_district_is_excluded_from_everyone_else_s_percentiles(
        self,
    ) -> None:
        baseline = score_coping(_three_districts())
        with_hole = score_coping(
            _three_districts() + [_district("010104", "Hole", 1000, None, None)]
        )
        for code in ("010101", "010102", "010103"):
            assert _by_code(baseline, code).score == _by_code(with_hole, code).score

    def test_a_withheld_district_still_appears_in_the_ranking_as_a_hole(self) -> None:
        ranking = score_coping(
            _three_districts() + [_district("010104", "Hole", 1000, None, None)]
        )
        assert len(ranking.districts) == 4
        assert ranking.withheld_unit_count == 1

    def test_a_population_below_the_threshold_withholds_the_published_population(
        self,
    ) -> None:
        strict = SuppressionPolicy(minimum_units=5, label="k-anonymity k=5")
        districts = [
            _district("010101", "Tiny", 2, Decimal(1000), Decimal(1000)),
            _district("010102", "Normal", 5000, Decimal(2000), Decimal(2000)),
        ]
        ranking = score_coping(districts, policy=strict)
        tiny = _by_code(ranking, "010101")
        assert tiny.population is None

    def test_a_zero_denominator_withholds_the_district(self) -> None:
        districts = _three_districts()
        districts.append(
            DistrictCopingInput(
                district_code="010104",
                district_name="Empty",
                population=0,
                variables=tuple(
                    CopingVariableInput(
                        variable=variable.key,
                        numerator=Decimal(0),
                        denominator=Decimal(0),
                    )
                    for variable in COPING_VARIABLES
                ),
            )
        )
        ranking = score_coping(districts)
        assert _by_code(ranking, "010104").score is None


# --------------------------------------------------------------------------- #
# The OSM extract classifier: pure, and therefore testable without the 35 MB file
# --------------------------------------------------------------------------- #


class TestOsmExtractClassifier:
    """Tag mapping for the national Geofabrik extract."""

    @pytest.mark.parametrize(
        ("tags", "expected"),
        [
            ({"amenity": "hospital"}, CopingFacilityKind.HOSPITAL),
            ({"amenity": "clinic"}, CopingFacilityKind.CLINIC),
            ({"amenity": "doctors"}, CopingFacilityKind.CLINIC),
            ({"amenity": "fire_station"}, CopingFacilityKind.FIRE_STATION),
            ({"amenity": "school"}, CopingFacilityKind.SCHOOL),
            ({"amenity": "community_centre"}, CopingFacilityKind.COMMUNITY_CENTRE),
            ({"healthcare": "hospital"}, CopingFacilityKind.HOSPITAL),
            ({"healthcare": "clinic"}, CopingFacilityKind.CLINIC),
            ({"healthcare": "centre"}, CopingFacilityKind.CLINIC),
        ],
    )
    def test_a_known_tag_maps_to_its_facility_kind(
        self, tags: dict[str, str], expected: CopingFacilityKind
    ) -> None:
        assert classify_coping_facility(tags) is expected

    @pytest.mark.parametrize(
        "tags",
        [
            {},
            {"amenity": "pharmacy"},
            {"amenity": "restaurant"},
            {"healthcare": "dentist"},
            {"shop": "mall"},
        ],
    )
    def test_an_unrelated_tag_maps_to_nothing(self, tags: dict[str, str]) -> None:
        assert classify_coping_facility(tags) is None

    def test_the_amenity_tag_wins_over_the_healthcare_tag(self) -> None:
        """A building tagged both ways must resolve deterministically."""
        assert (
            classify_coping_facility({"amenity": "hospital", "healthcare": "clinic"})
            is CopingFacilityKind.HOSPITAL
        )

    @pytest.mark.parametrize(
        "highway", ["motorway", "trunk", "primary"]
    )
    def test_the_primary_network_classes_are_recognised(self, highway: str) -> None:
        assert classify_road_class({"highway": highway}) == PRIMARY_ROAD_CLASS

    @pytest.mark.parametrize(
        "highway",
        ["residential", "service", "track", "footway", "path", "secondary"],
    )
    def test_a_road_outside_the_primary_network_is_not_classified(
        self, highway: str
    ) -> None:
        """``secondary`` is deliberately excluded, and that is a declared choice.

        The feature document specifies the *primary* network, and widening the
        definition would silently change every road-access score.
        """
        assert classify_road_class({"highway": highway}) is None

    def test_a_non_highway_way_is_not_a_road(self) -> None:
        assert classify_road_class({"building": "yes"}) is None

    def test_the_snapshot_licence_is_the_odbl(self) -> None:
        assert "ODbL" in OSM_SNAPSHOT_LICENCE

    def test_a_facility_record_keeps_its_osm_identity(self) -> None:
        facility = OsmFacility(
            kind=CopingFacilityKind.HOSPITAL,
            osm_type="node",
            osm_id=12345,
            name="Hospital Nacional",
            longitude=-89.2,
            latitude=13.7,
        )
        assert facility.osm_type == "node"
        assert facility.osm_id == 12345

    def test_a_road_record_refuses_a_degenerate_geometry(self) -> None:
        """A one-node way has no length and would break ST_Distance."""
        with pytest.raises(ValueError, match="at least two"):
            OsmRoad(
                road_class=PRIMARY_ROAD_CLASS,
                highway_tag="primary",
                osm_id=1,
                coordinates=((-89.2, 13.7),),
            )


# --------------------------------------------------------------------------- #
# Live corpus: the index against the real 262 districts
# --------------------------------------------------------------------------- #


async def _session() -> AsyncSession:
    """Open a session against the live PostGIS container, or skip."""
    engine = create_async_engine(settings.database_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return maker()


async def _require_corpus(session: AsyncSession) -> None:
    """Skip when the OSM coping corpus has not been ingested."""
    try:
        facilities = await session.scalar(
            text("SELECT count(*) FROM osm_coping_facility")
        )
        access = await session.scalar(text("SELECT count(*) FROM osm_unit_access"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"OSM coping corpus is not reachable: {exc}")
    if not facilities or not access:
        pytest.skip("OSM coping corpus is empty; run 'just osm-ingest' first")


class TestLiveCopingCorpus:
    """The real national extract, loaded into PostGIS."""

    async def test_the_extract_holds_health_facilities_nationwide(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            hospitals = await session.scalar(
                text(
                    "SELECT count(*) FROM osm_coping_facility WHERE kind = 'hospital'"
                )
            )
            clinics = await session.scalar(
                text("SELECT count(*) FROM osm_coping_facility WHERE kind = 'clinic'")
            )
            assert hospitals and hospitals > 100
            assert clinics and clinics > 300
        finally:
            await session.close()

    async def test_every_district_has_a_cached_access_record(self) -> None:
        """Access is cached per DEGURBA unit, never computed per request."""
        session = await _session()
        try:
            await _require_corpus(session)
            districts = await session.scalar(
                text(
                    """
                    SELECT count(DISTINCT u.district_code)
                    FROM osm_unit_access a
                    JOIN census_population_unit u ON u.id = a.population_unit_id
                    """
                )
            )
            assert districts == EXPECTED_DISTRICT_COUNT
        finally:
            await session.close()

    async def test_the_repository_returns_one_input_per_district(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
            inputs = await CopingRepository(session).district_inputs()
            assert len(inputs) == EXPECTED_DISTRICT_COUNT
            codes = {district.district_code for district in inputs}
            assert len(codes) == EXPECTED_DISTRICT_COUNT
        finally:
            await session.close()

    async def test_the_real_ranking_puts_remote_rural_districts_worst(self) -> None:
        """The check a unit test cannot make: is the index pointing the right way?

        An index can pass every arithmetic test and still be backwards. The
        departments whose districts must dominate the worst end are the remote
        rural ones -- Morazán (13), Chalatenango (04), La Unión (14), Cabañas
        (09) -- and the metropolitan departments San Salvador (06) and La
        Libertad (05) must dominate the best end.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            ranking = score_coping(await CopingRepository(session).district_inputs())
            scored = [d for d in ranking.districts if d.score is not None]
            assert len(scored) == EXPECTED_DISTRICT_COUNT

            remote = {"04", "09", "13", "14", "12", "11"}
            metropolitan = {"05", "06"}
            worst_ten = [d.district_code[:2] for d in scored[:10]]
            best_ten = [d.district_code[:2] for d in scored[-10:]]

            assert sum(1 for code in worst_ten if code in remote) >= 7, worst_ten
            assert (
                sum(1 for code in best_ten if code in metropolitan) >= 4
            ), best_ten
        finally:
            await session.close()

    async def test_the_identity_survives_the_real_262_districts(self) -> None:
        """The synthetic fixture cannot catch a precision drift; this can.

        Measured: 42 of 262 districts differ in the raw Decimal by at most
        1E-27, and none differ at the six published decimal places.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            ranking = score_coping(await CopingRepository(session).district_inputs())
            quantum = Decimal("0.000001")
            for district in ranking.districts:
                if district.score is None:
                    continue
                infrastructure = next(
                    theme
                    for theme in district.themes
                    if theme.theme == INFRASTRUCTURE_THEME
                )
                assert infrastructure.score is not None
                assert abs(district.score - infrastructure.score) < Decimal("1E-20")
                assert district.score.quantize(
                    quantum
                ) == infrastructure.score.quantize(quantum)
        finally:
            await session.close()

    async def test_morazan_scores_better_than_cabanas_on_access(self) -> None:
        """Pins the one result that contradicted the expected geography.

        The brief expected Morazán among the worst-coping departments. It is
        not, and the cause is measurable rather than a defect: Morazán holds
        the densest mapped primary-care network in the country, 2.36 hospitals
        or clinics per 10,000 inhabitants against a national range down to
        Cabañas's 0.56, spread over 26 districts averaging 50.6 km². Its mean
        population-weighted distance to care is 2.23 km, the shortest of the
        rural departments and shorter than San Salvador's own 2.36 km.

        This is pinned so that if a future corpus change inverts it, the change
        is visible and has to be re-explained rather than quietly absorbed. It
        asserts the *ordering*, which is the claim, not the magnitudes.
        """
        session = await _session()
        try:
            await _require_corpus(session)
            ranking = score_coping(await CopingRepository(session).district_inputs())
            scored = [d for d in ranking.districts if d.score is not None]

            def mean_health_km(department: str) -> float:
                rates = [
                    float(variable.rate)
                    for district in scored
                    if district.district_code.startswith(department)
                    for variable in district.variables
                    if variable.variable == HEALTH_KEY and variable.rate is not None
                ]
                assert rates, f"department {department} has no scored district"
                return sum(rates) / len(rates) / 1000

            morazan = mean_health_km("13")
            cabanas = mean_health_km("09")
            chalatenango = mean_health_km("04")
            assert morazan < cabanas, (morazan, cabanas)
            assert morazan < chalatenango, (morazan, chalatenango)
        finally:
            await session.close()

    async def test_the_two_index_variables_are_not_collinear(self) -> None:
        """Two near-identical variables would be an undeclared double weight."""
        session = await _session()
        try:
            await _require_corpus(session)
            inputs = await CopingRepository(session).district_inputs()
            ranking = score_coping(inputs)
            scored = [d for d in ranking.districts if d.score is not None]
            health = []
            road = []
            for district in scored:
                for variable in district.variables:
                    if variable.variable == HEALTH_KEY and variable.rate is not None:
                        health.append(float(variable.rate))
                    if variable.variable == ROAD_KEY and variable.rate is not None:
                        road.append(float(variable.rate))
            assert len(health) == len(road) == len(scored)

            mean_h = sum(health) / len(health)
            mean_r = sum(road) / len(road)
            cov = sum((h - mean_h) * (r - mean_r) for h, r in zip(health, road))
            var_h = sum((h - mean_h) ** 2 for h in health) ** 0.5
            var_r = sum((r - mean_r) ** 2 for r in road) ** 0.5
            correlation = cov / (var_h * var_r)
            assert abs(correlation) < 0.6, correlation
        finally:
            await session.close()

    async def test_a_corpus_with_no_access_records_is_refused(self) -> None:
        """A percentile over the wrong unit set is worse than an error."""
        session = await _session()
        try:
            await _require_corpus(session)
            repository = CopingRepository(session)
            with pytest.raises(CopingCorpusError, match="districts"):
                await repository.district_inputs(district_codes=["010101"])
        finally:
            await session.close()


class TestCopingApi:
    """The published contract, including the gaps that travel with every score."""

    async def _client(self) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        )

    async def test_the_ranked_list_publishes_its_methodology_and_gaps(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
        finally:
            await session.close()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/coping-capacity/districts"
            )
            assert response.status_code == 200
            payload = response.json()
            assert len(payload["districts"]) == EXPECTED_DISTRICT_COUNT
            assert payload["methodology"]["uses_principal_components"] is False
            assert payload["methodology"]["dimension"] == LCC_DIMENSION_KEY
            assert "lower bound" in payload["distance_basis"].lower()
            assert payload["declared_gaps"]

    async def test_the_audit_endpoint_exposes_every_variable_behind_one_score(
        self,
    ) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
        finally:
            await session.close()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/coping-capacity/districts/010101"
            )
            assert response.status_code == 200
            payload = response.json()
            keys = {variable["variable"] for variable in payload["variables"]}
            assert keys == {variable.key for variable in COPING_VARIABLES}
            for variable in payload["variables"]:
                assert "estimate" in variable
                assert "universe" in variable
                assert "rate" in variable
                assert "percentile" in variable

    async def test_an_unknown_district_is_a_404(self) -> None:
        session = await _session()
        try:
            await _require_corpus(session)
        finally:
            await session.close()
        async with await self._client() as client:
            response = await client.get(
                "/api/v1/prioritization/coping-capacity/districts/999999"
            )
            assert response.status_code == 404

    def test_the_openapi_contract_declares_the_new_operation_ids(self) -> None:
        schema = app.openapi()
        paths = schema["paths"]
        assert (
            paths["/api/v1/prioritization/coping-capacity/districts"]["get"][
                "operationId"
            ]
            == "listDistrictCopingCapacity"
        )
        assert (
            paths["/api/v1/prioritization/coping-capacity/districts/{district_code}"][
                "get"
            ]["operationId"]
            == "getDistrictCopingCapacityAudit"
        )
