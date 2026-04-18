# Milestone 3 — PostgreSQL on db01

## Goal

Run PostgreSQL 16 as a Docker container on db01, with persistent storage, an initial schema applied on first boot, credentials kept out of git, and the database reachable from the app tier over the 10.10.10.0/24 private network.

## What was built

### File layout

    db/
    ├── docker-compose.yml    # service definition
    ├── init.sql              # schema, runs on first container boot
    ├── .env                  # real credentials (git-ignored)
    └── .env.example          # template, committed

### docker-compose.yml

Defines one service, `postgres`, using the official `postgres:16` image. Key settings:

- `restart: unless-stopped` — if the container or VM reboots, Docker brings it back automatically
- `ports: "5432:5432"` — exposes Postgres on the VM's IP so other VMs can connect
- `volumes: pgdata:/var/lib/postgresql/data` — named volume for persistent storage, survives container deletion
- `volumes: ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro` — mounts the schema script into Postgres's init-hook directory, so it runs once on first boot
- `healthcheck` using `pg_isready` — gives Docker a signal when the database is actually accepting connections, not just when the process is up

### init.sql

Minimal schema for the app tier to use later:

    CREATE TABLE IF NOT EXISTS items (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    INSERT INTO items (name) VALUES ('hello'), ('world');

### Environment files

- `.env` contains real credentials (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) and is ignored by git via the root `.gitignore`
- `.env.example` is committed with placeholder values as a template for anyone cloning the repo

### Vagrantfile change

Added a synced folder so the project directory is accessible inside each VM at `/vagrant`:

    config.vm.synced_folder ".", "/vagrant", type: "rsync"

## How to verify it works

Inside db01, bring Postgres up:

    vagrant ssh db01
    cd /vagrant/db
    docker compose up -d

Check the container is healthy:

    docker ps

`STATUS` should show `Up X seconds (healthy)` within 30 seconds. If it says `(health: starting)` for more than a minute, the init script or healthcheck has a problem.

Verify the schema and seed data are in place:

    docker exec -it postgres psql -U appuser -d appdb -c "SELECT * FROM items;"

Two rows should come back: "hello" and "world".

From app01, prove the database is reachable across the private network:

    vagrant ssh app01 -c "docker run --rm -e PGPASSWORD=changeme-locally postgres:16 psql -h 10.10.10.20 -U appuser -d appdb -c 'SELECT count(*) FROM items;'"

Should return a count of 2.

## Lessons learned

**`synced_folder` doesn't apply to running VMs.** The share in the Vagrantfile only wires up at VM creation or reload time. Adding the line to an existing Vagrantfile and running `vagrant rsync` does nothing until the VM has the share configured in its runtime state. Fix: `vagrant reload` re-reads the Vagrantfile and applies the share.

**General rule:** Vagrantfile changes to `synced_folder`, networks, or provider config need a `reload` (or a fresh `up --provision`) to take effect. Changes inside provisioners apply on next `vagrant provision`.

**vagrant-libvirt doesn't enable a shared folder by default**, unlike the VirtualBox provider which auto-mounts `/vagrant`. Rsync is one option (one-way, host → VM, manual sync on change). NFS is the other (two-way, live, more setup). Rsync is fine for this project because files are only edited on the host, never on the guests.

**`$PGPASSWORD` env var** is the clean way to pass a Postgres password to non-interactive `psql`. Otherwise `psql` prompts, which breaks in scripts and `docker run` commands.

## Failure modes and what they'd look like

- **`cd /vagrant/db: No such file or directory`** — synced_folder isn't applied. `vagrant reload`.
- **Container stuck on `(health: starting)`** — init script likely has a syntax error. Check `docker logs postgres` inside db01.
- **`psql: connection refused`** from app01 — either Postgres isn't listening on 0.0.0.0, or the firewall inside db01 is blocking port 5432. Check `docker ps` shows `0.0.0.0:5432->5432/tcp`.
- **Authentication failed** — the env vars in `.env` don't match the credentials being passed in the psql command. Check `db/.env` on the host and what you're passing in the client.
