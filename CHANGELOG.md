# Changelog

## Unreleased

## v0.1.0 - 2026-04-12

Initial public release.

### Added
- zero-dependency HTTP file server CLI (`neev`) built on the Python standard library
- directory listings with per-file icons, breadcrumbs, and sortable columns
- in-browser previews for text, markdown (server-rendered), images, and PDFs
- HTTP Basic Auth via `--auth user:pass` or `NEEV_AUTH` env var, with constant-time credential comparison
- streaming ZIP downloads of folders (`--enable-zip-download`) with `--max-zip-size` cap
- opt-in file uploads (`--enable-upload`) with filename sanitization and path-traversal protection
- `--read-only` mode that force-disables writes
- `--show-hidden`, `--banner`, and custom `--host` / `--port` flags
- `neev.toml` config file support, merged under CLI precedence
- HTTP Range request support for resumable downloads and media seeking
- threaded HTTP server for concurrent request handling
- hardened origin checks and auth/upload robustness
- comprehensive README with CLI, HTTP API, security model, recipes, and architecture
