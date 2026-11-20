"""The evidence panel and the Evidence Project declarations (spec #460, ticket #468).

    # facts per point, never a Band
    panel = build_panel("C2", reading, declaration)
    # what the closing step stores
    snapshot(panel)
    # GitHub or GitLab, else NotAProject
    project = parse_project(url)
    # readable, "not readable yet", or GitLab's instruction
    access(project, repository, check, app_slug)

The reading comes from a `ReadingSource`: the Repository reading (#467) in production,
`OfflineRepositoryReading` locally and in tests. The access check is an
`AccessCheck`: `AppAccessCheck` (the Student Connector App) or `FakeAccessCheck`.
"""

from .access import (
    AccessCheck,
    AppAccessCheck,
    FakeAccessCheck,
    NotAProject,
    Project,
    access,
    parse_project,
)
from .panel import (
    DOCUMENTATION_ADVICE,
    NOTICE,
    PASSWORD_EXAMPLE,
    Access,
    Declaration,
    DeclarationHelp,
    EvidencePanel,
    NotVisible,
    PanelFact,
    build_panel,
    snapshot,
    unavailable_panel,
)
from .source import LazyReadingSource, OfflineRepositoryReading, ReadingSource

__all__ = [
    "DOCUMENTATION_ADVICE",
    "NOTICE",
    "PASSWORD_EXAMPLE",
    "Access",
    "AccessCheck",
    "AppAccessCheck",
    "Declaration",
    "DeclarationHelp",
    "FakeAccessCheck",
    "EvidencePanel",
    "ReadingSource",
    "LazyReadingSource",
    "NotAProject",
    "NotVisible",
    "OfflineRepositoryReading",
    "PanelFact",
    "Project",
    "access",
    "build_panel",
    "parse_project",
    "snapshot",
    "unavailable_panel",
]
