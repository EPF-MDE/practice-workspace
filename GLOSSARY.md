# Practice workspace

The engine a course runs so that each Student practises its Competencies on their own, one Path at a time, and then sits its Eval on the same kind of Path. This glossary holds the engine's language only. A course's own words stay in that course's glossary, which points here.

## Language

### The engine and its courses

**Practice workspace**: The space, signed into with GitHub, where each Student follows a Path per Competency on their own, for their Practice and then for their Eval. It is one public engine, and each course that uses it runs its own Instance with its own Course folder (ADR-0001). _Avoid_: platform, portal, app

**Engine**: This repository: the code of the Practice workspace, which holds no course. It knows a course only through the Course folder it is given at start. _Avoid_: core, framework

**Instance**: One course's running Practice workspace: a released version of the Engine, that course's Course folder, and its own apps, secrets and Store. _Avoid_: deployment, tenant

**Course**: A taught course that runs an Instance. Its material and what it says of its Students stay in its own repository, never here. _Avoid_: class, module

**Course folder**: Everything a Course gives the Engine: its settings, its content (one Markdown file per Competency) and its drawings. The Engine reads it at start and refuses to start on one that is incomplete or inconsistent. _Avoid_: course config, content directory

**Demo course**: The fictional Course folder shipped with the Engine, for its own tests and its README. No real Course, Student or answer is in it.

**Software Factory**: The agent runs that work on the Engine's own issues and pull requests: GitHub Actions workflows that a label starts, each running an agent script in `.sandcastle/`. It implements and reviews; the Instructor merges. _Avoid_: bot, pipeline

### People

**Student**: Someone on a Course's Roster, who follows the Paths. _Avoid_: user, learner

**Instructor**: The person who writes a Course's material and reads what its Students send. _Avoid_: teacher, admin

**Roster**: The list of a Course's Students, keyed by their numeric GitHub id, naming each Student's Group and their Evidence Project. Sign-in is checked against it. _Avoid_: class list, whitelist

**Group**: The Students of a Course who receive the same Group-specific content, named once in the Course folder's settings. _Avoid_: class, cohort, team

**Group block**: The part of a Step only one Group's Students see, opened in the content by the block id the Course folder's settings give that Group. A Step with one Group's block has one for every Group. _Avoid_: variant

**Upstream repository**: The repository a Group's Students start their Evidence Project from, if the Course folder's settings name one. The Repository reading credits the code of its course branches to those branches, not to the Student. _Avoid_: template

### What a Student follows

**Competency**: One capability a Course assesses independently. Every Course has the same three, C1, C2 and C3, in that order: the Engine's fixed set, not a setting. The Course folder gives each its title and the minutes its Path is given, in its settings, and its content in one Markdown file. _Avoid_: skill, criterion, learning outcome

**Path**: The steps one Student follows through one Competency: material to read, fields to fill, systems to redraw and Checks, the Instructor's answer to a step showing only once the Student's own is stored. The Practice and the Eval follow the same kind of Path and differ only in how it ends. _Avoid_: journey, course, parcours

**Step**: One position on a Path, with what it gives the Student to read and what it asks them to send. _Avoid_: page, lesson

**Locked answer**: The Instructor's answer to a Step, withheld by the server until the Student's own answer to that Step is stored: hiding it in the browser would still send it. A Step that waits for an earlier Step's answer is withheld the same way. _Avoid_: solution, hidden answer

**Check**: A question with a few choices, set on the material a Student has just read, corrected and explained once they send it. It tells a Student whether they understood; it is not graded, and it is not their Self-assessment. _Avoid_: quiz, test, exercise

**Practice**: A Student's Paths through a Course's Competencies before the Eval, each ending on their Self-assessment and Evidence Plan. It is not graded. _Avoid_: review, revision, training

**Eval**: The Path a Student follows at the end of a Course, where they answer the Instructor's questions on each Competency, one at a time, with concrete examples from their Evidence Project. _Avoid_: exam, oral, test

### What a Student sends

**Send**: One thing a Student stores: an answer, a drawing, a Self-assessment, an Evidence Plan, a declaration or a question. A Send never rewrites an earlier one. _Avoid_: save, submission

**Self-assessment**: For one Student and each Competency, where they stand on each point its Path says they can explain, on the levels the Course folder sets. It is not graded, the Instructor sees it, and the Evidence Plan is drafted from it. _Avoid_: self-evaluation, quiz

**Scale**: The levels a Self-assessment rates each point on, in order, each with an id and a label, listed in the Course folder's settings. Its last is the **top level**, the one that says a point is done: a point rated at it needs a link to the work, and the Evidence Plan leaves it out. A content's _to get there_ is written for a level below the top. _Avoid_: grade, rubric

**Evidence Plan**: For one Student and each Competency, for each point of their Self-assessment not yet done, the evidence they will put in their Evidence Project before the Reading Day, and what to do to get there. The Practice workspace drafts it from their Self-assessment and the Student amends it until the Reading Day. _Avoid_: Practice Plan, roadmap

**Evidence Project**: The one repository a Student puts their evidence in, for every Competency: by default the one the Roster names for them, which they may change for another until the Reading Day. _Avoid_: default repository, fork, portfolio, project

**Repository reading**: What the Practice workspace reads of a Student's Evidence Project, to show the Student and the Instructor where it stands for each Competency. It never changes what a Path shows. _Avoid_: fork reading, scan

**Evidence panel**: For one Student and each Competency, shown beside their Path and at its closing step: what the Repository reading finds on their Evidence Project, as the Roster names it or as the Student changed it. It shows facts, each naming the point it supports, never a grade; when it could not read the Evidence Project, it says why, and that it is not a zero. What it showed at the closing step is kept with their Evidence Plan. _Avoid_: fork panel

**Credit**: Whose work a fact of the Evidence panel shows: the Student's own, or the code of a Course's branch that their Evidence Project is built on, named by that branch.

### Time

**Close**: The instant a Course's Practice stops taking new answers, set in the Instance's settings. After it and until the Reading Day, a Self-assessment level only moves up to the top level of the Course's Scale, with a link to the work, so the Self-assessment cannot be rewritten to look better than the Practice was; the Evidence Plan and Evidence Project stay editable. _Avoid_: deadline, cut-off

**Reading Day**: The instant from which the Instructor reads each Student's Evidence Project, set in the Instance's settings. Nothing sent after it is read. _Avoid_: deadline, freeze

### Where it is kept

**Store**: Where every Send is kept, with every version, as dated entries: a Student's current state is the latest entry of each kind. It speaks the domain, never its backend, and checks no rule: its callers decide what may be sent, and when; an Instance sets which repository, label and data branch hold it. _Avoid_: database, persistence, storage
