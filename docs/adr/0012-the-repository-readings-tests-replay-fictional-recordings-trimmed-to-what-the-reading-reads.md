# The Repository reading's tests replay fictional recordings, trimmed to what the reading reads

The Repository reading is tested on recorded GitHub responses, replayed so the tests can also count the reading's requests. A recording of a real Evidence Project holds that Student's login, email, branches, commits and code, and this repository is public. **So only fictional recordings go in `backend/tests/repository_reading/fixtures/`: shaped on real repositories, their shapes, dates and counts kept, with logins, branches, pull requests, commits and code invented; and every recording is trimmed to the fields the reading reads.**

- **`backend/tests/repository_reading/record.py` records a real repository for study**, with read-only requests, and writes a trimmed fixture. Its output is not committed until it is made fictional.
