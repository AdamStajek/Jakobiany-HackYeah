"""Internal author reliability, derived from persisted verification decisions."""

from hackyeah import place_submissions, reports
from hackyeah.database import atomic


def scores() -> dict[str, float]:
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
    return {author: sum(values) / len(values) for author, values in results.items()}
