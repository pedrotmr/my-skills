#!/usr/bin/env python3
"""Normalize PR review, CI, and mergeability state for ultra-babysit-pr."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


FAILED_RUN_CONCLUSIONS = {
    "failure",
    "timed_out",
    "cancelled",
    "action_required",
    "startup_failure",
    "stale",
}
PENDING_CHECK_STATES = {
    "QUEUED",
    "IN_PROGRESS",
    "PENDING",
    "WAITING",
    "REQUESTED",
}
REVIEW_BOT_LOGIN_KEYWORDS = {
    "bugbot",
    "claude",
    "codex",
    "copilot",
    "coderabbit",
    "cursor",
    "gemini",
    "sonar",
    "sweep",
}
TRUSTED_AUTHOR_ASSOCIATIONS = {
    "OWNER",
    "MEMBER",
    "COLLABORATOR",
}
MERGE_BLOCKING_REVIEW_DECISIONS = {
    "REVIEW_REQUIRED",
    "CHANGES_REQUESTED",
}
MERGE_CONFLICT_OR_BLOCKING_STATES = {
    "BLOCKED",
    "DIRTY",
    "DRAFT",
    "UNKNOWN",
}


class GhCommandError(RuntimeError):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Watch PR review threads, comments, CI, flaky retries, and mergeability."
    )
    parser.add_argument("--pr", default="auto", help="auto, PR number, or PR URL")
    parser.add_argument("--repo", help="Optional OWNER/REPO override")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-flaky-retries", type=int, default=3)
    parser.add_argument("--state-file", help="Path to watcher state JSON")
    parser.add_argument("--once", action="store_true", help="Emit one JSON snapshot")
    parser.add_argument("--watch", action="store_true", help="Continuously emit JSONL snapshots")
    parser.add_argument(
        "--retry-failed-now",
        action="store_true",
        help="Rerun failed workflow jobs when the retry policy allows it",
    )
    parser.add_argument(
        "--mark-handled",
        nargs="+",
        metavar="ITEM_ID",
        help="Remove handled review items from the pending queue",
    )
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be > 0")
    if args.max_flaky_retries < 0:
        parser.error("--max-flaky-retries must be >= 0")
    exclusive = [args.once, args.watch, args.retry_failed_now, bool(args.mark_handled)]
    if sum(1 for flag in exclusive if flag) > 1:
        parser.error("choose only one of --once, --watch, --retry-failed-now, --mark-handled")
    if not any(exclusive):
        args.once = True
    return args


def gh_text(args, repo=None):
    cmd = ["gh"]
    if repo and (not args or args[0] != "api"):
        cmd.extend(["-R", repo])
    cmd.extend(args)
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as err:
        raise GhCommandError("`gh` command not found") from err
    except subprocess.CalledProcessError as err:
        stdout = (err.stdout or "").strip()
        stderr = (err.stderr or "").strip()
        detail = "\n".join(part for part in (stdout, stderr) if part)
        raise GhCommandError(f"GitHub CLI command failed: {' '.join(cmd)}\n{detail}") from err
    return proc.stdout


def gh_json(args, repo=None):
    raw = gh_text(args, repo=repo).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise GhCommandError(f"Failed to parse JSON from gh output for {' '.join(args)}") from err


def parse_pr_spec(pr_spec):
    if pr_spec == "auto":
        return {"mode": "auto", "value": None}
    if re.fullmatch(r"\d+", pr_spec):
        return {"mode": "number", "value": pr_spec}
    parsed = urlparse(pr_spec)
    if parsed.scheme and parsed.netloc and "/pull/" in parsed.path:
        return {"mode": "url", "value": pr_spec}
    raise ValueError("--pr must be 'auto', a PR number, or a PR URL")


def extract_repo_from_pr_url(pr_url):
    parsed = urlparse(pr_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 4 and parts[2] == "pull":
        return f"{parts[0]}/{parts[1]}"
    return None


def extract_repo_from_pr_view(data):
    head_repo = data.get("headRepository")
    head_owner = data.get("headRepositoryOwner")
    owner = None
    name = None
    if isinstance(head_owner, dict):
        owner = head_owner.get("login") or head_owner.get("name")
    elif isinstance(head_owner, str):
        owner = head_owner
    if isinstance(head_repo, dict):
        name = head_repo.get("name")
        repo_owner = head_repo.get("owner")
        if not owner and isinstance(repo_owner, dict):
            owner = repo_owner.get("login") or repo_owner.get("name")
    elif isinstance(head_repo, str):
        name = head_repo
    if owner and name:
        return f"{owner}/{name}"
    return None


def resolve_pr(pr_spec, repo_override=None):
    fields = (
        "number,url,state,mergedAt,closedAt,headRefName,headRefOid,"
        "headRepository,headRepositoryOwner,mergeable,mergeStateStatus,reviewDecision"
    )
    parsed = parse_pr_spec(pr_spec)
    cmd = ["pr", "view"]
    if parsed["value"] is not None:
        cmd.append(parsed["value"])
    cmd.extend(["--json", fields])
    data = gh_json(cmd, repo=repo_override)
    if not isinstance(data, dict):
        raise GhCommandError("Unexpected PR payload from `gh pr view`")
    pr_url = str(data.get("url") or "")
    repo = repo_override or extract_repo_from_pr_url(pr_url) or extract_repo_from_pr_view(data)
    if not repo:
        raise GhCommandError("Unable to determine OWNER/REPO for the PR")
    state = str(data.get("state") or "")
    return {
        "number": int(data["number"]),
        "url": pr_url,
        "repo": repo,
        "head_sha": str(data.get("headRefOid") or ""),
        "head_branch": str(data.get("headRefName") or ""),
        "state": state,
        "merged": bool(data.get("mergedAt")),
        "closed": bool(data.get("closedAt")) or state.upper() == "CLOSED",
        "mergeable": str(data.get("mergeable") or ""),
        "merge_state_status": str(data.get("mergeStateStatus") or ""),
        "review_decision": str(data.get("reviewDecision") or ""),
    }


def default_state_file_for(pr):
    repo_slug = pr["repo"].replace("/", "-")
    return Path(f"/tmp/codex-ultra-babysit-pr-{repo_slug}-pr{pr['number']}.json")


def load_state(path):
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as err:
            raise RuntimeError(f"State file is not valid JSON: {path}") from err
        if not isinstance(data, dict):
            raise RuntimeError(f"State file must contain an object: {path}")
    else:
        data = {}
    data.setdefault("started_at", None)
    data.setdefault("last_seen_head_sha", None)
    data.setdefault("retries_by_sha", {})
    data.setdefault("handled_review_item_ids", [])
    data.setdefault("pending_review_items", [])
    data.setdefault("last_snapshot_at", None)
    return data


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def get_authenticated_login():
    data = gh_json(["api", "user"])
    if not isinstance(data, dict) or not data.get("login"):
        raise GhCommandError("Unable to determine authenticated GitHub login")
    return str(data["login"])


def gh_api_list_paginated(endpoint, repo=None, per_page=100):
    items = []
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        payload = gh_json(["api", f"{endpoint}{sep}per_page={per_page}&page={page}"], repo=repo)
        if payload is None:
            break
        if not isinstance(payload, list):
            raise GhCommandError(f"Unexpected paginated payload from gh api {endpoint}")
        items.extend(payload)
        if len(payload) < per_page:
            break
        page += 1
    return items


def extract_login(user_obj):
    if isinstance(user_obj, dict):
        return str(user_obj.get("login") or "")
    return ""


def is_bot_login(login):
    return bool(login) and login.endswith("[bot]")


def is_supported_review_bot(login):
    lower = login.lower()
    return is_bot_login(login) and any(keyword in lower for keyword in REVIEW_BOT_LOGIN_KEYWORDS)


def is_trusted_human(item, authenticated_login):
    author = str(item.get("author") or "")
    if not author:
        return False
    if authenticated_login and author == authenticated_login:
        return True
    return str(item.get("author_association") or "").upper() in TRUSTED_AUTHOR_ASSOCIATIONS


def should_surface_review_item(item, authenticated_login):
    author = str(item.get("author") or "")
    if not author:
        return False
    if is_bot_login(author):
        return is_supported_review_bot(author)
    return is_trusted_human(item, authenticated_login)


def normalize_issue_comment(item):
    return {
        "id": f"issue_comment:{item.get('id')}",
        "kind": "issue_comment",
        "author": extract_login(item.get("user")),
        "author_association": str(item.get("author_association") or ""),
        "created_at": str(item.get("created_at") or ""),
        "body": str(item.get("body") or ""),
        "path": None,
        "line": None,
        "url": str(item.get("html_url") or ""),
        "thread_id": None,
        "comment_id": str(item.get("id") or ""),
        "is_resolved": None,
        "is_outdated": None,
    }


def normalize_review_submission(item):
    return {
        "id": f"review:{item.get('id')}",
        "kind": "review",
        "author": extract_login(item.get("user")),
        "author_association": str(item.get("author_association") or ""),
        "created_at": str(item.get("submitted_at") or item.get("created_at") or ""),
        "body": str(item.get("body") or ""),
        "path": None,
        "line": None,
        "url": str(item.get("html_url") or ""),
        "thread_id": None,
        "comment_id": str(item.get("id") or ""),
        "is_resolved": None,
        "is_outdated": None,
    }


def fetch_unresolved_review_threads(repo, pr_number):
    owner, name = repo.split("/", 1)
    query = """
      query($owner:String!,$repo:String!,$number:Int!){
        repository(owner:$owner,name:$repo){
          pullRequest(number:$number){
            reviewThreads(first:100){
              nodes{
                id
                isResolved
                isOutdated
                comments(first:50){
                  nodes{
                    databaseId
                    body
                    path
                    line
                    url
                    createdAt
                    author{login}
                    authorAssociation
                  }
                }
              }
            }
          }
        }
      }
    """
    data = gh_json(
        ["api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"repo={name}", "-F", f"number={pr_number}"],
        repo=repo,
    )
    nodes = (
        (((data or {}).get("data") or {}).get("repository") or {})
        .get("pullRequest", {})
        .get("reviewThreads", {})
        .get("nodes", [])
    )
    out = []
    for thread in nodes or []:
        if not isinstance(thread, dict):
            continue
        if thread.get("isResolved") or thread.get("isOutdated"):
            continue
        comments = (((thread.get("comments") or {}).get("nodes")) or [])
        if not comments:
            continue
        first = comments[0] if isinstance(comments[0], dict) else {}
        last = comments[-1] if isinstance(comments[-1], dict) else first
        comment_id = str(last.get("databaseId") or first.get("databaseId") or "")
        out.append(
            {
                "id": f"review_thread:{thread.get('id')}",
                "kind": "review_thread",
                "author": str((last.get("author") or {}).get("login") or ""),
                "author_association": str(last.get("authorAssociation") or ""),
                "created_at": str(last.get("createdAt") or ""),
                "body": str(last.get("body") or ""),
                "path": last.get("path"),
                "line": last.get("line"),
                "url": str(last.get("url") or ""),
                "thread_id": str(thread.get("id") or ""),
                "comment_id": comment_id,
                "is_resolved": bool(thread.get("isResolved")),
                "is_outdated": bool(thread.get("isOutdated")),
            }
        )
    return out


def fetch_review_activity(pr, authenticated_login):
    repo = pr["repo"]
    pr_number = pr["number"]
    issue_comments = gh_api_list_paginated(f"repos/{repo}/issues/{pr_number}/comments", repo=repo)
    review_submissions = gh_api_list_paginated(f"repos/{repo}/pulls/{pr_number}/reviews", repo=repo)
    items = [normalize_issue_comment(item) for item in issue_comments if isinstance(item, dict)]
    items += [normalize_review_submission(item) for item in review_submissions if isinstance(item, dict)]
    items += fetch_unresolved_review_threads(repo, pr_number)
    filtered = [item for item in items if should_surface_review_item(item, authenticated_login)]
    filtered.sort(key=lambda item: (item.get("created_at") or "", item.get("kind") or "", item.get("id") or ""))
    return filtered


def merge_pending_review_items(state, current_items):
    handled = {str(item_id) for item_id in state.get("handled_review_item_ids") or []}
    existing = {
        str(item.get("id")): item
        for item in state.get("pending_review_items") or []
        if isinstance(item, dict) and item.get("id") not in handled
    }
    current_ids = set()
    for item in current_items:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in handled:
            continue
        current_ids.add(item_id)
        existing[item_id] = item

    pending = []
    for item_id, item in existing.items():
        # Review threads disappear from the pending queue once GitHub reports
        # them resolved or outdated. Issue comments and review summaries stay
        # pending until --mark-handled records an explicit decision.
        if item.get("kind") == "review_thread" and item_id not in current_ids:
            continue
        pending.append(item)
    pending.sort(key=lambda item: (item.get("created_at") or "", item.get("kind") or "", item.get("id") or ""))
    state["pending_review_items"] = pending
    return pending


def get_pr_checks(pr_spec, repo):
    parsed = parse_pr_spec(pr_spec)
    cmd = ["pr", "checks"]
    if parsed["value"] is not None:
        cmd.append(parsed["value"])
    cmd.extend(["--json", "name,state,bucket,link,workflow,event,startedAt,completedAt"])
    data = gh_json(cmd, repo=repo)
    if data is None:
        return []
    if not isinstance(data, list):
        raise GhCommandError("Unexpected payload from `gh pr checks`")
    return data


def summarize_checks(checks):
    pending = 0
    failed = 0
    passed = 0
    for check in checks:
        bucket = str(check.get("bucket") or "").lower()
        state = str(check.get("state") or "").upper()
        if bucket == "pending" or state in PENDING_CHECK_STATES:
            pending += 1
        if bucket == "fail":
            failed += 1
        if bucket == "pass":
            passed += 1
    return {
        "pending_count": pending,
        "failed_count": failed,
        "passed_count": passed,
        "all_terminal": pending == 0,
    }


def get_workflow_runs_for_sha(repo, head_sha):
    data = gh_json(["api", f"repos/{repo}/actions/runs", "-X", "GET", "-f", f"head_sha={head_sha}", "-f", "per_page=100"], repo=repo)
    if not isinstance(data, dict):
        raise GhCommandError("Unexpected payload from actions runs API")
    runs = data.get("workflow_runs") or []
    if not isinstance(runs, list):
        raise GhCommandError("Expected `workflow_runs` to be a list")
    return runs


def failed_runs_from_workflow_runs(runs, head_sha):
    out = []
    for run in runs:
        if not isinstance(run, dict) or str(run.get("head_sha") or "") != head_sha:
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion in FAILED_RUN_CONCLUSIONS:
            out.append(
                {
                    "run_id": run.get("id"),
                    "workflow_name": run.get("name") or run.get("display_title") or "",
                    "status": str(run.get("status") or ""),
                    "conclusion": conclusion,
                    "html_url": str(run.get("html_url") or ""),
                }
            )
    out.sort(key=lambda item: (str(item.get("workflow_name") or ""), str(item.get("run_id") or "")))
    return out


def get_jobs_for_run(repo, run_id):
    data = gh_json(["api", f"repos/{repo}/actions/runs/{run_id}/jobs", "-X", "GET", "-f", "per_page=100"], repo=repo)
    if not isinstance(data, dict):
        raise GhCommandError("Unexpected payload from actions run jobs API")
    jobs = data.get("jobs") or []
    if not isinstance(jobs, list):
        raise GhCommandError("Expected `jobs` to be a list")
    return jobs


def failed_jobs_from_workflow_runs(repo, runs, head_sha):
    out = []
    for run in runs:
        if not isinstance(run, dict) or str(run.get("head_sha") or "") != head_sha:
            continue
        run_id = run.get("id")
        if run_id in (None, ""):
            continue
        run_status = str(run.get("status") or "")
        run_conclusion = str(run.get("conclusion") or "")
        if run_status.lower() == "completed" and run_conclusion not in FAILED_RUN_CONCLUSIONS:
            continue
        for job in get_jobs_for_run(repo, run_id):
            if not isinstance(job, dict):
                continue
            conclusion = str(job.get("conclusion") or "")
            if conclusion not in FAILED_RUN_CONCLUSIONS:
                continue
            job_id = job.get("id")
            out.append(
                {
                    "run_id": run_id,
                    "workflow_name": run.get("name") or run.get("display_title") or "",
                    "run_status": run_status,
                    "run_conclusion": run_conclusion,
                    "job_id": job_id,
                    "job_name": str(job.get("name") or ""),
                    "status": str(job.get("status") or ""),
                    "conclusion": conclusion,
                    "html_url": str(job.get("html_url") or ""),
                    "logs_endpoint": f"repos/{repo}/actions/jobs/{job_id}/logs" if job_id not in (None, "") else None,
                }
            )
    out.sort(key=lambda item: (str(item.get("workflow_name") or ""), str(item.get("job_name") or ""), str(item.get("job_id") or "")))
    return out


def current_retry_count(state, head_sha):
    try:
        return int((state.get("retries_by_sha") or {}).get(head_sha, 0))
    except (TypeError, ValueError):
        return 0


def set_retry_count(state, head_sha, count):
    retries = state.get("retries_by_sha")
    if not isinstance(retries, dict):
        retries = {}
    retries[head_sha] = int(count)
    state["retries_by_sha"] = retries


def is_pr_ready_to_merge(pr, checks_summary, pending_review_items):
    if pr["closed"] or pr["merged"]:
        return False
    if pending_review_items:
        return False
    if not checks_summary["all_terminal"] or checks_summary["failed_count"] > 0 or checks_summary["pending_count"] > 0:
        return False
    if str(pr.get("mergeable") or "") != "MERGEABLE":
        return False
    if str(pr.get("merge_state_status") or "") in MERGE_CONFLICT_OR_BLOCKING_STATES:
        return False
    if str(pr.get("review_decision") or "") in MERGE_BLOCKING_REVIEW_DECISIONS:
        return False
    return True


def unique_actions(actions):
    out = []
    seen = set()
    for action in actions:
        if action not in seen:
            out.append(action)
            seen.add(action)
    return out


def recommend_actions(pr, checks_summary, failed_runs, failed_jobs, pending_review_items, retries_used, max_retries):
    actions = []
    if pr["closed"] or pr["merged"]:
        actions.append("stop_pr_closed")
        return actions
    if pending_review_items:
        actions.append("process_review_items")
    has_failed_checks = checks_summary["failed_count"] > 0 or bool(failed_jobs)
    if has_failed_checks:
        if checks_summary["all_terminal"] and retries_used >= max_retries:
            actions.append("stop_exhausted_retries")
        else:
            actions.append("diagnose_ci_failure")
            if checks_summary["all_terminal"] and failed_runs and retries_used < max_retries:
                actions.append("retry_failed_checks")
    if is_pr_ready_to_merge(pr, checks_summary, pending_review_items):
        actions.append("ready_to_merge")
    if not actions:
        actions.append("idle")
    return unique_actions(actions)


def collect_snapshot(args):
    pr = resolve_pr(args.pr, repo_override=args.repo)
    state_path = Path(args.state_file) if args.state_file else default_state_file_for(pr)
    state = load_state(state_path)
    if not state.get("started_at"):
        state["started_at"] = int(time.time())

    authenticated_login = get_authenticated_login()
    current_review_items = fetch_review_activity(pr, authenticated_login)
    pending_review_items = merge_pending_review_items(state, current_review_items)
    checks = get_pr_checks(str(pr["number"]), repo=pr["repo"])
    checks_summary = summarize_checks(checks)
    workflow_runs = get_workflow_runs_for_sha(pr["repo"], pr["head_sha"])
    failed_runs = failed_runs_from_workflow_runs(workflow_runs, pr["head_sha"])
    failed_jobs = failed_jobs_from_workflow_runs(pr["repo"], workflow_runs, pr["head_sha"])
    retries_used = current_retry_count(state, pr["head_sha"])
    actions = recommend_actions(
        pr,
        checks_summary,
        failed_runs,
        failed_jobs,
        pending_review_items,
        retries_used,
        args.max_flaky_retries,
    )

    state["pr"] = {"repo": pr["repo"], "number": pr["number"]}
    state["last_seen_head_sha"] = pr["head_sha"]
    state["last_snapshot_at"] = int(time.time())
    save_state(state_path, state)
    return {
        "pr": pr,
        "checks": checks_summary,
        "failed_runs": failed_runs,
        "failed_jobs": failed_jobs,
        "pending_review_items": pending_review_items,
        "actions": actions,
        "retry_state": {
            "current_sha_retries_used": retries_used,
            "max_flaky_retries": args.max_flaky_retries,
        },
        "state_file": str(state_path),
    }


def mark_handled(args):
    pr = resolve_pr(args.pr, repo_override=args.repo)
    state_path = Path(args.state_file) if args.state_file else default_state_file_for(pr)
    state = load_state(state_path)
    handled = {str(item_id) for item_id in state.get("handled_review_item_ids") or []}
    handled.update(str(item_id) for item_id in args.mark_handled)
    state["handled_review_item_ids"] = sorted(handled)
    state["pending_review_items"] = [
        item
        for item in state.get("pending_review_items") or []
        if isinstance(item, dict) and str(item.get("id") or "") not in handled
    ]
    state["last_snapshot_at"] = int(time.time())
    save_state(state_path, state)
    return {
        "state_file": str(state_path),
        "marked_handled": list(args.mark_handled),
        "remaining_pending_count": len(state["pending_review_items"]),
    }


def retry_failed_now(args):
    snapshot = collect_snapshot(args)
    pr = snapshot["pr"]
    checks_summary = snapshot["checks"]
    failed_runs = snapshot["failed_runs"]
    retries_used = snapshot["retry_state"]["current_sha_retries_used"]
    max_retries = snapshot["retry_state"]["max_flaky_retries"]
    result = {
        "snapshot": snapshot,
        "rerun_attempted": False,
        "rerun_count": 0,
        "rerun_run_ids": [],
        "reason": None,
    }
    if pr["closed"] or pr["merged"]:
        result["reason"] = "pr_closed"
        return result
    if checks_summary["failed_count"] <= 0:
        result["reason"] = "no_failed_pr_checks"
        return result
    if not failed_runs:
        result["reason"] = "no_failed_runs"
        return result
    if not checks_summary["all_terminal"]:
        result["reason"] = "checks_still_pending"
        return result
    if retries_used >= max_retries:
        result["reason"] = "retry_budget_exhausted"
        return result
    for run in failed_runs:
        run_id = run.get("run_id")
        if run_id in (None, ""):
            continue
        gh_text(["run", "rerun", str(run_id), "--failed"], repo=pr["repo"])
        result["rerun_run_ids"].append(run_id)
    if result["rerun_run_ids"]:
        state_path = Path(snapshot["state_file"])
        state = load_state(state_path)
        set_retry_count(state, pr["head_sha"], current_retry_count(state, pr["head_sha"]) + 1)
        state["last_snapshot_at"] = int(time.time())
        save_state(state_path, state)
        result["rerun_attempted"] = True
        result["rerun_count"] = len(result["rerun_run_ids"])
        result["reason"] = "rerun_triggered"
    else:
        result["reason"] = "failed_runs_missing_ids"
    return result


def print_json(obj):
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    sys.stdout.flush()


def snapshot_change_key(snapshot):
    pr = snapshot.get("pr") or {}
    checks = snapshot.get("checks") or {}
    pending = snapshot.get("pending_review_items") or []
    return (
        str(pr.get("head_sha") or ""),
        str(pr.get("state") or ""),
        str(pr.get("mergeable") or ""),
        str(pr.get("merge_state_status") or ""),
        str(pr.get("review_decision") or ""),
        int(checks.get("passed_count") or 0),
        int(checks.get("failed_count") or 0),
        int(checks.get("pending_count") or 0),
        tuple(str(item.get("id") or "") for item in pending if isinstance(item, dict)),
        tuple(snapshot.get("actions") or []),
    )


def run_watch(args):
    last_change_key = None
    while True:
        snapshot = collect_snapshot(args)
        print_json(
            {
                "event": "snapshot",
                "payload": {
                    "snapshot": snapshot,
                    "next_poll_seconds": args.poll_seconds,
                },
            }
        )
        actions = set(snapshot.get("actions") or [])
        if "stop_pr_closed" in actions or "stop_exhausted_retries" in actions:
            print_json({"event": "stop", "payload": {"actions": snapshot.get("actions"), "pr": snapshot.get("pr")}})
            return 0
        last_change_key = snapshot_change_key(snapshot) if last_change_key is None else snapshot_change_key(snapshot)
        time.sleep(args.poll_seconds)


def main():
    args = parse_args()
    try:
        if args.mark_handled:
            print_json(mark_handled(args))
            return 0
        if args.retry_failed_now:
            print_json(retry_failed_now(args))
            return 0
        if args.watch:
            return run_watch(args)
        print_json(collect_snapshot(args))
        return 0
    except (GhCommandError, RuntimeError, ValueError) as err:
        sys.stderr.write(f"ultra_pr_watch.py error: {err}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("ultra_pr_watch.py interrupted\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
