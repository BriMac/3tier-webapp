# Milestone 1 — Vagrant scaffolding

## Goal

Provision four Debian 12 VMs on an isolated private network using Vagrant and libvirt/KVM, with the topology fully defined in code so the lab is reproducible from git.

## Topology

| Node  | Role                     | IP            |
|-------|--------------------------|---------------|
| web01 | Nginx reverse proxy + LB | 10.10.10.10   |
| app01 | FastAPI instance #1      | 10.10.10.11   |
| app02 | FastAPI instance #2      | 10.10.10.12   |
| db01  | PostgreSQL               | 10.10.10.20   |

## Network design decisions

**Two networks per VM.** Vagrant always attaches a NAT interface (192.168.121.0/24 by default) for its own SSH access. This is vagrant-libvirt's management network and can't be disabled. The 10.10.10.0/24 network is a second interface defined explicitly in the Vagrantfile — this is what the app tiers use to talk to each other.

**10.10.10.0/24 was chosen** to avoid overlap with the home LAN (192.168.1.0/24). 192.168.56.0/24 would also have worked but 10.10.10.0/24 is more obviously "lab" at a glance.

**Private host-only network.** No bridging, no DHCP from the home router. Fully self-contained. The lab works identically at home, on the road, or offline.

## Host prerequisites (CachyOS)

Install these packages on the CachyOS host before anything else. They provide the virtualisation stack (KVM/QEMU), the management daemon (libvirt), and the GUI (virt-manager) for inspecting VMs.

    sudo pacman -S vagrant libvirt qemu-full virt-install dnsmasq virt-manager

Enable the libvirt daemon so it starts on boot and right now:

    sudo systemctl enable --now libvirtd

Add your user to the libvirt and kvm groups so you can manage VMs without sudo. Group changes only apply on new login sessions, so log out and back in (or reboot) after this command:

    sudo usermod -aG libvirt,kvm $USER

Install the Vagrant plugin that lets Vagrant talk to libvirt:

    vagrant plugin install vagrant-libvirt

Notes on CachyOS specifics:

- `vagrant` itself lives in the AUR, not the main repos. If `pacman` can't find it, install via `paru -S vagrant`.
- `ebtables` and `bridge-utils` don't exist on current CachyOS. Drop them from any tutorial that mentions them. They've been replaced by `iptables-nft` and `iproute2`, both already installed.

## Troubleshooting notes

**`virsh list --all` returns nothing despite VMs running.** Libvirt has two separate daemons — session (per-user) and system (root). Vagrant creates VMs in the system daemon, but `virsh` defaults to session mode for non-root users. Fix by setting the default URI:

    export LIBVIRT_DEFAULT_URI=qemu:///system

Add that line to `~/.bashrc` (or `~/.zshrc`) to make it permanent.

**VMs stuck on "Waiting for domain to get an IP address..."** Usually a firewall blocking DHCP on the libvirt bridge. On CachyOS, `ufw` can be installed and active without an obvious indicator. Stop and disable it:

    sudo systemctl stop ufw
    sudo systemctl disable ufw

**`[fog][WARNING] Unrecognized arguments: libvirt_ip_command`** — cosmetic warning from the vagrant-libvirt plugin. Harmless, ignore.

**Group membership didn't take effect after `usermod`.** Group changes only apply to new login sessions, not your current shell. Either log out of the desktop session entirely or reboot.

## How to verify it works

After `vagrant up` completes, four checks confirm the lab is healthy.

Check all four VMs are running:

    vagrant status

All four should show `running`.

Check the private network is wired up:

    vagrant ssh web01 -c "ping -c 2 10.10.10.11"
    vagrant ssh app01 -c "ping -c 2 10.10.10.20"
    vagrant ssh app02 -c "ping -c 2 10.10.10.10"

All three pings must succeed. If any fail, the private network isn't working and no Docker or application work will succeed on top of it.
