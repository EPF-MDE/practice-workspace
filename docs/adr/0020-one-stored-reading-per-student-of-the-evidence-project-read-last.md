# One stored reading per Student, of the Evidence Project read last

A Repository reading is plain data: the batch writes it, a refresh replaces it, and the Evidence panel serves it. A Student may change their Evidence Project until the Reading Day, and a refresh with no change happens far more often than one with a change. **So each Student has one stored reading, as JSON in `repository-readings/<login>.json` on the data branch, of the Evidence Project read last; it names the repository it read, and it is served only while that is still the Student's Evidence Project.**

- `RepositoryReading.to_dict` and `RepositoryReading.from_dict` in `backend/app/repository_reading/reading.py` are the stored form. `ReadingStore` in `backend/app/repository_reading/storage.py` is the seam, with three adapters: `InMemoryReadings` for tests and local runs, `DirectoryReadings` for a local folder, and `WorkspaceDataReadings` for the data branch.
- `RepositoryReader._stored` returns no reading when the stored one reads another Evidence Project (`RepositoryReading.reads`), so a change of Evidence Project is read afresh rather than served stale.
- `StudentToRead.key` compares repositories without case, because GitHub names a repository without case: `Owner/Repo` and `owner/repo` are one Evidence Project.
- `ReadingStore.save(..., changed=False)` means only the time of the check moved: `WorkspaceDataReadings` keeps it in memory and writes nothing to GitHub, so a refresh with no change makes no commit.
- `run_batch` in `backend/app/repository_reading/batch.py` reads every repository, then writes one file per Student in a single commit.
