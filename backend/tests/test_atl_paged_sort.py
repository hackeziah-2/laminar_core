"""Unit tests for ATL paged sort normalization."""
from app.repository.aircraft_technical_log import _normalize_atl_paged_sort


def test_normalize_atl_paged_sort_accepts_asc_desc_aliases():
    assert _normalize_atl_paged_sort("asc") == "sequence_no"
    assert _normalize_atl_paged_sort("desc") == "-sequence_no"
    assert _normalize_atl_paged_sort("ASC") == "sequence_no"
    assert _normalize_atl_paged_sort("DESC") == "-sequence_no"


def test_normalize_atl_paged_sort_accepts_sequence_no_variants():
    assert _normalize_atl_paged_sort("sequence_no") == "sequence_no"
    assert _normalize_atl_paged_sort("-sequence_no") == "-sequence_no"
    assert _normalize_atl_paged_sort("sequenceNo") == "sequence_no"
    assert _normalize_atl_paged_sort("-sequenceNo") == "-sequence_no"
    assert _normalize_atl_paged_sort("sequence_no:desc") == "-sequence_no"
    assert _normalize_atl_paged_sort("sequence_no asc") == "sequence_no"
    assert _normalize_atl_paged_sort("sequence_no desc") == "-sequence_no"
