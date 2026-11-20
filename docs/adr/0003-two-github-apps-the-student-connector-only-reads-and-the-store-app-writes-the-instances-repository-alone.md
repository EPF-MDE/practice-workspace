# Two GitHub Apps: the Student Connector only reads, and the Store App writes the Instance's repository alone

An Instance signs Students in with GitHub, reads their Evidence Projects, some of them private, and writes its Store to the Course's repository. One GitHub App doing all three would hold write access to the Course's repository on behalf of every sign-in, and the Repository reading must never change a Student's repository. **So each Instance uses two GitHub Apps: the Student Connector (the `github_app_*` settings), for "Sign in with GitHub" and read-only access to Students' repositories, and the Store App (the `store_app_*` settings), with Issues and Contents write on the Instance's repository alone.** The Store, the Roster and the data branch are reached only with the Store App's installation.

- **The Repository reading's GitHub seam only reads**: it has one method, `get`.
- **A Student makes a private repository readable by installing the Student Connector on it**; a public repository is readable by any installation.
