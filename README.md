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

## Status

- [x] Four Debian 12 VMs on isolated 10.10.10.0/24 network
- [x] Docker installed on all nodes
- [ ] PostgreSQL on db01
- [ ] FastAPI on app01/app02
- [ ] Nginx reverse proxy + load balancing on web01
