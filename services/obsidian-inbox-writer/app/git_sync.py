from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class GitSyncResult:
    synced: bool
    warning: str | None = None
    details: str | None = None
    commit_hash: str | None = None


def git_pull_rebase(vault_root: Path) -> GitSyncResult:
    result = _run_git(vault_root, ["pull", "--rebase"])
    if result.ok:
        return GitSyncResult(synced=True)
    return GitSyncResult(
        synced=False,
        warning="git pull --rebase failed",
        details=_combine_output(result),
    )


def git_commit_push(vault_root: Path, relative_path: str, message: str) -> GitSyncResult:
    add_result = _run_git(vault_root, ["add", "--", relative_path])
    if not add_result.ok:
        return GitSyncResult(
            synced=False,
            warning="git add failed",
            details=_combine_output(add_result),
        )

    diff_result = _run_git(vault_root, ["diff", "--cached", "--quiet"])
    if diff_result.returncode == 0:
        return GitSyncResult(synced=True)
    if diff_result.returncode > 1:
        return GitSyncResult(
            synced=False,
            warning="git diff failed",
            details=_combine_output(diff_result),
        )

    commit_result = _run_git(vault_root, ["commit", "-m", message])
    if not commit_result.ok:
        return GitSyncResult(
            synced=False,
            warning="git commit failed",
            details=_combine_output(commit_result),
        )

    commit_hash = git_current_head(vault_root)
    push_result = _run_git(vault_root, ["push"])
    if not push_result.ok:
        return GitSyncResult(
            synced=False,
            warning="git push failed",
            details=_combine_output(push_result),
            commit_hash=commit_hash,
        )

    return GitSyncResult(synced=True, commit_hash=commit_hash)


def git_current_head(vault_root: Path) -> str | None:
    result = _run_git(vault_root, ["rev-parse", "HEAD"])
    if not result.ok:
        return None
    return result.stdout.strip() or None


def git_short_status(vault_root: Path) -> str:
    result = _run_git(vault_root, ["status", "--short"])
    if not result.ok:
        return _combine_output(result)
    return result.stdout.strip()


def git_commit_subject(vault_root: Path, commit_hash: str) -> str | None:
    result = _run_git(vault_root, ["show", "-s", "--format=%s", commit_hash])
    if not result.ok:
        return None
    return result.stdout.strip() or None


def git_revert_push(vault_root: Path, commit_hash: str, message_prefix: str = "revert") -> GitSyncResult:
    subject = git_commit_subject(vault_root, commit_hash)
    if not subject:
        return GitSyncResult(synced=False, warning="commit not found")
    if not (subject.startswith("life: add ") or subject.startswith("life: update ") or subject.startswith("inbox: add ")):
        return GitSyncResult(synced=False, warning=f"refuse to revert non-writer commit: {subject}")

    revert_result = _run_git(vault_root, ["revert", "--no-edit", commit_hash])
    if not revert_result.ok:
        abort_result = _run_git(vault_root, ["revert", "--abort"])
        details = _combine_output(revert_result)
        if not abort_result.ok:
            details = f"{details}\n\nrevert abort also failed:\n{_combine_output(abort_result)}"
        return GitSyncResult(
            synced=False,
            warning="git revert failed",
            details=details,
        )

    revert_hash = git_current_head(vault_root)
    push_result = _run_git(vault_root, ["push"])
    if not push_result.ok:
        return GitSyncResult(
            synced=False,
            warning="git push failed",
            details=_combine_output(push_result),
            commit_hash=revert_hash,
        )

    return GitSyncResult(synced=True, commit_hash=revert_hash)


def _run_git(vault_root: Path, args: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=vault_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(returncode=1, stdout="", stderr=str(exc))

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _combine_output(result: CommandResult) -> str:
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return output or f"git exited with code {result.returncode}"
