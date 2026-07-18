from dc_mar_sdk.scripts.geocode_quality_collect import normalize_score, quality_bucket, perturb_address


def test_normalize_score_handles_both_scales():
    assert normalize_score(None) is None
    assert normalize_score(0.85) == 85.0
    assert normalize_score(85.0) == 85.0


def test_quality_bucket_rules():
    assert quality_bucket(None, 0, None) == "no_match"
    assert quality_bucket(None, 1, "err") == "error"
    assert quality_bucket(None, 1, None) == "unknown_score"
    assert quality_bucket(70.0, 1, None) == "low"
    assert quality_bucket(90.0, 1, None) == "medium"
    assert quality_bucket(99.0, 1, None) == "high"


def test_perturb_address_generates_multiple_variants():
    variants = perturb_address("1600 Pennsylvania Ave NW")
    assert "1600 Pennsylvania Ave NW" in variants
    assert "1600 Pennsylvania Ave" in variants
    assert "1600 Pennsylvania Avenue NW" in variants
    assert len(variants) > 3
