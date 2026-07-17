"""
Infrastructure: DGT ambient label HTML parser.

Parses the (server-rendered, no JS/AJAX) HTML returned by DGT's public
distintivo-ambiental form. See add-ambient-label-lookup design.md decisions
2 and 3 for the full rationale.

Branches on the response's result container class BEFORE extracting a
label, since DGT's Spanish prose can change wording without changing the
class it uses to drive the alert's visual style:

- `border-success` → a label was found. The letter is cross-checked between
  the sticker image's filename (`distintivo_(A|B|C|ECO|0)_...`) and the
  `Distintivo Ambiental X` prose text; a mismatch is treated as `error`
  (markup drift) rather than trusting either value.
- `alert-warning` → DGT's confirmed "no label" result. This is a genuine,
  confident terminal result (`status=found`, `label=A`), not an error.
- `alert-danger` → DGT found no record for the plate. Inconclusive
  (`status=not_found`), not necessarily wrong — could also be a transient
  hiccup — so it is retried later rather than treated as terminal.
- None of the three known shapes → unrecognized markup (drift, or a page
  DGT changed without notice). Treated as `status=error` since this is a
  parsing/integration failure, not a DGT-confirmed "not found".
"""

import logging
import re

from mobility_manager.domain.ports.ambient_label_lookup_port import (
    VehicleAmbientLabelResult,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)

logger = logging.getLogger(__name__)

_SUCCESS_CONTAINER_RE = re.compile(r'class="[^"]*\bborder-success\b[^"]*"')
_WARNING_CONTAINER_RE = re.compile(r'class="[^"]*\balert-warning\b[^"]*"')
_DANGER_CONTAINER_RE = re.compile(r'class="[^"]*\balert-danger\b[^"]*"')

_ICON_SRC_RE = re.compile(r'<img[^>]+src="([^"]*distintivo_[^"]+)"')
_ICON_FILENAME_LETTER_RE = re.compile(r"distintivo_(A|B|C|ECO|0)_")
_LABEL_TEXT_RE = re.compile(r"Distintivo\s+Ambiental\s+(A|B|C|ECO|0)\b")


def parse_ambient_label_response(html: str) -> VehicleAmbientLabelResult:
    """Parse a DGT distintivo-ambiental response into a VehicleAmbientLabelResult."""
    if _SUCCESS_CONTAINER_RE.search(html):
        return _parse_success_container(html)

    if _WARNING_CONTAINER_RE.search(html):
        return VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.A)

    if _DANGER_CONTAINER_RE.search(html):
        return VehicleAmbientLabelResult(status=AmbientLabelStatus.NOT_FOUND, label=None)

    logger.warning("DGT ambient label response matched none of the known container shapes")
    return VehicleAmbientLabelResult(status=AmbientLabelStatus.ERROR, label=None)


def _parse_success_container(html: str) -> VehicleAmbientLabelResult:
    """Extract and cross-check the letter from a border-success container."""
    filename_match = _ICON_FILENAME_LETTER_RE.search(html)
    text_match = _LABEL_TEXT_RE.search(html)

    if filename_match is None or text_match is None:
        logger.warning("DGT success container missing the expected filename or prose signal")
        return VehicleAmbientLabelResult(status=AmbientLabelStatus.ERROR, label=None)

    filename_letter = filename_match.group(1)
    text_letter = text_match.group(1)
    if filename_letter != text_letter:
        logger.warning(
            "DGT ambient label cross-check mismatch: filename says %s, text says %s",
            filename_letter,
            text_letter,
        )
        return VehicleAmbientLabelResult(status=AmbientLabelStatus.ERROR, label=None)

    icon_match = _ICON_SRC_RE.search(html)
    icon_relative_url = icon_match.group(1) if icon_match else None

    return VehicleAmbientLabelResult(
        status=AmbientLabelStatus.FOUND,
        label=AmbientLabel(filename_letter),
        icon_relative_url=icon_relative_url,
    )
