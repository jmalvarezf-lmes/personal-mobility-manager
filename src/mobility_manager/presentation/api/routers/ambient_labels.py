"""
Presentation: Ambient labels API router.

Endpoints:
  GET /ambient-labels/{label}/icon — cached DGT sticker icon
"""

from fastapi import APIRouter, HTTPException, Request, Response

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel

router = APIRouter(prefix="/ambient-labels", tags=["ambient-labels"])

# Icons are immutable once cached (see add-ambient-label-lookup design.md
# decision 9) — safe to cache publicly for a long time.
_CACHE_CONTROL = "public, max-age=31536000, immutable"


@router.get("/{label}/icon")
def get_ambient_label_icon(request: Request, label: str) -> Response:
    """
    Serve the cached DGT sticker icon for `label`.

    Intentionally unauthenticated (see design.md decision 9): the image is
    non-sensitive and identical for every caller — the same picture is
    public on DGT's own site. Returns 404 for label `A` (which never has a
    sticker) or for a label with no cache entry yet.
    """
    try:
        parsed_label = AmbientLabel(label)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown ambient label") from None

    if parsed_label == AmbientLabel.A:
        raise HTTPException(status_code=404, detail="Label A has no icon")

    icon_repo = request.app.state.ambient_label_icon_repo
    icon = icon_repo.get_by_label(parsed_label)
    if icon is None:
        raise HTTPException(status_code=404, detail="Icon not cached yet")

    return Response(
        content=icon.image_bytes,
        media_type=icon.content_type,
        headers={"Cache-Control": _CACHE_CONTROL},
    )
