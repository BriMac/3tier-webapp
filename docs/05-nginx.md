# Milestone 5 — Nginx reverse proxy and load balancer on web01

## Goal

Place Nginx in front of both app nodes so external clients hit a single address (`http://10.10.10.10`) and Nginx distributes requests across app01 and app02. The load balancer must detect when a backend is unhealthy and route around it transparently, so one app node going down doesn't take the whole service with it.

## What was built

### File layout

    nginx/
    ├── docker-compose.yml    # how to run the container
    └── nginx.conf            # routing, balancing, logging config

No `.env` file — the upstream addresses aren't secret, they're architecture.

### nginx.conf

Core pieces of the config:

**Upstream pool:**

    upstream app_backend {
        least_conn;
        server 10.10.10.11:8000 max_fails=3 fail_timeout=10s;
        server 10.10.10.12:8000 max_fails=3 fail_timeout=10s;
    }

- `least_conn` routes each request to the backend with the fewest active connections. Better than round-robin when requests have varying duration.
- `max_fails=3 fail_timeout=10s` means after 3 consecutive failures, Nginx removes the backend from the pool for 10 seconds before trying it again.

**Custom log format to make load balancing observable:**

    log_format upstreamlog '$remote_addr - $remote_user [$time_local] '
                            '"$request" $status $body_bytes_sent '
                            '"$http_referer" "$http_user_agent" '
                            'upstream=$upstream_addr';

The `upstream=$upstream_addr` suffix at the end of every log line shows which backend actually served the request. Without this, there's no way to prove load balancing is happening.

**Proxy headers to preserve original client info:**

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

Without these, the FastAPI app would see Nginx's container IP as the client IP. These headers preserve the real information so application logs and any future per-client logic work correctly.

**Timeouts:**

    proxy_connect_timeout 5s;
    proxy_send_timeout    30s;
    proxy_read_timeout    30s;

Prevents a slow or dead backend from holding an Nginx worker open indefinitely. The 5-second connect timeout is what bounds the worst-case delay when a backend has just died — Nginx waits at most 5 seconds before trying the next one.

**Local health endpoint:**

    location = /nginx_health {
        access_log off;
        return 200 "nginx ok\n";
    }

Cheap liveness probe that doesn't hit the backends. Useful for Docker healthchecks and external monitoring.

### docker-compose.yml

- Uses `nginx:1.27-alpine` — small official image, no custom build needed.
- Mounts `nginx.conf` read-only.
- Healthcheck uses `wget` hitting `/nginx_health`.

## How to run it

    vagrant ssh web01 -c "cd /vagrant/nginx && docker compose up -d"
    vagrant ssh web01 -c "docker ps"

Container should report `(healthy)` within ~20 seconds.

## Evidence of correctness

### 1. Requests are spread across both app nodes

    for i in $(seq 1 100); do curl -s http://10.10.10.10/whoami; echo; done | sort | uniq -c

Expected output:

         50 {"host":"app01"}
         50 {"host":"app02"}

**Why this proves something:** 100 requests hitting Nginx on web01 resulted in 50 being served by each backend. The 50/50 split confirms `least_conn` is distributing traffic correctly and neither backend is being starved or preferred.

### 2. Failover works when a backend dies

Stop app01's container:

    vagrant ssh app01 -c "docker stop app"

Run the curl loop again:

    for i in $(seq 1 20); do curl -s http://10.10.10.10/whoami; echo; done

All 20 responses come back as `{"host":"app02"}`. No error, no partial failure, no visible delay to the client.

**Why this proves something:** Nginx detected app01 was unreachable, removed it from the upstream pool, and silently routed every subsequent request to app02. The service stayed up despite losing half the application tier. This is what "high availability at the app tier" actually means in practice.

### 3. Recovery is automatic

Restart app01:

    vagrant ssh app01 -c "docker start app"

Wait 10 seconds (the `fail_timeout` window), then re-run the loop. Responses now alternate between app01 and app02 again.

**Why this proves something:** Nginx doesn't need to be told a backend has recovered. After the fail_timeout window, it tentatively tries the dead backend again; if that succeeds, the backend rejoins the pool. Zero operator intervention required.

### 4. Which backend served each request is visible in the logs

    vagrant ssh web01 -c "docker logs nginx 2>&1 | grep -oP 'upstream=\K[^ ]+' | sort | uniq -c"

Counts the number of requests served by each upstream IP across the entire log history.

**Why this proves something:** the `upstreamlog` format makes the balancing auditable. In a real incident, this is the kind of log analysis that tells you whether traffic was distributed as expected.

## Failure modes and what they'd look like

- **`Bad Gateway` (HTTP 502) from curl** — both backends down or network unreachable. `docker ps` inside each app node will show container status.
- **All requests go to one backend** — the other was marked dead. Check `docker logs nginx` for connection errors. Confirm the missing backend's container is running and port 8000 is accessible.
- **Nginx container unhealthy** — typo or syntax error in `nginx.conf`. `docker logs nginx` shows the parse error on startup; `nginx -t` inside the container validates the config.
- **High latency before failover** — happens when a backend hangs rather than refusing connections. `proxy_connect_timeout` bounds the wait; consider lowering it if quicker failover matters.

## Lessons learned

**`least_conn` is usually the right default.** Round-robin is the classic demo but misbehaves when request durations vary — a slow request to app01 doesn't slow down new requests being sent there. `least_conn` naturally steers around hotspots.

**`max_fails` + `fail_timeout` do the right thing without any active health checks.** Nginx's open-source version doesn't do active polling (that's a Plus feature). Passive health checks — observing whether requests succeed — are good enough for most situations and free.

**Logging the upstream is what makes load balancing observable.** Without the `$upstream_addr` field in the log format, you're left inferring behaviour from application-side logs. Putting it at the proxy layer means the evidence is one `grep` away.

**Docker healthchecks and upstream health checks are different things.** The Compose healthcheck confirms Nginx itself is alive. The `max_fails` config controls Nginx's view of the backends. Both are necessary; neither replaces the other.

**Headers matter more than they seem.** Without `X-Real-IP` / `X-Forwarded-For`, the app sees every request as coming from the Nginx container's IP. Logs get useless, IP-based rate limiting breaks, geolocation breaks. These two lines of config save a lot of grief later.
