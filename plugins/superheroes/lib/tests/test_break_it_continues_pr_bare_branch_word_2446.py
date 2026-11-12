"""Distinguish bare paths containing 'branch' from explicit PR references.

Only throwaway repositories are written. GitHub page reading and worktree
creation are replaced; launch preflight and branch detection remain real.
"""
import json
import subprocess
from types import SimpleNamespace

import pytest

from test_launcher import L, _all_checks, _head_sha, _init_repo, _valid_premise
from test_launcher_cloud import _isolated  # noqa: F401 (autouse isolation fixture)


@pytest.mark.parametrize(('surface', 'expected_reason', 'worktree_count'), [
    ('docs/branch-guide.md', 'break-it-worktree-reached', 1),
    ('origin/docs/branch-guide.md', 'premise-continues-pr-without-adoption', 0),
    ('continue branch docs/branch-guide.md', 'premise-continues-pr-without-adoption', 0),
])
def test_branch_word_inside_a_bare_path_is_not_a_continuation_marker(
    tmp_path, monkeypatch, surface, expected_reason, worktree_count,
):
    # axis: a bare tracked path containing 'branch' passes continuation detection,
    # while explicit references to the same PR branch refuse before worktree creation.
    repo = _init_repo(tmp_path / 'repo')
    branch = 'docs/branch-guide.md'
    tracked = tmp_path / 'repo' / branch
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text('owner content\n', encoding='utf-8')
    for args in (
        ('add', branch),
        ('-c', 'user.email=test@test.local', '-c', 'user.name=test',
         'commit', '-q', '-m', 'tracked branch guide'),
        ('branch', branch),
        ('remote', 'add', 'origin', 'https://github.com/o/r.git'),
    ):
        subprocess.run(
            ['git', '-C', repo, *args],
            check=True, capture_output=True, text=True,
        )
    head = _head_sha(repo)
    answer = SimpleNamespace(
        returncode=0,
        stdout=json.dumps([{
            'number': 7,
            'head': {
                'ref': branch, 'sha': head,
                'repo': {'id': 1, 'full_name': 'o/r'},
            },
            'base': {'repo': {'id': 1, 'full_name': 'o/r'}},
        }]),
        stderr='',
    )
    monkeypatch.setattr(L, '_gh_open_pulls_page', lambda *a, **kw: answer)
    reached_worktree = []

    def stop_at_worktree(repo_root, path, base, env=None):
        reached_worktree.append(path)
        return {'ok': False, 'reason': 'break-it-worktree-reached', 'path': path}

    monkeypatch.setattr(L, 'create_build_worktree', stop_at_worktree)
    result = L.launch_build(
        repo, 656, _valid_premise(repo, surfaces=[surface]),
        _all_checks(), str(tmp_path / 'logs'),
    )
    assert result['ok'] is False
    assert result['reason'] == expected_reason, result
    assert len(reached_worktree) == worktree_count
    assert _head_sha(repo) == head
    assert tracked.read_text(encoding='utf-8') == 'owner content\n'
    branch_head = subprocess.run(
        ['git', '-C', repo, 'rev-parse', 'refs/heads/' + branch],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert branch_head == head
