"""Doc↔code census: pilot reclaim and fence contract matches pilot_reclaim.py / pilot_fence.py."""
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_fence  # noqa: E402
import pilot_reclaim  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_RECLAIM_SECTION = "## Reclaim safety"
_RECLAIM_SUBSECTIONS = (
    "### On-disk layout",
    "### Quarantine, never delete",
    "### The sidecar",
    "### Deletion authorization",
    "### The terminal receipt",
    "### The sweep",
    "### Journal rotation and retention",
    "### Reclaim refusal tokens",
    "### The reassignment acceptance probe",
    "### Fence refusal tokens",
)
_RECLAIM_TOKEN_HEADER = "| Token | When returned |"
_FENCE_TOKEN_HEADER = "| Token | When returned |"

_DESTRUCTIVE_CALLS = frozenset({
    "rmtree",
    "remove",
    "unlink",
    "rmdir",
    "removedirs",
    "replace",
    "renames",
    "move",
    "rename",
})
_RENAME_ALLOWED_FUNCTIONS = frozenset({
    "quarantine_entry",
    "rotate_journal",
})
_FORBIDDEN_FREE_SPACE = frozenset({"disk_usage", "statvfs"})
_FORBIDDEN_PARAMS = frozenset({
    "force", "prune", "aggressive", "grace_hours", "grace",
})


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _reason_constants(module):
    """Discover REASON_* string constants via dir(module)."""
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REASON_")
        and isinstance(getattr(module, name), str)
    }


def _parse_markdown_table(doc, header_line):
    """Return list of row tuples for a markdown table after header_line."""
    lines = doc.splitlines()
    try:
        start = lines.index(header_line)
    except ValueError:
        return None
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(tuple(cells))
    return rows


def _parse_token_table(doc, header_line):
    """Parse a two-column token table into a set of token strings."""
    rows = _parse_markdown_table(doc, header_line)
    if rows is None:
        raise AssertionError(
            "token table header %r not found in pilot-contract.md (file: %s)"
            % (header_line, _PILOT_CONTRACT)
        )
    tokens = set()
    for token_cell, _desc in rows:
        token = token_cell.strip("`")
        if token in tokens:
            raise ValueError("duplicate token row in table %r: %r" % (header_line, token))
        tokens.add(token)
    return tokens


def _extract_section(doc, heading):
    """Return text from heading through the next heading of equal or higher level."""
    lines = doc.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == heading
        )
    except StopIteration:
        return None
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("#"):
            heading_level = len(line) - len(line.lstrip("#"))
            if heading_level <= level:
                end = i
                break
    return "\n".join(lines[start:end])


