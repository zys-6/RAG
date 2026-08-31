# 36 - `jj` XRDP And Offline VM Notes

This note records workstation-side issues discovered during the August 6, 2026 offline GPU rehearsal on `jj-ThinkStation-P2-Tower`.

It is not part of the target-host migration procedure. Its purpose is to preserve the local troubleshooting facts that made the offline VM test reproducible.

---

## 1. XRDP User Separation

Observed behavior:

- XRDP login as the normal workstation user `jj` authenticated successfully
- `xorgxrdp` started correctly
- the session then exited immediately because the window manager returned exit code `1`

The reliable workaround was to use a separate XRDP user:

```bash
sudo adduser jj-rdp
sudo usermod -aG sudo jj-rdp
sudo -u jj-rdp bash -lc 'printf "%s\n" xfce4-session > ~/.xsession'
sudo chown jj-rdp:jj-rdp /home/jj-rdp/.xsession
sudo systemctl restart xrdp xrdp-sesman
```

Why this helped:

- `jj` already had an active desktop history, XFCE session state, and user-specific startup/cache files
- `jj-rdp` started with a clean home directory and a minimal `~/.xsession`
- XRDP could therefore start a clean Xorg + XFCE session without colliding with the existing `jj` desktop state

Practical rule:

- XRDP does not always require a separate user
- but on this workstation, a dedicated XRDP account was the most reliable choice

---

## 2. Why Two `jj` Accounts Appeared On The Login Screen

This happened because the new account `jj-rdp` was created with the full name `jj`.

The display manager may show full names instead of raw usernames, so both entries appeared as `jj`.

To distinguish them clearly:

```bash
sudo chfn -f "jj Remote" jj-rdp
```

---

## 3. Libvirt And `virt-manager` Access

`virt-manager` initially showed:

- `QEMU/KVM - Not Connected`

The practical access pattern was:

- run `virt-manager` with elevated access when needed, or
- add the XRDP user to `libvirt` and `kvm` and then re-login

Command:

```bash
sudo usermod -aG libvirt,kvm jj-rdp
```

After group changes, fully log out and back in before retrying `virt-manager`.

---

## 4. Valid Offline VM Constraint

The first VM rehearsal was not a valid offline proof even though the installer UI was told not to connect to the internet.

Reason:

- the desktop installer still attempted to download packages from `archive.ubuntu.com` and `security.ubuntu.com`

What a valid offline rehearsal required:

- create the VM with no NIC using `--network none`
- complete the install
- disable `ubuntu.sources` inside the VM before testing the local repo

Commands used after installation:

```bash
sudo mv /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.disabled
sudo rm -f /etc/apt/sources.list.d/offline-gpu-local.list
sudo apt-get update
apt-cache policy
```

Valid offline baseline:

- `ip route` empty
- `apt-cache policy` showed only `/var/lib/dpkg/status`

---

## 5. Verified Offline Repo Result

After copying `offline-repo-noble-gpu-min.tar` into the VM and extracting it under `/opt`, the following worked:

```bash
printf '%s\n' 'deb [trusted=yes] file:/opt/offline-repo-noble-gpu-min ./' | sudo tee /etc/apt/sources.list.d/offline-gpu-local.list
sudo apt-get update
sudo apt-get install -y openssh-server openssh-client openssh-sftp-server
sudo apt-cache policy openssh-server openssh-client openssh-sftp-server
```

The result showed the SSH packages coming from:

- `file:/opt/offline-repo-noble-gpu-min ./ Packages`

This verified that the refreshed tar was sufficient for the offline SSH path.

---

## 6. Checksum Path Caveat

The copied `offline-repo-noble-gpu-min.tar.sha256` file contained the source-host path:

- `/home/jj/offline-repo-noble-gpu-min.tar`

On another machine or inside the VM, `sha256sum -c` failed because that absolute path did not exist.

The correct interpretation:

- the tar itself may still be valid
- compare the hash value directly, or
- regenerate a local checksum file on the receiving machine
