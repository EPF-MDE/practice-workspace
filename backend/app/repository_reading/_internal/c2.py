from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..reading import (
    STUDENT,
    Credit,
    Fact,
    PointId,
)
from .rules import (
    CLEAN_BENCH,
    FALLBACK_CHAIN,
    RUNS_PAGES,
    _date,
)
from .state import _ReadingState


class _C2Facts(_ReadingState):
    def _runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        path: str | None = f"repos/{self.s.evidence_project}/actions/runs?per_page=100"
        for _ in range(RUNS_PAGES):
            if not path:
                break
            r = self.github.get(path)
            if r.status != 200:
                break
            runs.extend(r.body.get("workflow_runs", []))
            path = r.next_page
        return sorted(runs, key=lambda x: x["created_at"], reverse=True)

    def _c2a(self, pull_list: list[dict[str, Any]], runs: list[dict[str, Any]]) -> None:
        for p in sorted(pull_list, key=lambda p: p["number"]):
            until = p.get("closed_at") or "9999"
            mine = sorted(
                (
                    x
                    for x in runs
                    if (
                        x["head_branch"] == p["head"]["ref"]
                        or p["number"]
                        in [q["number"] for q in x.get("pull_requests", [])]
                    )
                    and x["created_at"] <= until
                ),
                key=lambda x: x["created_at"],
            )
            red = next(
                (i for i, x in enumerate(mine) if x["conclusion"] == "failure"), None
            )
            green_after = red is not None and any(
                x["conclusion"] == "success" for x in mine[red + 1 :]
            )
            rerun_green = any(
                x["conclusion"] == "success" and (x.get("run_attempt") or 1) > 1
                for x in mine
            )
            if green_after or rerun_green:
                self.facts["C2"].append(
                    Fact(
                        point=PointId.C2_A,
                        text=f"Pull request #{p['number']} “{p['title']}”: "
                        "its check went red, then green.",
                        link=p.get("html_url"),
                        detail={
                            "pull_request": p["number"],
                            "runs": [x["html_url"] for x in mine],
                        },
                    )
                )

    def _c2b(self, default_sha: str | None) -> None:
        a = self.analyses.get(default_sha) if default_sha else None
        if not a:
            return
        own = {f["path"] for f in a["files"]}
        for path, w in (a.get("workflows") or {}).items():
            if w.get("architecture"):
                self.facts["C2"].append(
                    Fact(
                        point=PointId.C2_B,
                        text="The Architecture Check runs from "
                        f"`{path}` on `{self.default}`.",
                        credited_to=STUDENT
                        if path in own
                        else Credit(a["closest"] or a.get("fallback") or STUDENT),
                        link=f"https://github.com/{self.s.evidence_project}/blob/{self.default}/{path}",
                        detail={"workflow": path},
                    )
                )
                break
        fallback = a.get("fallback")
        if fallback and FALLBACK_CHAIN.index(fallback) >= FALLBACK_CHAIN.index(
            CLEAN_BENCH
        ):
            self.facts["C2"].append(
                Fact(
                    point=PointId.C2_B,
                    text=f"`{self.default}` contains the Clean Bench Fallback Branch "
                    f"(it is built on `{fallback}`).",
                    credited_to=Credit(fallback),
                    detail={"fallback": fallback},
                )
            )

    def _c2c(self, branch_list: list[dict[str, Any]]) -> None:
        r = self.github.get(
            f"repos/{self.s.evidence_project}/rules/branches/"
            f"{quote(self.default, safe='')}"
        )
        rules = r.body if r.status == 200 and isinstance(r.body, list) else []
        checks = sorted(
            {
                c["context"]
                for rule in rules
                if rule.get("type") == "required_status_checks"
                for c in rule.get("parameters", {}).get("required_status_checks", [])
            }
        )
        kinds = sorted({rule["type"] for rule in rules})
        source = "ruleset"
        protected = any(
            b["name"] == self.default and b.get("protected") for b in branch_list
        )
        if not rules and protected:
            b = self.github.get(
                f"repos/{self.s.evidence_project}/branches/"
                f"{quote(self.default, safe='')}"
            )
            protection = (
                (b.body or {}).get("protection") or {} if b.status == 200 else {}
            )
            checks = sorted(
                (protection.get("required_status_checks") or {}).get("contexts") or []
            )
            kinds = ["required_status_checks"] if checks else ["protected"]
            source = "branch protection"
        if not kinds:
            return
        others = [k.replace("_", " ") for k in kinds if k != "required_status_checks"]
        text = f"The {source} on `{self.default}` "
        text += (
            ("requires " + " and ".join(f"`{c}`" for c in checks))
            if checks
            else "requires no check"
        )
        text += f"; other rules: {', '.join(others)}." if others else "."
        self.facts["C2"].append(
            Fact(
                point=PointId.C2_C,
                text=text,
                link=f"https://github.com/{self.s.evidence_project}/settings/rules",
                detail={"source": source, "required_checks": checks, "rules": kinds},
            )
        )

    def _c2d(self, runs: list[dict[str, Any]]) -> None:
        if runs:
            last = runs[0]
            self.facts["C2"].append(self._run_fact("The last run", last))
            on_default = next(
                (x for x in runs if x["head_branch"] == self.default), None
            )
            if on_default and on_default is not last:
                self.facts["C2"].append(
                    self._run_fact(
                        f"The last run on `{self.default}`", on_default, branch=False
                    )
                )
        seen = set()
        for sha, a in self.analyses.items():
            own = {f["path"] for f in a["files"]}
            workflows = dict(a.get("workflows") or {})
            for path in a.get("workflow_files", []):
                if path not in workflows:
                    w = self._workflow(sha, path)
                    if w:
                        workflows[path] = w
                        a.setdefault("workflows_own", {})[path] = w
            workflows.update(a.get("workflows_own") or {})
            for path, w in workflows.items():
                for job, needs in (w.get("deploy_needs") or {}).items():
                    key = (path, job, tuple(needs), path in own)
                    if key in seen:
                        continue
                    seen.add(key)
                    waits = ", ".join(f"`{n}`" for n in needs) or "nothing"
                    self.facts["C2"].append(
                        Fact(
                            point=PointId.C2_D,
                            text=f"In `{path}`, the job `{job}` waits for {waits}.",
                            credited_to=STUDENT
                            if path in own
                            else Credit(a["closest"] or STUDENT),
                            detail={
                                "workflow": path,
                                "job": job,
                                "needs": needs,
                                "waits_for_test": any("test" in n for n in needs),
                            },
                        )
                    )

    def _run_fact(self, label: str, run: dict[str, Any], branch: bool = True) -> Fact:
        conclusion = run.get("conclusion") or run.get("status")
        where = f" on `{run['head_branch']}`" if branch else ""
        return Fact(
            point=PointId.C2_D,
            text=f"{label}, “{run['name']}”{where}, "
            f"ended {conclusion} on {_date(run['created_at'])}.",
            link=run.get("html_url"),
            detail={
                "run": run["id"],
                "branch": run["head_branch"],
                "conclusion": conclusion,
                "date": _date(run["created_at"]),
            },
        )

    def _deployments(self) -> dict[str, dict[str, Any]]:
        r = self.github.get(f"repos/{self.s.evidence_project}/deployments?per_page=100")
        found = r.body if r.status == 200 and isinstance(r.body, list) else []
        latest: dict[str, dict[str, Any]] = {}
        for d in found:
            env = d.get("environment", "").lower()
            kind = (
                "production" if "prod" in env else "staging" if "stag" in env else None
            )
            if kind:
                latest.setdefault(kind, d)
        return latest

    def _c2e(self, deployments: dict[str, dict[str, Any]]) -> None:
        for kind in ("staging", "production"):
            d = deployments.get(kind)
            if not d:
                continue
            r = self.github.get(
                f"repos/{self.s.evidence_project}/deployments/{d['id']}/statuses?per_page=1"
            )
            status = r.body[0] if r.status == 200 and r.body else {}
            state = status.get("state", "unknown")
            self.facts["C2"].append(
                Fact(
                    point=PointId.C2_E,
                    text=f"The last deployment to {kind}, "
                    f"on {_date(d['created_at'])}, "
                    f"runs commit `{d['sha'][:7]}` ({state}).",
                    link=f"https://github.com/{self.s.evidence_project}/commit/{d['sha']}",
                    detail={
                        "environment": d["environment"],
                        "sha": d["sha"],
                        "date": _date(d["created_at"]),
                        "state": state,
                        "url": status.get("environment_url"),
                    },
                )
            )
