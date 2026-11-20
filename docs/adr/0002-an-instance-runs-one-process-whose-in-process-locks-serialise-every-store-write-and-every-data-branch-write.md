# An Instance runs one process, whose in-process locks serialise every Store write and every data branch write

A Send's version is counted from the entries already stored, and a writer that reads the data branch's tip, builds a commit and moves the ref loses another writer's commit if both do it at once. **So an Instance runs one process (`uvicorn app.main:app`, one worker) holding one Store, and that process serialises its writes with in-process locks: one per Student for their Sends, and one per data branch, which every writer of that branch takes.** A drawing's files and the Repository reading's stored readings both go to the data branch, so they share that lock.

- **Scaling out means moving the locks first.** Two workers would each hold their own locks and their own copy of a record: versions would collide, and one would not see the other's Sends.
- **Writers outside the process meet a retry, not the lock.** The Repository reading's batch and the Instructor by hand also move the data branch, so a write GitHub refuses as stale reads the branch again and retries a few times before failing.
- **Each Student has one stored reading**, of the Evidence Project read last, on the data branch. A refresh that finds no change writes nothing, so it makes no commit.
