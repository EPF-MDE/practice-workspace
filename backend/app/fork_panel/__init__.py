"""The fork panel and the Evidence Project declarations (spec #460, ticket #468).

    # facts per point, never a Band
    panel = build_panel("C2", reading, declaration)
    # what the closing step stores
    snapshot(panel)
    # GitHub or GitLab, else NotAProject
    project = parse_project(url)
    # readable, "not readable yet", or GitLab's instruction
    access(project, fork, check, app_slug)

The reading comes from a `ForkSource`: the fork reading (#467) in production,
`OfflineForkReading` locally and in tests. The access check is an
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
    ForkPanel,
    NotVisible,
    PanelFact,
    build_panel,
    snapshot,
    unavailable_panel,
)
from .source import ForkSource, LazyForkSource, OfflineForkReading

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
    "ForkPanel",
    "ForkSource",
    "LazyForkSource",
    "NotAProject",
    "NotVisible",
    "OfflineForkReading",
    "PanelFact",
    "Project",
    "access",
    "build_panel",
    "parse_project",
    "snapshot",
    "unavailable_panel",
]
