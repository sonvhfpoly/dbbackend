from domains.guidance.models import EducationPath, PathType
from domains.guidance.anti_bias import DiversityValidator, RegionExpansionValidator, RecommendationCandidate

def make_path(id, type, location=None):
    return EducationPath(id=id, name=f"Path {id}", type=type, duration="1 year", location=location)

def test_diversity_validator_converts_university_only_list_into_mixed_list():
    catalog = [
        make_path(1, PathType.UNIVERSITY),
        make_path(2, PathType.UNIVERSITY),
        make_path(3, PathType.VOCATIONAL),
    ]
    candidates = [
        RecommendationCandidate(path=catalog[0], reasoning_explanation="a"),
        RecommendationCandidate(path=catalog[1], reasoning_explanation="b"),
    ]

    result = DiversityValidator().validate(candidates, catalog, student_location=None)

    types = {c.path.type for c in result}
    assert types == {PathType.UNIVERSITY, PathType.VOCATIONAL}
    assert len(result) == len(candidates)

def test_diversity_validator_leaves_already_mixed_list_untouched():
    catalog = [
        make_path(1, PathType.UNIVERSITY),
        make_path(2, PathType.VOCATIONAL),
        make_path(3, PathType.SHORT_COURSE),
    ]
    candidates = [
        RecommendationCandidate(path=catalog[0], reasoning_explanation="a"),
        RecommendationCandidate(path=catalog[1], reasoning_explanation="b"),
    ]

    result = DiversityValidator().validate(candidates, catalog, student_location=None)

    assert result == candidates

def test_diversity_validator_noop_when_catalog_has_no_alternative_type():
    catalog = [
        make_path(1, PathType.UNIVERSITY),
        make_path(2, PathType.UNIVERSITY),
    ]
    candidates = [RecommendationCandidate(path=catalog[0], reasoning_explanation="a")]

    result = DiversityValidator().validate(candidates, catalog, student_location=None)

    assert result == candidates

def test_region_expansion_validator_injects_remote_option_when_all_local():
    catalog = [
        make_path(1, PathType.UNIVERSITY, location="Can Tho"),
        make_path(2, PathType.VOCATIONAL, location="Can Tho"),
        make_path(3, PathType.SHORT_COURSE, location=None),  # remote/nationwide
    ]
    candidates = [
        RecommendationCandidate(path=catalog[0], reasoning_explanation="a"),
        RecommendationCandidate(path=catalog[1], reasoning_explanation="b"),
    ]

    result = RegionExpansionValidator().validate(candidates, catalog, student_location="Can Tho")

    assert any(c.path.location is None for c in result)
    assert len(result) == len(candidates)

def test_region_expansion_validator_noop_when_remote_option_already_present():
    catalog = [
        make_path(1, PathType.UNIVERSITY, location="Can Tho"),
        make_path(2, PathType.SHORT_COURSE, location=None),
    ]
    candidates = [
        RecommendationCandidate(path=catalog[0], reasoning_explanation="a"),
        RecommendationCandidate(path=catalog[1], reasoning_explanation="b"),
    ]

    result = RegionExpansionValidator().validate(candidates, catalog, student_location="Can Tho")

    assert result == candidates
