# A Path greys the Steps ahead, and never locks them

A Student follows a Path in order, but must be free to read ahead or come back. **So the Steps more than one past the first unfinished one are greyed, never locked, and an optional Step is never waited for.**

- `finishedSteps` in `frontend/src/practice/progress.ts`: a Step is finished once its answer or drawing is sent; a reading Step once the Student says they read it, or once they sent a later Step that is not optional.
- `greyedSteps` in the same file greys the Steps more than one past the first unfinished Step that is not optional, and nothing else.
