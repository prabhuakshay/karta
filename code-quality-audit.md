# Code Quality Audit

## Scope
- Repository path: `/home/konkan/projects/python-projects/karta`
- Audit date: 2026-04-12
- Requested scope: full-repository audit of first-party code, tests, and quality config
- Report path: `code-quality-audit.md`

## Governing Standards
- Repo guidance read: `CLAUDE.md`
- Tooling and config read: `pyproject.toml`, `.pre-commit-config.yaml`, `README.md`, `package.json`
- Audit references read: `references/checklist.md`, `references/reporting.md` from the `code-quality-audit-reviewer` skill
- Commands run:
  - `git status --short`
  - `find src/neev -maxdepth 1 -name '*.py' -print | sort`
  - `find tests -maxdepth 1 -name '*.py' -print | sort`
  - `xargs wc -l < <(find src/neev -maxdepth 1 -name '*.py' -print | sort)`
  - `xargs wc -l < <(find tests -maxdepth 1 -name '*.py' -print | sort)`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run ty check`
  - `uv run pytest -q`
  - Targeted local repro commands for upload and auth edge cases

## Repository State
- Worktree state: clean at audit time (`git status --short` returned no tracked modifications)
- Confidence note: findings are based on current checked-in code and local tool output, not an in-progress refactor

## Findings

### High
#### 1. Browser folder uploads lose their directory structure because the form and parser disagree on multipart field ordering
Why it matters:

The UI advertises folder upload, but the server only applies a `relativePath` value to the next file part it sees. The browser form emits file inputs before the hidden `relativePath` fields, so real browser submissions flatten folder uploads into the current directory instead of recreating nested paths. That is a user-visible correctness bug on a primary write path.

Evidence:
- `CLAUDE.md:70-73`
- `src/neev/html_upload.py:160-165`
- `src/neev/upload.py:165-180`
- `tests/test_upload_unit.py:206-214`

Details:

`render_upload_section()` places the hidden `relativePath` inputs after the file inputs, so the multipart body order is file part(s) first and path metadata later. `handle_upload()` stores a single `pending_rel_path` and only uses it when a later file part arrives, which means browser-style folder uploads save `file.txt` directly in the target directory. A local reproduction confirmed the bug: a multipart body with `file` followed by `relativePath` saved `file.txt` at the root and did not create `myfolder/sub/file.txt`.

Remediation:

Bind path metadata to each file deterministically instead of depending on part order. The safest fix is to encode the relative path in the file part itself or buffer the parsed parts so each file can be matched to its own path metadata before writing to disk. Add a real HTTP integration test that exercises `webkitdirectory`-style ordering.

#### 2. Invalid UTF-8 on the login endpoint crashes the request handler instead of returning a 4xx
Why it matters:

This is a security-adjacent auth path. A single malformed byte sequence currently raises `UnicodeDecodeError`, tears down the handler, and drops the client connection with no HTTP response. That violates the repo’s “stability over features” guidance for request handlers and makes an error path behave like a server fault.

Evidence:
- `CLAUDE.md:28-31`
- `CLAUDE.md:75-77`
- `src/neev/server_auth.py:67-77`
- `tests/test_auth_integration.py:123-159`

Details:

`handle_login()` decodes the request body with `.decode("utf-8")` and does not catch `UnicodeDecodeError`. A local repro against a live server with `body=b"\xff"` caused a traceback in `server_auth.py:76` and the client received `RemoteDisconnected` instead of a 400 response. The current auth integration tests cover valid, invalid, and oversized bodies, but not malformed encodings.

Remediation:

Treat bad form encodings as client errors: decode with `errors="strict"` inside a `try` block and return `400 Bad Request` on `UnicodeDecodeError`. Add a regression test that posts invalid UTF-8 to `/_neev/login`.

#### 3. The multipart parser accepts truncated bodies without a closing boundary and still writes files
Why it matters:

Uploads are a write path. Accepting malformed multipart as successful input means a partially transmitted or truncated request can still create files on disk, which is the wrong failure mode for a security-sensitive endpoint.

Evidence:
- `CLAUDE.md:28-31`
- `src/neev/upload_multipart.py:157-175`
- `src/neev/upload.py:167-186`
- `tests/test_upload_unit.py:116-119`

Details:

`_MultipartStream._read_body()` writes whatever remains in the buffer and returns when the stream ends without ever seeing the next delimiter. `handle_upload()` then treats the part as valid and saves it. A local reproduction with a body missing the terminating `--boundary--` still produced `x.txt` on disk. The unit suite currently codifies that behavior by asserting `test_no_closing_boundary` returns a parsed part instead of an error.

Remediation:

Reject incomplete multipart bodies. `_read_body()` should raise `UploadError` if EOF is reached before the next delimiter, and the tests should be updated to expect a 400 instead of a successful parse/save.

### Medium
#### 1. The repository advertises type-checking support, but `ty` currently fails with 25 diagnostics across the test suite
Why it matters:

This project explicitly carries `ty` as a dev dependency and a `tool.ty` section in `pyproject.toml`, so a failing type-check baseline is real quality drift. It also undermines the repo’s “type hints on all function signatures” rule and reduces trust in test helpers that are heavily reused across integration tests.

Evidence:
- `CLAUDE.md:87-89`
- `pyproject.toml:40-47`
- `pyproject.toml:165-166`
- `tests/test_auth_integration.py:97-99`
- `tests/test_server.py:68-70`
- `tests/test_server_preview.py:67-69`
- `tests/test_coverage_gaps.py:41-54`
- `tests/test_issue_103.py:20-33`

Details:

`uv run ty check` reported 25 diagnostics. The main patterns are:
- broad `except Exception` branches that probe `.code`, `.headers`, and `.read()` on values that are not typed as HTTP errors
- untyped `defaults.update(overrides)` config builders that widen `Config(**defaults)` beyond the declared constructor types
- tests that call preview helpers with stub handlers while suppressing type mismatches

Ruff and pytest are green, so this drift is easy to miss today.

Remediation:

Introduce typed helper protocols or catch `urllib.error.HTTPError` explicitly in the request helpers, replace loose `dict` config builders with typed factory functions, and remove `type: ignore` scaffolding by using stubs/protocols that match the handler interfaces.

#### 2. Preview pages depend on external CDNs, which breaks the repo’s portability story on isolated networks
Why it matters:

The README positions `neev` as a lightweight local-network sharing tool, but markdown and text previews will degrade or fail on air-gapped or firewalled networks because core rendering assets are fetched from `cdn.jsdelivr.net`. That is an architectural mismatch for a tool sold on self-contained portability.

Evidence:
- `README.md:58-60`
- `README.md:64-72`
- `src/neev/html_markdown.py:17-33`
- `src/neev/html_preview.py:115-131`

Details:

Markdown preview pulls `marked`, `mermaid`, `DOMPurify`, and highlight.js from jsDelivr. Text preview also pulls highlight.js CSS and JS from the CDN. The Python package has zero runtime dependencies, but these UI features are not actually self-contained once the browser loads them.

Remediation:

Bundle these assets under `src/neev/static/` or make CDN-backed preview enhancement optional with a graceful offline fallback that still renders raw content locally.

### Low
#### 1. `src/neev/cli.py` exceeds the repo’s hard 300-line Python file limit
Why it matters:

This is a direct violation of an explicit repo rule. It is not a correctness bug by itself, but it does mean the project is already drifting from its own “small, simple, split when needed” standard.

Evidence:
- `CLAUDE.md:93`
- `src/neev/cli.py:1`

Details:

`xargs wc -l < <(find src/neev -maxdepth 1 -name '*.py' -print | sort)` reports `src/neev/cli.py` at 309 lines. The file is still readable, but it now sits past the line budget the repo calls a hard maximum.

Remediation:

Split parser construction, validation helpers, and startup banner rendering into one or two adjacent modules, or move config-building helpers beside `config.py`/`toml_config.py`.

## Open Questions
- Should folder upload support remain in scope? If yes, the server/parser contract needs to be made browser-realistic rather than test-only.
- Is `ty` intended to be part of the supported workflow today, or is it still aspirational? The current config suggests “yes,” but it is not enforced in pre-commit.
- Are CDN-backed preview enhancements acceptable for this project, or should `neev` remain fully self-contained for offline/LAN use?

## Coverage Notes
- Deep review covered all first-party Python modules under `src/neev/` and all checked-in tests under `tests/`.
- Static assets were only reviewed for ownership and integration concerns, not line-by-line minified content. `src/neev/static/alpine.min.js` was treated as bundled third-party code.
- I did not perform browser-driven UI interaction; the folder-upload finding was confirmed through multipart ordering and local reproductions rather than an actual browser session.
- Tool results:
  - `uv run ruff check .`: passed
  - `uv run ruff format --check .`: passed
  - `uv run pytest -q`: passed (`387 passed`, coverage `97.81%`)
  - `uv run ty check`: failed with 25 diagnostics

## Recommended Priorities
1. Fix the upload path handling and multipart truncation behavior before relying on uploads in real use; both findings affect write-path correctness.
2. Harden `/_neev/login` against malformed request bodies and add regression coverage for invalid encodings.
3. Restore a passing `ty` baseline so the configured type-check tooling becomes trustworthy again.
4. Decide whether preview pages must work offline; if yes, vendor the browser assets and add tests for the self-contained path.
