"""Every row of a GitHub REST list, read one page at a time by page number.

`read(fetch, path, key=None)` asks for `path` with `per_page=100&page=N` for N = 1, 2, ... and returns
the rows of every page, or None when any page cannot be read. It asks by number on the same repos/...
path because gh's paginate flag follows GitHub's Link next-page URLs instead, which name
repositories/{id}/..., and the cloud session's proxy refuses those with HTTP 403 (#1890, #1901).
A caller that wants only a list's first `limit` rows passes `limit`, and the read stops as soon as it holds them.

`fetch(endpoint)` is the caller's one `gh api <endpoint>` call: it returns that call's stdout text, or
None when the call failed. The reader runs no process of its own, so each caller keeps its own runner,
environment and timeout. Stdlib only.
"""
import json

# GitHub serves at most 100 rows a page; a page with fewer ends the list.
PAGE_ROWS = 100
# A bound on a read that never ends: a list this long fails the read, never returns what was read so far.
MAX_PAGES = 1000


def read(fetch, path, key=None, limit=None):
    """Every row of a GitHub REST list, or None when any page cannot be read.

    `key` names the list inside a page that is an object (check runs); otherwise the page is the list.
    `limit` (a positive int) returns exactly the first `limit` rows and asks for no page after the one that holds them.
    A path that already carries a query gets the page query joined with `&`."""
    sep = "&" if "?" in path else "?"
    rows = []
    for number in range(1, MAX_PAGES + 1):
        out = fetch(f"{path}{sep}per_page={PAGE_ROWS}&page={number}")
        try:
            page = None if out is None else json.loads(out)
        except ValueError:
            page = None
        if key is not None:
            page = page.get(key) if isinstance(page, dict) else None
        # axis: a page that cannot be read, or is not a list, fails the whole read, never a partial list — see bite-proof record wo1_1901_gh_pages
        if not isinstance(page, list):
            return None
        rows.extend(page)
        # axis: a read holding `limit` rows stops there and returns exactly the first `limit`, asking for no later page
        if limit is not None and len(rows) >= limit:
            return rows[:limit]
        # axis: the first page with fewer than a full page's rows (an empty one included) ends the read — see bite-proof record wo1_1901_gh_pages
        if len(page) < PAGE_ROWS:
            return rows
    # axis: a list that never ends fails the read, never returns what was read so far — see bite-proof record wo1_1901_gh_pages
    return None
