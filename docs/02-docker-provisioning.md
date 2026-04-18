# Milestone 2 — Docker provisioning

## Goal

Install Docker Engine and the Compose plugin identically on all four VMs, in a way that is reproducible from git. Anyone cloning the repo should be able to run `vagrant up` and end up with a working four-node Docker lab with no manual steps.

## What we built

### The provisioning script (`provision/install-docker.sh`)

1. **Idempotency check** — `if command -v docker ...` at the top. If Docker is already installed, the script exits immediately. This matters because `vagrant provision` can be run multiple times, and we don't want a full reinstall every run.

2. **`set -euo pipefail`** — safety line at the top of every decent bash script.
   - `-e` exits on any error
   - `-u` errors on undefined variables
   - `-o pipefail` catches errors in the middle of pipelines

   Without this, a failing step can be silently ignored and the script appears to succeed with a broken install.O

3. **Prerequisites** (`apt-get install ca-certificates curl gnupg lsb-release`) — packages needed to fetch Docker's repo and verify its signature.

4. **GPG key for Docker's repo** — downloads Docker's public signing key, dearmors it (ASCII to binary), stores it in `/etc/apt/keyrings/`. This is the modern apt way. Older tutorials use `apt-key add`, which is deprecated.

5. **Adding Docker's apt repo** — writes a `.list` file telling apt to also check Docker's URL and to trust packages signed with the key. `$(lsb_release -cs)` dynamically inserts `bookworm` (Debian 12's codename), so the script works on other Debian versions too.

6. **Installing the packages**
   - `docker-ce` — the engine
   - `docker-ce-cli` — the `docker` command
   - `containerd.io` — the container runtime Docker sits on top of
   - `docker-buildx-plugin` — for building images
   - `docker-compose-plugin` — modern Compose, invoked as `docker compose` (not the legacy `docker-compose` Python binary)

7. **`usermod -aG docker vagrant`** — adds the `vagrant` user to the `docker` group. Without this, every docker command needs `sudo`. With it, `vagrant ssh` into the VM lets you run `docker ps` as a normal user.

8. **`systemctl enable --now docker`** — starts the Docker daemon now and configures it to start on every boot.

### The Vagrantfile hook

```ruby
node.vm.provision "shell", path: "provision/install-docker.sh"
```

This tells Vagrant: "after each VM boots, run this script inside it as root." Vagrant automatically shares the project directory into the VM, so the script is accessible. It runs once on first boot, and only runs again when you explicitly invoke `vagrant provision` or `vagrant up --provision`.

## How to verify it works

| Check | Command | What it proves |
|---|---|---|
| Script ran on each VM | Watch `vagrant provision` for `==> Docker installed on <hostname>` on all four | The shell script executed, didn't exit early on error, reached the success echo |
| Docker binary exists | `vagrant ssh web01 -c "docker --version"` (and app01/app02/db01) | The `docker` CLI is installed and on PATH |
| Compose plugin exists | `docker compose version` on each VM | v2 Compose plugin is installed, not the old Python `docker-compose` |
| Vagrant user has Docker access | `vagrant ssh app01 -c "docker ps"` | The `docker` group membership took effect. Without it, the socket is unreachable and `docker ps` returns "permission denied" |
| End-to-end image pull + run | `vagrant ssh app01 -c "docker run --rm hello-world"` | Daemon running, container DNS working, image pulled from Docker Hub, container executed and cleaned up |

## Failure modes and what they'd look like

- **Docker not installed at all** → `bash: docker: command not found`
- **Docker installed but daemon not running** → `docker --version` works, but `docker ps` gives "Cannot connect to the Docker daemon"
- **Compose plugin not installed** → `docker --version` works, but `docker compose version` gives "docker: 'compose' is not a docker command"
- **Group membership didn't apply** → `docker ps` gives "permission denied"

## Lessons learned

- Vagrant's `vagrant provision` only runs provisioners on VMs that already exist. Don't confuse with `vagrant up --provision`.
- Pasting Ruby or YAML directly into the bash prompt will produce dozens of errors and damage nothing. The shell just doesn't know what to do with it.
- `heredoc` syntax (`cat > file <<'EOF' ... EOF`) is bash-specific. Fish shell errors on it. When in doubt, use `nano` or `vim` to write the file instead.
