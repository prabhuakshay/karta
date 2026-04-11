# neev

A zero-dependency Python CLI that serves local directories over HTTP with authentication, file browsing, ZIP folder downloads, and optional uploads. Think `python -m http.server` with auth, better UI, and practical file-sharing features. Built entirely on the Python standard library.

Target users are developers sharing build artifacts, teams on a local network, and anyone needing a quick self-hosted file browser.

## Architecture Decisions

- **Project type**: CLI (`--app --package` with `src/` layout and `[project.scripts]` entry point)
- **Zero dependencies**: stdlib only — `argparse` for CLI, `http.server` for serving, `zipfile` for folder downloads, `html` for escaping, `base64` for auth
- **Why stdlib**: the tool should be as lightweight and portable as possible. No virtualenv needed to run it, no supply chain risk
- **Auth**: HTTP Basic Auth. Credentials via `--auth user:pass` CLI flag or `NEEV_AUTH` env var. Constant-time comparison with `hmac.compare_digest`
- **Secure defaults**: localhost-only binding, no uploads, no hidden files, no ZIP downloads unless explicitly opted in

## Domain Concepts

- **Served directory**: the root directory neev exposes over HTTP. All paths are resolved relative to this and must not escape it (path traversal protection)
- **Read-only mode**: disables all write operations (uploads) regardless of other flags
- **Hidden files**: dotfiles/dotdirs — hidden by default, shown only with `--show-hidden`
- **ZIP download**: on-the-fly ZIP streaming of a directory's contents, opt-in via `--enable-zip-download`

## Development Guidelines

- **Stability over features** — this is a security-adjacent tool. Every handler must validate paths, check auth, and respect mode flags before doing anything
- **Path traversal protection is critical** — every file/directory access must resolve the real path and verify it's within the served directory. Use `os.path.realpath()` and check prefix
- **No external dependencies** — if stdlib can't do it, it's out of scope for MVP
- **Upload safety** — when uploads are enabled: enforce max file size (100MB default), reject path traversal in filenames, write only to served directory, sanitize filenames

## Development Philosophy

Follow the Zen of Python (`import this`). These principles are non-negotiable:

### Simple over clever
- Write code a junior developer can read on their first day. If it needs a comment to explain *what* it does, rewrite it until it doesn't.
- KISS — the simplest solution that works is the right solution. Don't abstract until you must. Three similar lines are better than a premature abstraction.
- Flat is better than nested. If you're deeper than 3 levels of indentation, refactor.
- Explicit is better than implicit. No magic, no surprises.

### Optimize where it matters
- Write clear code first, then optimize the hot paths. Measure before optimizing — `cProfile`, `time`, or benchmarks, not intuition.
- Prefer built-in data structures and stdlib. They're implemented in C and almost always faster than a hand-rolled alternative.
- Use generators and lazy evaluation for large datasets. Don't load everything into memory if you don't have to.

### Maintainability is a feature
- Code is read far more than it is written. Optimize for the reader.
- Comments explain *why*, never *what*. If a comment is needed to explain what the code does, the code is bad — rewrite it with better names, smaller functions, or clearer structure.
- Every function does one thing. If you're writing "and" in a function name, split it.
- Leave `# TODO:` comments (VS Code detectable) for any future improvements, cleanup, or known limitations you spot while working. Format: `# TODO: <description>` — no assignee, no date, just the actionable note.

### Clean code defaults
- No dead code. No commented-out code. Delete it — git remembers.
- No bare `except:`. Catch specific exceptions.
- No mutable default arguments.
- Return early to avoid deep nesting.
- Use context managers (`with`) for resource management.
- Prefer composition over inheritance.

## Architecture

### Complexity is the enemy
- Every abstraction, layer, and indirection has a cost. Add them only when the pain of not having them is real, not imagined.
- Say no to features and abstractions you don't need yet. Solve the 80% case.
- Monolith first. Don't distribute until you must.

### Code organization
- Wait for natural "cut points" to emerge before refactoring — don't abstract prematurely.
- Allow measured duplication if the alternative is a complex abstraction. Two similar functions are better than one function with six parameters and three flags.
- Understand existing code before restructuring (Chesterton's Fence). If you don't know why it's there, don't remove it.

### Testing
- Integration tests over unit tests — they catch more real bugs with less maintenance.
- Write tests after the prototype, when the domain is understood.
- Always add a regression test with every bug fix.

### Logging
- Log generously, especially around I/O boundaries, retries, and error paths.
- Structured logging with context (request ID, user, operation).

## Tooling

- **[uv](https://docs.astral.sh/uv/)** — package and project management

## Code Style

- **imports**: stdlib, third-party, first-party — separated by blank lines. `from x import y` for specific items, `import x` for namespaces. Never wildcard imports
- **naming**: modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_SNAKE_CASE`. Be descriptive — `get_user_by_email` not `get_u`
- **type hints**: on all function signatures. Modern syntax (`list[str]`, `str | None`)
- **strings**: f-strings default. `%`-style only in logging calls
- **docstrings**: Google format. Every public function/method/class
- **comments**: explain *why*, never *what*. If a comment explains what the code does, the code needs rewriting, not a comment
- **logging**: `logging.getLogger(__name__)` per module. Never root logger. `%`-style formatting. `logger.exception()` in except blocks
- **TODO markers**: `# TODO: <description>` for future work — VS Code picks these up in the Problems panel and TODO Tree extension
- **file length**: Python files must stay under 300 lines (hard max 400). No exceptions — split the file if it exceeds this