def _assert_bidirectional_tokens(code_tokens, doc_tokens, label):
    missing_from_doc = code_tokens - doc_tokens
    extra_in_doc = doc_tokens - code_tokens
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md %s token mismatch — missing from doc: %s; in doc but not in code: %s (file: %s)"
        % (
            label,
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def _module_path(module):
    return os.path.join(_LIB, module.__name__.replace(".", "/") + ".py")


def _parse_module_ast(module):
    with open(_module_path(module), encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=_module_path(module))


class _DestructiveCallVisitor(ast.NodeVisitor):
    """Collect destructive primitive call sites via Name and Attribute nodes."""

    def __init__(self, filename):
        self.filename = filename
        self.import_aliases = {}
        self.calls = []
        self.subprocess_calls = []
        self._function_stack = []

    def visit_FunctionDef(self, node):
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[-1]
            self.import_aliases[name] = alias.name

    def visit_ImportFrom(self, node):
        if node.module == "subprocess":
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_aliases[name] = "subprocess.%s" % alias.name
        elif node.module == "shutil":
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_aliases[name] = "shutil.%s" % alias.name
        elif node.module == "os":
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_aliases[name] = "os.%s" % alias.name
        elif node.module == "pathlib":
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_aliases[name] = "pathlib.%s" % alias.name

    def _resolve_call(self, func_node):
        if isinstance(func_node, ast.Name):
            name = func_node.id
            if name in self.import_aliases:
                return self.import_aliases[name]
            return name
        if isinstance(func_node, ast.Attribute):
            value = func_node.value
            attr = func_node.attr
            if isinstance(value, ast.Name):
                base = value.id
                if base in self.import_aliases:
                    base = self.import_aliases[base]
                return "%s.%s" % (base, attr)
            if isinstance(value, ast.Attribute):
                inner = self._resolve_call(value)
                if inner is not None:
                    return "%s.%s" % (inner, attr)
            if isinstance(value, ast.Call):
                inner = self._resolve_call(value.func)
                if inner is not None:
                    return "%s.%s" % (inner, attr)
            return None
        return None

    def _is_destructive_target(self, target):
        if target is None:
            return False
        leaf = target.split(".")[-1]
        if leaf not in _DESTRUCTIVE_CALLS:
            return False
        if leaf == "rename":
            if not self._function_stack:
                return True
            return self._function_stack[-1] not in _RENAME_ALLOWED_FUNCTIONS
        if target.startswith(("shutil.", "os.")):
            return True
        if target in self.import_aliases:
            resolved = self.import_aliases[target]
            return resolved.startswith(("shutil.", "os."))
        if target.endswith((".unlink", ".rmdir")):
            base = target.rsplit(".", 1)[0]
            return base in ("Path", "pathlib.Path") or base in self.import_aliases
        return False

    def _is_subprocess_target(self, target):
        if target is None:
            return False
        if target == "subprocess" or target.startswith("subprocess."):
            return True
        if target in self.import_aliases:
            return self.import_aliases[target].startswith("subprocess.")
        return False

    def visit_Call(self, node):
        target = self._resolve_call(node.func)
        if self._is_destructive_target(target):
            self.calls.append((node.lineno, target))
        if self._is_subprocess_target(target):
            self.subprocess_calls.append((node.lineno, target))
        self.generic_visit(node)


class _IdentifierVisitor(ast.NodeVisitor):
    """Collect identifier references for free-space and forbidden-param checks."""

    def __init__(self):
        self.names = []
        self.import_aliases = {}

    def visit_ImportFrom(self, node):
        if node.module == "shutil":
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_aliases[name] = "shutil.%s" % alias.name
        self.generic_visit(node)

    def visit_Name(self, node):
        self.names.append((node.lineno, node.id))

    def visit_Attribute(self, node):
        self.names.append((node.lineno, node.attr))
        self.generic_visit(node)


class _PublicFunctionVisitor(ast.NodeVisitor):
    """Collect public function definitions and their parameter names."""

    def __init__(self):
        self.functions = []

    def visit_FunctionDef(self, node):
        if not node.name.startswith("_"):
            params = [arg.arg for arg in node.args.args]
            params.extend(kw.arg for kw in node.args.kwonlyargs)
            self.functions.append((node.lineno, node.name, params))
        self.generic_visit(node)


def _collect_destructive_calls(module):
    tree = _parse_module_ast(module)
    visitor = _DestructiveCallVisitor(_module_path(module))
    visitor.visit(tree)
    return visitor.calls, visitor.subprocess_calls


def _collect_identifiers(module):
    tree = _parse_module_ast(module)
    visitor = _IdentifierVisitor()
    visitor.visit(tree)
    return visitor.names


def _collect_public_functions(module):
    tree = _parse_module_ast(module)
    visitor = _PublicFunctionVisitor()
    visitor.visit(tree)
    return visitor.functions


def test_reclaim_safety_sections_present():
    doc = _load_contract()
    assert _RECLAIM_SECTION in doc, (
        "missing section %s (file: %s)" % (_RECLAIM_SECTION, _PILOT_CONTRACT)
    )
    for heading in _RECLAIM_SUBSECTIONS:
        assert heading in doc, (
            "missing subsection %s (file: %s)" % (heading, _PILOT_CONTRACT)
        )


def test_reclaim_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _RECLAIM_SECTION)
    assert section is not None
    token_start = section.index("### Reclaim refusal tokens")
    reclaim_tokens_section = section[token_start:]
    doc_tokens = _parse_token_table(reclaim_tokens_section, _RECLAIM_TOKEN_HEADER)
    code_tokens = _reason_constants(pilot_reclaim)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_reclaim REASON_*")


def test_fence_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _RECLAIM_SECTION)
    assert section is not None
    token_start = section.index("### Fence refusal tokens")
    fence_tokens_section = section[token_start:]
    doc_tokens = _parse_token_table(fence_tokens_section, _FENCE_TOKEN_HEADER)
    code_tokens = _reason_constants(pilot_fence)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_fence REASON_*")


