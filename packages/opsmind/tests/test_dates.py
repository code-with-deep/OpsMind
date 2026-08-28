"""Unit tests for date-range normalizer."""

from datetime import date

import pytest

from opsmind.tools.dates import normalize_date_range


def test_problem_and_prior_week_aliases():
    problem = normalize_date_range("problem week")
    assert problem.start == date(2026, 8, 17)
    assert problem.end == date(2026, 8, 23)

    prior = normalize_date_range("prior_week")
    assert prior.start == date(2026, 8, 10)
    assert prior.end == date(2026, 8, 16)


def test_this_week_relative_to_as_of():
    rng = normalize_date_range("this_week", as_of=date(2026, 8, 20))
    assert rng.start == date(2026, 8, 17)
    assert rng.end == date(2026, 8, 23)


def test_explicit_iso_range():
    rng = normalize_date_range("2026-08-17:2026-08-23")
    assert rng.label == "explicit"
    assert rng.start.isoformat() == "2026-08-17"


def test_invalid_expression():
    with pytest.raises(ValueError):
        normalize_date_range("next quarter")
