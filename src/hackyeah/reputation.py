"""Internal author reliability, derived from persisted verification decisions."""

from hackyeah import place_submissions, reports
from hackyeah.database import atomic


def _decisions() -> dict[str, list[bool]]:
    """Acceptance rate in [0, 1]; unreviewed authors default to 0.5.

    Each suggestion counts once. Editing it back to pending keeps the last
    verification decision until the new version has been verified.
    """
    results: dict[str, list[bool]] = {}
    with atomic:
        for report in reports._reports.values():
            reviewed = next(
                (
                    version
                    for version in [
                        report,
                        *reversed(reports._history.get(report.id, [])),
                    ]
                    if version.status != "pending"
                ),
                None,
            )
            if reviewed is not None:
                results.setdefault(report.author_id, []).append(
                    reviewed.status == "accepted"
                )
        for item in place_submissions.submissions.values():
            if item.status != "pending":
                results.setdefault(item.author_id, []).append(item.status == "accepted")
    return results


def scores() -> dict[str, float]:
    return {author: sum(values) / len(values) for author, values in _decisions().items()}


def title(author_id: str) -> str:
    """Reward reliability backed by reviewed contributions, including new users."""
    decisions = _decisions().get(author_id, [])
    score = sum(decisions) / len(decisions) if decisions else 0.5
    for minimum, reliability, name in (
        (50, 0.9, "Legenda Krakowa"),
        (25, 0.85, "Strażnik Wawelu"),
        (10, 0.75, "Przewodnik po Kazimierzu"),
        (3, 0.6, "Tropiciel Plant"),
    ):
        if len(decisions) >= minimum and score >= reliability:
            return name
    return "Krakowski Odkrywca"
