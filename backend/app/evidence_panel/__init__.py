"""The Evidence panel and the Evidence Project declarations (spec #460, ticket #468).

    # facts per point, never a Band, from the declared Evidence Project or the roster's
    panel = read_panel("C2", source, student, declaration)
    # what the closing step stores
    snapshot(panel)
    # GitHub or GitLab, else NotAProject
    project = parse_project(url)
    # readable, "not readable yet", or GitLab's instruction
    access(project, evidence_project, check, app_slug)

The reading comes from a `RepositoryReadingSource`: the Repository reading (#467) in
production, `OfflineRepositoryReading` locally and in tests. The access check is an
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
    snapshot,
)
from .source import (
    LazyRepositoryReadingSource,
    OfflineRepositoryReading,
    RepositoryReadingSource,
    read_panel,
)

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
    "RepositoryReadingSource",
    "LazyRepositoryReadingSource",
    "NotAProject",
    "NotVisible",
    "OfflineRepositoryReading",
    "PanelFact",
    "Project",
    "access",
    "parse_project",
    "read_panel",
    "snapshot",
]
