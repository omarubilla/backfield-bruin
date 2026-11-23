"""Tests for the Bruin benchmark export (run after scripts/run_pipeline.sh)."""
import json
import os

import jsonschema
import pytest

from bruin_export import payload as P

ROOT = os.path.dirname(os.path.dirname(__file__))
SCHEMA = json.load(open(os.path.join(ROOT, "docs", "athlete_benchmark.schema.json")))
ATHLETE = "bf-demo-qb-001"


@pytest.fixture(scope="module")
def doc():
    d = P.build(ATHLETE)
    assert d is not None
    return d


def by_metric(doc):
    return {m["metric"]: m for m in doc["measurements"]}


def test_payload_matches_schema(doc):
    jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker()).validate(json.loads(json.dumps(doc, default=str)))


def test_evaluation_id_is_deterministic(doc):
    assert P.build(ATHLETE)["evaluationId"] == doc["evaluationId"]


def test_percentile_only_when_calculable(doc):
    for m in doc["measurements"]:
        if m["percentile_status"] == "calculated":
            assert m["percentile"] is not None and m["benchmark"]["sample_size"] >= 20 and m["measured"]
        else:
            assert m["percentile"] is None and m["missing"]["percentile_withheld"]


def test_ten_yard_split_has_no_fabricated_cohort(doc):
    m = by_metric(doc)["ten_yd_split_sec"]
    assert m["measured"] and m["value"] == 1.66
    assert m["benchmark"] is None and m["percentile"] is None
    assert m["percentile_status"] == "no_reference_cohort" and m["missing"]["cohort_missing"]
    assert "ten_yd_split_sec" in doc["summary"]["missing_cohorts"]


def test_unmeasured_combine_metrics_are_explicit(doc):
    m = by_metric(doc)
    for metric in ("bench_reps", "cone_sec"):
        assert m[metric]["measured"] is False and m[metric]["value"] is None
        assert m[metric]["benchmark"]["sample_size"] > 0
        assert m[metric]["percentile_status"] == "not_measured"
        assert metric in doc["summary"]["missing_values"]


def test_measured_values_have_units_and_source(doc):
    for m in doc["measurements"]:
        assert m["unit"] in {"in", "lb", "s", "reps"}
        if m["measured"]:
            assert m["source"]["record_id"] and m["source"]["capture_method"] and m["source"]["provider"]


def test_percentile_direction_matches_cohort(doc):
    m = by_metric(doc)
    forty = m["forty_sec"]  # lower is better: 4.82 s vs QB median 4.81 -> just under the 50th percentile
    assert forty["lower_is_better"] and 40 < forty["percentile"] < 50
    broad = m["broad_jump_in"]  # higher is better: 112 in vs median 111 -> about the 50th
    assert not broad["lower_is_better"] and 45 < broad["percentile"] < 56


def test_caveats_for_hand_timed_and_self_reported(doc):
    m = by_metric(doc)
    assert m["forty_sec"]["comparability"] == "caveat"
    assert m["height_in"]["comparability"] == "caveat"
    assert m["vertical_in"]["comparability"] == "comparable"


def test_pipeline_status_embedded(doc):
    p = doc["pipeline"]
    assert p["tool"] == "bruin" and p["validated"] is True and p["status"] == "succeeded"
    assert p["quality_checks"]["failed_blocking"] == 0
    assert {x["provider"] for x in p["providers"]} >= {"nflverse", "collegefootballdata", "pff", "backfield-demo"}


def test_pff_context_is_labelled_and_separate(doc):
    ctx = doc["pffContext"]
    assert ctx["provider"] == "pff" and ctx["status"] == "available"
    assert all(r["gradeSource"] == "PFF" and r["gradeMetric"].startswith("pff_grade_") for r in ctx["positionReference"])
    assert {r["league"] for r in ctx["positionReference"]} == {"nfl", "ncaa"}
    # PFF never leaks into the combine measurements
    assert not any("pff" in m["metric"] for m in doc["measurements"])
    assert all((m["benchmark"] or {}).get("source", "nflverse combine") == "nflverse combine" for m in doc["measurements"])


def test_synthetic_hs_athlete_is_not_matched_to_pff(doc):
    m = doc["pffContext"]["athleteMatch"]
    assert m["matched"] is False and m["pffPlayerId"] is None and doc["pffContext"]["playerSeasons"] == []


def test_redacted_payload_has_no_pff_values():
    d = P.build(ATHLETE, redact_pff=True)
    assert d["pffContext"]["redacted"] is True
    assert all(r["distribution"] is None for r in d["pffContext"]["positionReference"])
    jsonschema.Draft202012Validator(SCHEMA).validate(json.loads(json.dumps(d, default=str)))


def test_pff_player_lookup_links_by_provider_id():
    rows = P.pff_search("Joe Burrow", league="nfl", season=2025)
    assert rows and rows[0]["identity_match_type"] == "provider_id_nflverse_pff_id" and rows[0]["pfr_id"] == "BurrJo01"
    assert rows[0]["grade_source"] == "PFF"


# --- real linked player (gold.player_benchmark_results) ---

REAL = "pfr:CookBr03"


def test_real_player_payload_valid_and_linked_by_provider_id():
    d = P.build(REAL)
    jsonschema.Draft202012Validator(SCHEMA).validate(json.loads(json.dumps(d, default=str)))
    assert d["athlete"]["isSynthetic"] is False and d["athlete"]["position"] == "QB"
    assert "players.pff_id" in d["athlete"]["identityProvider"] and "00-0040398" in d["athlete"]["identityProvider"]
    m = d["pffContext"]["athleteMatch"]
    assert m["matched"] and m["method"] == "provider_id" and m["pffPlayerId"] == "124199"
    assert {(s["league"], s["season"]) for s in d["pffContext"]["playerSeasons"]} >= {("ncaa", 2024), ("nfl", 2025)}


def test_real_player_combine_values_are_published_and_not_imputed():
    m = by_metric(P.build(REAL))
    assert m["forty_sec"]["value"] == 4.59 and m["forty_sec"]["source"]["provider"] == "nflverse"
    assert m["bench_reps"]["measured"] is False and m["bench_reps"]["percentile"] is None
    assert m["bench_reps"]["percentile_status"] == "not_measured"
    # player is excluded from his own cohort: percentile denominator is cohort n - 1
    assert 85 < m["forty_sec"]["percentile"] < 92


def test_real_player_redacted_public_version():
    d = P.build(REAL, redact_pff=True)
    assert d["pffContext"]["playerSeasons"] == [] and d["pffContext"]["redacted"] is True
    assert all(r["distribution"] is None for r in d["pffContext"]["positionReference"])
