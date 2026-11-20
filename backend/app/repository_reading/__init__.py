"""The Repository reading: one reading of a Student's repository, for three readers
(spec #460, ticket #467).

    reader = RepositoryReader(github, readings)
    # the stored reading; a repository never read is read now
    reading = reader.read(student)
    # 2 requests if no ref moved; else recomputes the refs that moved
    reading = reader.refresh(student)

See NOTES.md of the rehearsal, in the course repository this engine came from, for the
interface the Evidence panel and the Eval read.
"""

from .github import (
    GitHub,
    HttpGitHub,
    Response,
    installation_token,
    repository_tokens,
    static_token,
)
from .reader import RepositoryReader
from .reading import (
    COMPETENCIES,
    CompetencyReading,
    Fact,
    RepositoryReading,
    StudentToRead,
)
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
    "RepositoryReader",
    "RepositoryReading",
    "GitHub",
    "GitHubWorkspaceData",
    "HttpGitHub",
    "InMemoryReadings",
    "ReadingStore",
    "Response",
    "StudentToRead",
    "WorkspaceDataReadings",
    "installation_token",
    "repository_tokens",
    "static_token",
]
