# Milestone 4 — FastAPI on app01 and app02

## Goal

Run an identical Python web API on two VMs (app01, app02) as a Docker container, connected to the Postgres database on db01. Both app nodes must be independently reachable, share the same data, and identify themselves by their VM hostname so the upcoming load-balancing demo is observable.

## What was built

### File layout

    app/
    ├── Dockerfile            # how to build the image
    ├── docker-compose.yml    # how to run it, per VM
    ├── requirements.txt      # pinned Python dependencies
    ├── main.py               # the FastAPI app
    ├── .env                  # DB connection details (git-ignored)
    └── .env.example          # template, committed

### The app (`main.py`)

A small FastAPI service with four endpoints:

| Method | Path     | Purpose |
|--------|----------|---------|
| GET    | /health  | Liveness probe, returns `{"status":"ok","host":"<vm>"}` |
| GET    | /whoami  | Returns `{"host":"<vm>"}` — used to demonstrate load balancing |
| GET    | /items   | Lists all rows from the `items` table |
| POST   | /items   | Creates a new item from `{"name":"..."}` JSON body |

Key design choices:

- **DB connection details come from environment variables** with sensible defaults. Keeps secrets out of code.
- **`lifespan` hook** runs `SELECT 1` at startup. If Postgres is unreachable, the container fails fast rather than serving broken responses.
- **Hostname reporting** uses an `APP_HOST` env var if set (the VM's real hostname is passed in), otherwise falls back to the container's internal hostname. This matters because Docker by default gives containers random IDs as hostnames. Without this override the `/whoami` endpoint would return useless container IDs and the load-balancing demo in milestone 5 would be meaningless.
- **Direct `psycopg` connections per request** — simpler than connection pooling for a demo, fine for the traffic this will see. A real production app would use a pool.

### The Dockerfile

- `python:3.12-slim` base — small but complete enough for FastAPI.
- Dependencies installed in a separate layer *before* the app code is copied. Docker caches this layer, so rebuilds after code changes are fast; rebuilds after dependency changes are slow. Deliberate ordering.
- Runs as a non-root user (`appuser`, UID 1001). Defense in depth — a compromised container is still sandboxed, but best practice is to drop privileges anyway.
- `PYTHONUNBUFFERED=1` so logs reach stdout immediately instead of being buffered by Python's default behaviour.
- `uvicorn` bound to `0.0.0.0:8000` inside the container so Docker can map it to the host.

### The Compose file

- `build: .` instead of `image:` — the image is built from the local Dockerfile rather than pulled from a registry.
- `APP_HOST: ${APP_HOST:-unknown}` — reads the VM's hostname from the environment when `docker compose` runs, falling back to "unknown" if not set.
- Healthcheck uses a one-liner Python script hitting `/health` — avoids adding `curl` to the image just for the healthcheck.

### The Vagrantfile change

Synced-folder rsync options had to be made explicit so `.env` files sync into the VMs. vagrant-libvirt's default rsync excludes respect `.gitignore`, which means `.env` (git-ignored) would have been silently skipped. Overriding the exclude list to just `.vagrant/` and `.git/` solves it:

    config.vm.synced_folder ".", "/vagrant", type: "rsync",
      rsync__exclude: [".vagrant/", ".git/"],
      rsync__args: ["--verbose", "--archive", "--delete", "-z"]

## How to run it

On each app node, with the VM hostname passed in at runtime so `APP_HOST` becomes `app01` or `app02`:

    vagrant ssh app01 -c "cd /vagrant/app && APP_HOST=\$(hostname) docker compose up -d --build"
    vagrant ssh app02 -c "cd /vagrant/app && APP_HOST=\$(hostname) docker compose up -d --build"

The `\$` (escaped `$`) is important. Without the backslash, the host shell expands `$(hostname)` before the command is sent to the VM, and the VM gets the host's name — wrong. With the backslash, the expansion happens inside the VM.

## Evidence of correctness

Four tests, each demonstrating a specific property of the system.

### 1. Each app node identifies itself correctly

    vagrant ssh app01 -c "curl -s http://localhost:8000/whoami"
    # -> {"host":"app01"}

    vagrant ssh app02 -c "curl -s http://localhost:8000/whoami"
    # -> {"host":"app02"}

**Why this proves something:** without the `APP_HOST` override, both would have returned container IDs like `c4b5e1f80cc8`. Distinct, correct hostnames per VM confirm the env-var injection is working and the load-balancing demo in the next milestone will be observable.

### 2. Each app node can reach the database on startup

The `lifespan` hook in `main.py` runs a `SELECT 1` before serving any requests. If the container shows `(healthy)` status, that query succeeded.

    vagrant ssh app01 -c "docker ps"
    # -> STATUS: Up X seconds (healthy)

**Why this proves something:** it's not enough for the container to start. A container would happily start with a broken database config and then fail on every request. The startup probe guarantees the DB path is open before any endpoint is called. Healthy status means app01 → 10.10.10.20:5432 is working.

### 3. Both app nodes read and write the same database

    # Write from app01
    vagrant ssh app01 -c "curl -s -X POST http://localhost:8000/items \
        -H 'Content-Type: application/json' \
        -d '{\"name\": \"from app01\"}'"
    # -> {"id":3,"name":"from app01","created_at":"..."}

    # Read from app02
    vagrant ssh app02 -c "curl -s http://localhost:8000/items"
    # -> [... {"id":3,"name":"from app01",...} ...]

**Why this proves something:** this is the defining test of a 3-tier architecture. If app01 and app02 were independent stacks (say, each with its own embedded SQLite), app02 would not see what app01 wrote. A write on one node being visible on the other via the database proves:

- The app tier is stateless
- The data tier is shared
- The network path from both app nodes to db01 is working
- The authentication and schema seen by each node are identical

Without this test, two nodes could "work" in isolation and silently misbehave under load balancing.

### 4. Input validation rejects bad requests

    vagrant ssh app01 -c "curl -s -X POST http://localhost:8000/items \
        -H 'Content-Type: application/json' \
        -d '{\"name\": \"\"}'"
    # -> {"detail":"name must not be empty"}

**Why this proves something:** pydantic validates the JSON shape, but empty strings still pass type-checking. The explicit `if not item.name.strip()` check in `create_item` demonstrates that business-logic validation happens even when type validation lets something through. Not critical for the lab, but documents an intended pattern.

## Failure modes and what they'd look like

- **`/whoami` returns container ID like `c4b5e1f80cc8`** — `APP_HOST` env var not set. Check that `docker compose up` was run with `APP_HOST=$(hostname)`.
- **Container status `Restarting` in a loop** — `lifespan` startup failed, usually DB unreachable. `docker logs app` inside the VM shows the psycopg error.
- **HTTP 500 on `/items`** — schema mismatch or DB connection dropped. Check app container logs.
- **`{"host":""}`** — `APP_HOST` was set to an empty string, usually because `$HOSTNAME` was referenced in a non-interactive shell where it wasn't exported. Use `$(hostname)` instead, which always works.

## Lessons learned

**Container hostnames are not VM hostnames.** `socket.gethostname()` inside a container returns the container ID. Useful for debugging a specific container instance; useless for identifying which VM the container is running on. Pass the VM hostname in as an env var if it matters.

**vagrant-libvirt rsync excludes `.gitignore` entries by default.** That's usually what you want. When it isn't — for example, syncing `.env` into a lab VM — override `rsync__exclude` explicitly in the Vagrantfile.

**`$HOSTNAME` is a bash interactive variable and not reliably available** in `vagrant ssh -c "..."` invocations. `$(hostname)` runs the `hostname` command every time and always returns the right value.

**Pin Python dependency versions.** Unpinned `fastapi` or `psycopg` in `requirements.txt` means the image rebuilds years later might pull incompatible versions and mysteriously fail. Pinning trades a tiny maintenance cost now for reproducibility forever.
