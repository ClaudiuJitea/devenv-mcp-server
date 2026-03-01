# DevEnv MCP Server

An MCP (Model Context Protocol) server that provisions **Docker-based development environments** on demand.

Any AI agent (Claude, Gemini, Cursor, etc.) can call these tools to create, manage, and inspect containerized dev environments — completely hands-free. No more manual setup of Node, Python, or Docker Compose for every new project.

## Features

- **Instant Scaffolding:** Create full-stack projects (Next.js, Flask, FastAPI, etc.) with one command.
- **Docker Isolation:** Every environment runs in its own container, keeping your host machine clean.
- **Two Workspace Modes:** `isolated` (default, container-only files) or `mapped` (bind-mounted host files).
- **Hands-free Dependencies:** The AI automatically installs required packages and sets up the environment.
- **Direct File Access:** `write_file` and `read_file` tools let the agent modify files inside the container.
- **Portable Export:** `export_environment` snapshots an environment into a Docker image tarball.
- **Universal IDE Support:** Works with VS Code (Gemini), Claude Desktop, Cursor, Windsurf, and Claude CLI.

## Supported Stacks

| Stack | Framework | Base Image | Default Port |
|---|---|---|---|
| `flask` | Flask (Python) | `python:3.12-slim` | 5000 |
| `django` | Django (Python) | `python:3.12-slim` | 8000 |
| `fastapi` | FastAPI (Python) | `python:3.12-slim` | 8000 |
| `nextjs` | Next.js (React) | `node:20-slim` | 3000 |
| `vite-react` | Vite + React | `node:20-slim` | 5173 |
| `vite-vue` | Vite + Vue | `node:20-slim` | 5173 |
| `express` | Express.js | `node:20-slim` | 3000 |
| `static-html` | Static HTML/CSS/JS | `node:20-slim` | 8080 |
| `laravel` | Laravel (PHP) | `php:8.3-fpm-alpine` | 8000 |
| `symfony` | Symfony (PHP) | `php:8.3-fpm-alpine` | 8000 |
| `nestjs` | NestJS (Node.js) | `node:22-slim` | 3000 |
| `bun-hono` | Hono (Bun) | `oven/bun:1-alpine` | 3000 |
| `rust-axum` | Axum/Actix (Rust) | `rust:1-slim` | 8080 |
| `go-gin` | Gin/Fiber (Go) | `golang:1.24-alpine` | 8080 |
| `nginx-static` | Nginx (Static Assets) | `nginx:alpine` | 80 |

## Prerequisites

- **Docker** with `docker compose` v2 installed and running.
- **Python 3.10+** with `pip`.

## Quick Start

1. **Clone and Install:**
   ```bash
   git clone https://github.com/ClaudiuJitea/devenv-mcp-server.git
   cd devenv-mcp-server
   pip install -r requirements.txt
   ```

2. **Configure your IDE:** (See [IDE Integration](#ide-integration) below)

3. **Start Creating:** Ask your AI agent:
   > "Create a new Next.js project called 'my-portfolio' using the devenv tool."

## IDE Integration

### Gemini Code Assist (VS Code)
Add to your VS Code `settings.json`:
```json
{
  "gemini.mcp.servers": {
    "devenv": {
      "command": "python3",
      "args": ["/absolute/path/to/server.py"],
      "env": {}
    }
  }
}
```

### Claude Desktop
Add to `~/.config/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "devenv": {
      "command": "python3",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

### Cursor / Windsurf / Claude CLI
The server supports the standard MCP protocol via `stdio`. Use the path to `server.py` in your configuration.

## Available Tools

| Tool | Description |
|---|---|
| `list_supported_stacks` | Show all available technology stacks |
| `create_environment` | Create a new Docker dev environment |
| `list_environments` | List all environments and their status |
| `start_environment` | Start a stopped environment |
| `stop_environment` | Stop a running environment |
| `destroy_environment` | Remove environment, container, volumes, associated images, and files by default |
| `exec_command` | Run a command inside a container |
| `write_file` | Write/create a file inside a container's /app |
| `read_file` | Read a file from a container's /app |
| `get_environment_info` | Get detailed environment info |
| `export_environment` | Export a portable image tar and generate deploy scripts |

## Workspace Modes

`create_environment` supports `workspace_mode`:

- `isolated` (default): no host bind mount. Source code, dependencies, and generated files stay inside the container.
- `mapped`: bind-mount project files from `~/devenv-projects/<project>` to `/app` for direct host editing.

Recommended default is `isolated` when you want portability and host isolation.

## How It Works

1. **Request:** The AI agent identifies a stack requirement (e.g., "I want a Flask app").
2. **Execution:** It calls `create_environment(project_name="app", stack="flask", workspace_mode="isolated")`.
3. **Provisioning:** The MCP server:
   - Creates a project directory at `~/devenv-projects/<project>/`.
   - Generates Dockerfile, compose, and metadata files.
   - Builds and starts a dedicated container for that project.
   - Runs stack-specific initialization commands when required.
4. **Editing Workflow:**
   - In `isolated` mode, use `write_file`, `read_file`, and `exec_command` to work entirely in-container.
   - In `mapped` mode, edit files directly from the host and they reflect in the container.
5. **Portability:** Call `export_environment` to snapshot and save a tarball (`docker load -i ...` on another machine). In mapped mode, export automatically captures mapped host files into an isolated image first. The export also writes `deploy-<project>.sh` and `deploy-<project>.ps1` next to the tar.

## Directory Structure

```
~/devenv-projects/
└── my-project/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .devenv.json
    ├── app.py            # or stack scaffold files
    └── ...
```

## Development

To test the server manually:
```bash
python3 server.py
```
Or use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):
```bash
npx @modelcontextprotocol/inspector python3 server.py
```

---
Built for the AI-First Developer Workflow.
