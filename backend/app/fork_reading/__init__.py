"""The fork reading: one reading of a Student's fork, for three readers (spec #460,
ticket #467).

    reader = ForkReader(github, readings)
    # the stored reading; a fork never read is read now
    reading = reader.read(student)
    # 2 requests if no ref moved; else recomputes the refs that moved
    reading = reader.refresh(student)

See NOTES.md of the rehearsal, in the course repository this engine came from, for the
interface the fork panel and the Eval read.
"""

from .github import GitHub, HttpGitHub, Response, installation_token, static_token
from .reader import ForkReader
from .reading import COMPETENCIES, CompetencyReading, Fact, ForkReading, StudentFork
from .storage import (
    DirectoryReadings,
    GitHubWorkspaceData,
    InMemoryReadings,
    ReadingStore,
    WorkspaceDataReadings,
)

__all__ = [
    "COMPETENCIES",
    "CompetencyReading",
    "DirectoryReadings",
    "Fact",
    "ForkReader",
    "ForkReading",
    "GitHub",
    "GitHubWorkspaceData",
    "HttpGitHub",
    "InMemoryReadings",
    "ReadingStore",
    "Response",
    "StudentFork",
    "WorkspaceDataReadings",
    "installation_token",
    "static_token",
]
