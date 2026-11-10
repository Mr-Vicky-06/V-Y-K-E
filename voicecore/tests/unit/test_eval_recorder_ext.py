"""Unit tests for evaluation recorder extensions:
- Manifest backward-compatibility
- CLI --only parser (numeric and repeat ranges)
- Number and clock-time normalisation
- Clock-dependent reminder rule (#28)
"""
from pathlib import Path
import json
import pytest

from scripts.record_eval_set import (
    eval_clock_dependent_28,
    is_id_selected,
    load_manifest,
    normalize_text_for_wer,
    normalize_words,
    parse_only_arg,
    calculate_wer,
    RECORDING_SET,
)


def test_manifest_backward_compatibility(tmp_path: Path):
    """Verify that older manifests lacking blast_radius or repeat_of load cleanly and backfill."""
    old_labels = [
        {"id": 1, "filename": "utt_001.wav", "expected_transcript": "open notepad"},
        {"id": 11, "filename": "utt_011.wav", "expected_transcript": "search files for quarterly report"},
        {"id": 999, "filename": "utt_999.wav", "expected_transcript": "custom external command"},
    ]
    labels_file = tmp_path / "labels.json"
    with labels_file.open("w", encoding="utf-8") as f:
        json.dump(old_labels, f)

    loaded = load_manifest(labels_file)
    assert len(loaded) == 3

    # ID 1 should have backfilled blast_radius='reversible', category='open_app'
    assert loaded[0]["id"] == 1
    assert loaded[0]["blast_radius"] == "reversible"
    assert loaded[0]["category"] == "open_app"
    assert loaded[0]["repeat_of"] is None

    # ID 11 should have backfilled blast_radius='none', category='search_files'
    assert loaded[1]["id"] == 11
    assert loaded[1]["blast_radius"] == "none"
    assert loaded[1]["category"] == "search_files"

    # ID 999 (uncataloged) should safely default without crash
    assert loaded[2]["id"] == 999
    assert loaded[2]["blast_radius"] == "none"
    assert loaded[2]["repeat_of"] is None


def test_parse_only_arg_ranges_and_ids():
    """Verify parsing of numeric ranges, repeat ranges, single IDs, and mixed filters."""
    # 1. New ranges specified in prompt
    s1 = parse_only_arg("41-55,R01-R12")
    assert is_id_selected(41, s1)
    assert is_id_selected(50, s1)
    assert is_id_selected(55, s1)
    assert not is_id_selected(40, s1)
    assert not is_id_selected(56, s1)
    assert not is_id_selected(1, s1)
    assert is_id_selected("R01", s1)
    assert is_id_selected("R06", s1)
    assert is_id_selected("R12", s1)
    assert not is_id_selected("R13", s1)

    # 2. Comma-separated discrete IDs
    s2 = parse_only_arg("1,2,5")
    assert is_id_selected(1, s2)
    assert is_id_selected(2, s2)
    assert is_id_selected(5, s2)
    assert not is_id_selected(3, s2)
    assert not is_id_selected(4, s2)

    # 3. Repeat sub-range with whitespace and mixed case
    s3 = parse_only_arg(" r01 - r04 , 9 ")
    assert is_id_selected("R01", s3)
    assert is_id_selected("R04", s3)
    assert not is_id_selected("R05", s3)
    assert is_id_selected(9, s3)
    assert not is_id_selected(10, s3)

    # 4. Empty string selects all
    s_empty = parse_only_arg("")
    assert is_id_selected(1, s_empty)
    assert is_id_selected(55, s_empty)
    assert is_id_selected("R12", s_empty)


def test_number_and_clock_time_normalisation():
    """Verify that word numbers, 12-hr AM/PM, and 24-hr times map to canonical tokens."""
    # 10:00 vs 10 a.m. vs ten
    t1 = normalize_text_for_wer("set a reminder to call mom tomorrow at 10:00")
    t2 = normalize_text_for_wer("set a reminder to call mom tomorrow at 10 a.m.")
    t3 = normalize_text_for_wer("set a reminder to call mom tomorrow at ten")
    assert t1 == t2 == t3 == ["set", "a", "reminder", "to", "call", "mom", "tomorrow", "at", "1000"]

    # 18:00 vs 6 p.m. vs six pm
    t4 = normalize_text_for_wer("remind me to buy milk tomorrow at 18:00")
    t5 = normalize_text_for_wer("remind me to buy milk tomorrow at 6 p.m.")
    t6 = normalize_text_for_wer("remind me to buy milk tomorrow at six pm")
    assert t4 == t5 == t6 == ["remind", "me", "to", "buy", "milk", "tomorrow", "at", "1800"]

    # Word numbers in intervals
    t7 = normalize_text_for_wer("remind me in 20 minutes")
    t8 = normalize_text_for_wer("remind me in twenty minutes")
    assert t7 == t8 == ["remind", "me", "in", "20", "minutes"]

    t9 = normalize_text_for_wer("stretch in 1 hour")
    t10 = normalize_text_for_wer("stretch in one hour")
    assert t9 == t10 == ["stretch", "in", "1", "hour"]

    # WER comparison
    ref = "set a reminder at 18:00"
    hyp = "set a reminder at 6 p.m."
    raw_wer, raw_edits, _ = calculate_wer(ref, hyp, normalize_fn=normalize_words)
    norm_wer, norm_edits, _ = calculate_wer(ref, hyp, normalize_fn=normalize_text_for_wer)

    assert raw_wer > 0.0
    assert raw_edits >= 1
    assert norm_wer == 0.0
    assert norm_edits == 0


def test_clock_dependent_reminder_rule_28():
    """Verify runtime clock check for case #28 ('remind me to call John at 15:00')."""
    # 1. When time is after 15:00 local (e.g. 16:30):
    ok_after, reason_after = eval_clock_dependent_28(hour=16, decision="REFUSE")
    assert ok_after is True
    assert "after 15:00 local -> REFUSE" in reason_after

    bad_after, reason_bad = eval_clock_dependent_28(hour=16, decision="ACT")
    assert bad_after is False
    assert "VIOLATION" in reason_bad

    # 2. When time is before 15:00 local (e.g. 10:15):
    ok_before_confirm, _ = eval_clock_dependent_28(hour=10, decision="CONFIRM")
    assert ok_before_confirm is True

    ok_before_act, _ = eval_clock_dependent_28(hour=10, decision="ACT")
    assert ok_before_act is True


def test_catalog_structure_and_blast_radii():
    """Verify that catalog has 67 items, all with valid blast radii and required categories."""
    assert len(RECORDING_SET) == 67

    valid_blast = {"none", "reversible", "destructive", "external"}
    for item in RECORDING_SET:
        assert item["blast_radius"] in valid_blast

    # Verify ID 41-55 categories
    for item in RECORDING_SET:
        if isinstance(item["id"], int) and 41 <= item["id"] <= 55:
            if item["id"] in (52, 53, 54):
                assert item["category"] == "Natural Variants"
            else:
                assert item["category"] == "Unsupported & Conversational Negatives"

    # Verify repeat takes R01-R12
    repeat_items = [i for i in RECORDING_SET if isinstance(i["id"], str) and i["id"].startswith("R")]
    assert len(repeat_items) == 12
    for r in repeat_items:
        assert r["category"] == "Repeat Takes"
        assert r["repeat_of"] is not None
