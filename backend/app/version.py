"""Code version determination via direct filesystem access without git commands."""

from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent.parent


def get_code_version(repo_root: Path | None = None) -> str:
    """Read short git commit hash directly from the filesystem (.git), or return 'unknown'.

    Per Decision D-09, strictly avoids running git subprocess commands.
    """
    root = repo_root if repo_root is not None else get_repo_root()
    git_dir = root / ".git"

    if not git_dir.is_dir():
        # Might be a git worktree or submodule with a .git file pointing to gitdir
        if git_dir.is_file():
            try:
                content = git_dir.read_text(encoding="utf-8").strip()
                if content.startswith("gitdir:"):
                    git_dir = (root / content[7:].strip()).resolve()
            except OSError:
                return "unknown"
        else:
            return "unknown"

    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return "unknown"

    try:
        head_content = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"

    if not head_content:
        return "unknown"

    if head_content.startswith("ref:"):
        ref_path = head_content[4:].strip()
        ref_file = git_dir / ref_path
        if ref_file.is_file():
            try:
                commit_hash = ref_file.read_text(encoding="utf-8").strip()
                return commit_hash[:7] if len(commit_hash) >= 7 else commit_hash
            except OSError:
                return "unknown"

        # Check packed-refs if loose ref file doesn't exist
        packed_refs_file = git_dir / "packed-refs"
        if packed_refs_file.is_file():
            try:
                for line in packed_refs_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("^"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == ref_path:
                            commit_hash = parts[0]
                            return commit_hash[:7] if len(commit_hash) >= 7 else commit_hash
            except OSError:
                return "unknown"

        return "unknown"

    # Detached HEAD: directly contains the commit hash
    return head_content[:7] if len(head_content) >= 7 else head_content
