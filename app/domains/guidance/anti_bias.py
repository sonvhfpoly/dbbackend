from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from .models import EducationPath

@dataclass
class RecommendationCandidate:
    path: EducationPath
    reasoning_explanation: str

class BiasValidator(ABC):
    """Strategy interface: each validator inspects a candidate recommendation
    set and may replace entries to counter a specific narrowing-of-choice
    pattern. New rules are added by writing a new validator, not by editing
    existing ones (Open/Closed)."""

    @abstractmethod
    def validate(
        self,
        candidates: List[RecommendationCandidate],
        available_paths: List[EducationPath],
        student_location: Optional[str],
    ) -> List[RecommendationCandidate]:
        raise NotImplementedError

class DiversityValidator(BiasValidator):
    """If every recommended path shares the same PathType (e.g. all
    UNIVERSITY), swap the last one for a different type from the catalog. A
    single-track set of recommendations narrows the student's perceived
    options instead of expanding them, which the ethical requirements
    explicitly forbid — this holds regardless of what the AI itself decided."""

    def validate(self, candidates, available_paths, student_location):
        if not candidates:
            return candidates

        types_present = {c.path.type for c in candidates}
        if len(types_present) > 1:
            return candidates

        chosen_ids = {c.path.id for c in candidates}
        alternative = next(
            (p for p in available_paths if p.type not in types_present and p.id not in chosen_ids),
            None,
        )
        if alternative is None:
            return candidates  # catalog has no other type to offer; nothing to swap in

        result = list(candidates)
        result[-1] = RecommendationCandidate(
            path=alternative,
            reasoning_explanation=(
                "Được bổ sung để bạn có ít nhất một lựa chọn khác loại hình đào tạo "
                f"({alternative.type.value.lower()}) bên cạnh các gợi ý trên, thay vì chỉ thấy một "
                "hướng duy nhất. Đây là một tham khảo thêm — không phải lựa chọn bắt buộc."
            ),
        )
        return result

class RegionExpansionValidator(BiasValidator):
    """If every recommended path is tied to the student's exact location (none
    are remote/nationwide, i.e. `location is None`), swap the last one for a
    remote option. A student in a smaller locality shouldn't have their
    choices silently capped at whatever happens to exist in their own city."""

    def validate(self, candidates, available_paths, student_location):
        if not candidates or not student_location:
            return candidates

        already_expanded = any(c.path.location is None or c.path.location != student_location for c in candidates)
        if already_expanded:
            return candidates

        chosen_ids = {c.path.id for c in candidates}
        alternative = next(
            (p for p in available_paths if p.location is None and p.id not in chosen_ids),
            None,
        )
        if alternative is None:
            return candidates  # no remote/nationwide option exists in the catalog to offer

        result = list(candidates)
        result[-1] = RecommendationCandidate(
            path=alternative,
            reasoning_explanation=(
                f"Được bổ sung vì các gợi ý trên đều chỉ gắn với {student_location} — đây là một lựa "
                "chọn học từ xa/không giới hạn theo khu vực, để bạn có thêm tham khảo ngoài phạm vi "
                "địa phương. Bạn hoàn toàn có thể bỏ qua nếu không phù hợp."
            ),
        )
        return result

class AntiBiasEngine:
    """Runs a list of validators in sequence over a candidate set. Order
    matters only in that later validators see earlier ones' output — with the
    default pair, DiversityValidator and RegionExpansionValidator each touch
    at most the last slot, so both concerns can still land even if a set of
    size 1 only has room for one fix."""

    def __init__(self, validators: Optional[List[BiasValidator]] = None):
        self.validators = validators if validators is not None else [DiversityValidator(), RegionExpansionValidator()]

    def run(
        self,
        candidates: List[RecommendationCandidate],
        available_paths: List[EducationPath],
        student_location: Optional[str],
    ) -> List[RecommendationCandidate]:
        for validator in self.validators:
            candidates = validator.validate(candidates, available_paths, student_location)
        return candidates
