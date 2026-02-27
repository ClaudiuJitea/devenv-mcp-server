# 🚀 DevEnv MCP Server

An MCP (Model Context Protocol) server that provisions **Docker-based development environments** on demand.

Any AI agent (Claude, Gemini, Cursor, etc.) can call these tools to create, manage, and inspect containerized dev environments — completely hands-free. No more manual setup of Node, Python, or Docker Compose for every new project.

## ✨ Features

- **Instant Scaffolding:** Create full-stack projects (Next.js, Flask, FastAPI, etc.) with one command.
- **Docker Isolation:** Every environment runs in its own container, keeping your host machine clean.
- **Hot Reloading:** Multi-stage Dockerfiles configured for development with HMR and auto-reload.
- **Hands-free Dependencies:** The AI automatically installs required packages and sets up the environment.
- **Universal IDE Support:** Works with VS Code (Gemini), Claude Desktop, Cursor, Windsurf, and Claude CLI.

## 🛠️ Supported Stacks

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

## 📋 Prerequisites

- **Docker** with `docker compose` v2 installed and running.
- **Python 3.10+** with `pip`.

## 🚀 Quick Start

1. **Clone and Install:**
   ```bash
   git clone https://github.com/ClaudiuJitea/devenv-mcp-server.git
   cd devenv-mcp-server
   pip install -r requirements.txt
   ```

2. **Configure your IDE:** (See [IDE Integration](#-ide-integration) below)

3. **Start Creating:** Ask your AI agent:
   > "Create a new Next.js project called 'my-portfolio' using the devenv tool."

## 🔌 IDE Integration

### Gemini Code Assist (VS Code)
Add to your VS Code `settings.json`:
```json
{
  "gemini.mcp.servers": {
    "devenv": {
      "command": "python3",
      "args": ["/home/clau/MCP/server.py"],
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

## 🧰 Available Tools

| Tool | Description |
|---|---|
| `list_supported_stacks` | Show all available technology stacks |
| `create_environment` | Create a new Docker dev environment |
| `list_environments` | List all environments and their status |
| `start_environment` | Start a stopped environment |
| `stop_environment` | Stop a running environment |
| `destroy_environment` | Remove environment (optionally with files) |
| `exec_command` | Run a command inside a container |
| `get_environment_info` | Get detailed environment info |

## ⚙️ How It Works

1. **Request:** The AI agent identifies a stack requirement (e.g., "I want a Flask app").
2. **Execution:** It calls `create_environment(project_name="app", stack="flask")`.
3. **Provisioning:** The MCP server:
   - Creates a project directory.
   - Generates optimized `Dockerfile` and `docker-compose.yml`.
   - Scaffolds initial boilerplate files.
   - Starts the container and installs dependencies.
4. **Synchronization:** The project folder is volume-mounted, so your IDE edits reflect instantly in the running container.

## 🧪 Development

To test the server manually:
```bash
python3 server.py
```
Or use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):
```bash
npx @modelcontextprotocol/inspector python3 server.py
```

---
Built with ❤️ for the AI-First Developer Workflow.