def test_only_authorized_shutil_rmtree_in_reclaim_modules():
    """The only destructive primitive call in either module is one shutil.rmtree."""
    all_calls = []
    all_subprocess = []
    for module in (pilot_reclaim, pilot_fence):
        calls, subprocess_calls = _collect_destructive_calls(module)
        for lineno, target in calls:
            all_calls.append((module.__name__, lineno, target))
        for lineno, target in subprocess_calls:
            all_subprocess.append((module.__name__, lineno, target))
    if all_subprocess:
        site = all_subprocess[0]
        raise AssertionError(
            "forbidden subprocess call at %s:%d (%s)"
            % (site[0], site[1], site[2])
        )
    rmtree_calls = [
        site for site in all_calls if site[2].endswith("rmtree")
    ]
    non_rmtree = [site for site in all_calls if not site[2].endswith("rmtree")]
    if non_rmtree:
        site = non_rmtree[0]
        raise AssertionError(
            "forbidden destructive call at %s:%d (%s)"
            % (site[0], site[1], site[2])
        )
    assert len(rmtree_calls) == 1, (
        "expected exactly one shutil.rmtree call, found %d: %s"
        % (len(rmtree_calls), rmtree_calls)
    )
    site = rmtree_calls[0]
    assert site[0] == "pilot_reclaim", (
        "shutil.rmtree must live in pilot_reclaim, not %s (line %d)"
        % (site[0], site[1])
    )

    tree = _parse_module_ast(pilot_reclaim)
    visitor = _DestructiveCallVisitor(_module_path(pilot_reclaim))
    visitor.visit(tree)
    rmtree_enclosing = None
    stack = []

    class _EnclosingWalker(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_Call(self, node):
            target = visitor._resolve_call(node.func)
            nonlocal rmtree_enclosing
            if target and target.endswith("rmtree"):
                rmtree_enclosing = stack[-1] if stack else None
            self.generic_visit(node)

    _EnclosingWalker().visit(tree)
    if rmtree_enclosing != "_delete_entry":
        raise AssertionError(
            "shutil.rmtree must be inside _delete_entry, found in %r"
            % rmtree_enclosing
        )


def test_no_free_space_read_in_reclaim_modules():
    """Neither module references disk_usage or statvfs."""
    for module in (pilot_reclaim, pilot_fence):
        tree = _parse_module_ast(module)
        id_visitor = _IdentifierVisitor()
        id_visitor.visit(tree)
        for lineno, name in id_visitor.names:
            lower = name.lower()
            if name in _FORBIDDEN_FREE_SPACE or "disk_usage" in lower or "statvfs" in lower:
                raise AssertionError(
                    "forbidden free-space read %r at %s:%d"
                    % (name, module.__name__, lineno)
                )
        for alias_name, resolved in id_visitor.import_aliases.items():
            if resolved in _FORBIDDEN_FREE_SPACE or "disk_usage" in resolved:
                raise AssertionError(
                    "forbidden free-space import %r -> %r in %s"
                    % (alias_name, resolved, module.__name__)
                )


def test_no_forbidden_public_parameters_in_reclaim_modules():
    """No public function takes force/prune/aggressive/grace_hours/grace."""
    for module in (pilot_reclaim, pilot_fence):
        for lineno, func_name, params in _collect_public_functions(module):
            for param in params:
                if param in _FORBIDDEN_PARAMS:
                    raise AssertionError(
                        "forbidden parameter %r on public function %s at %s:%d"
                        % (param, func_name, module.__name__, lineno)
                    )


def test_grace_hours_threshold_matches_doc():
    assert pilot_reclaim.GRACE_HOURS == 72
    doc = _load_contract()
    section = _extract_section(doc, _RECLAIM_SECTION)
    assert section is not None
    assert "72" in section, (
        "pilot-contract.md reclaim section missing 72-hour grace (file: %s)"
        % _PILOT_CONTRACT
    )


_LAYOUT_FILENAME_SITES = {
    "slot.json": ("pilot_lifecycle", "record_path"),
    ".slot.lock": ("pilot_lifecycle", "lock_path"),
    "journal.ndjson": ("pilot_reclaim", "_journal_segment_re_for"),
    ".pilot-quarantine": ("pilot_reclaim", "QUARANTINE_DIR_NAME"),
    ".quarantine.json": ("pilot_reclaim", "SIDECAR_SUFFIX"),
}


def test_on_disk_layout_filenames_match_lib():
    doc = _load_contract()
    section = _extract_section(doc, _RECLAIM_SECTION)
    assert section is not None
    layout_start = section.index("### On-disk layout")
    layout_block = section[layout_start:].split("```")[1]
    for filename, site in _LAYOUT_FILENAME_SITES.items():
        assert filename in layout_block, (
            "pilot-contract.md on-disk layout missing %r (file: %s)"
            % (filename, _PILOT_CONTRACT)
        )
        module_name, attr = site
        if module_name == "pilot_lifecycle":
            import pilot_lifecycle as pl_mod
            if attr == "record_path":
                path = pl_mod.record_path("/slots", "slot-a")
                assert path.endswith(filename)
            elif attr == "lock_path":
                path = pl_mod.lock_path("/slots", "slot-a")
                assert path.endswith(filename)
        elif module_name == "pilot_reclaim":
            if attr == "_journal_segment_re_for":
                journal_path = os.path.join("/slots", "slot-a", filename)
                seg_re = pilot_reclaim._journal_segment_re_for(journal_path)
                assert seg_re.match("journal.0001.ndjson")
            else:
                assert getattr(pilot_reclaim, attr) == filename
