
## About this project

This is a personal learning project, not production infrastructure. I'm using it to practise DevOps fundamentals, infrastructure as code, containers, reverse proxies, observability, out of interest, and outside of my day job in network security. It's built on a single machine with VMs and runs entirely offline. Expect rough edges, notes-to-self in the docs, and the occasional backtrack as I learn what works, and doesnt work :)



# 3-Tier Web App

Four-VM lab: Nginx load balancer, dual FastAPI app nodes, PostgreSQL. Debian 12 on libvirt/KVM via Vagrant.

| Node  | Role                          | IP          |
|-------|-------------------------------|-------------|
| web01 | Nginx reverse proxy + LB      | 10.10.10.10 |
| app01 | FastAPI instance #1           | 10.10.10.11 |
| app02 | FastAPI instance #2           | 10.10.10.12 |
| db01  | PostgreSQL                    | 10.10.10.20 |

## Bring up

    vagrant up

## Tear down

    vagrant destroy -f

## Documentation

Detailed write-ups for each milestone live in [`docs/`](docs/):

- [01 — Vagrant scaffolding](docs/01-vagrant-scaffolding.md)
- [02 — Docker provisioning](docs/02-docker-provisioning.md)
- [03 — PostgreSQL on db01](docs/03-postgres.md)


## Status

- [x] Four Debian 12 VMs on isolated 10.10.10.0/24 network
- [x] Docker installed on all nodes
- [x ] PostgreSQL on db01
- [ ] FastAPI on app01/app02
- [ ] Nginx reverse proxy + load balancing on web01
