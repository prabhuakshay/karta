# karta

Zero-dependency Python CLI for sharing local directories over HTTP with authentication, file browsing, and ZIP downloads.

`python -m http.server` is great for quick local sharing, but it lacks basic protections and convenience features — no authentication, no way to download folders, no upload support, no control over what's visible. karta fills that gap. It's a single command that serves any directory with a clean browser interface, HTTP Basic Auth, optional uploads, and ZIP folder downloads. No dependencies, no configuration files, just a CLI that does the right thing out of the box.

karta is built for developers sharing build artifacts, teams exchanging files on a local network, or anyone who needs a quick self-hosted file browser without spinning up a full server.

## Usage

```bash
# Serve current directory
karta

# Serve a specific directory
karta --dir ./public

# Serve with authentication
karta --auth user:pass

# Custom host and port
karta --dir /tmp/share --host 0.0.0.0 --port 8080

# Read-only mode (no uploads even if enabled elsewhere)
karta --read-only

# Enable folder ZIP downloads
karta --enable-zip-download

# Enable file uploads
karta --enable-upload

# Show hidden files
karta --show-hidden

# Combine flags
karta --dir ./share --auth user:pass --enable-zip-download --port 8080
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--dir` | `.` (cwd) | Directory to serve |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Bind port |
| `--auth` | none | HTTP Basic Auth credentials (`user:pass`) |
| `--read-only` | off | Disable all write operations |
| `--enable-upload` | off | Allow file uploads via browser |
| `--enable-zip-download` | off | Allow downloading folders as ZIP |
| `--show-hidden` | off | Show dotfiles in directory listings |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `KARTA_AUTH` | Auth credentials (`user:pass`), alternative to `--auth` |

## Key Concepts

- **Secure by default** — serves on localhost only, no uploads, no hidden files, no ZIP downloads unless explicitly enabled
- **Zero dependencies** — stdlib only (`http.server`, `argparse`, `zipfile`)
- **Single command** — no config files, no setup, just flags
