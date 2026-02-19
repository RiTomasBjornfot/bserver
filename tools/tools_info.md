# Tool Scripts Guide

This document explains how to use the shell scripts in `tools/`.

## Prerequisites

- You can run Bash scripts (`bash` is installed).
- You can reach the target server over SSH.
- You have valid SSH authentication for the configured account (SSH key or password).
- Scripts can be run directly if they are executable, or with `bash <script> ...`.

## `tools/cp2server.sh`

Uploads one local file to the server using `scp`.

Default remote destination:
- Host: `SRV-L055-T`
- User: `u93142@sp.se`
- Directory: `/home/u93142@sp.se/servers/hypelignum/indata`

Usage:

```bash
tools/cp2server.sh [-o <save_dir>] <send_file>
```

Examples:

```bash
tools/cp2server.sh ./data/input.csv
tools/cp2server.sh -o /home/u93142@sp.se/servers/hypelignum/indata ./data/input.csv
```

Options:
- `-o <save_dir>`: override the remote destination directory.
- `-h`: print help.

Notes:
- The script creates the remote directory first (`mkdir -p` over SSH).
- It may ask for authentication more than once (one SSH call for directory creation, one SCP call for upload) if key-based auth is not configured.

## `tools/cp2local.sh`

Downloads one file from the server to your local machine using `scp`.

Configured remote endpoint:
- User: `u93142@sp.se`
- Host: `srv-l055-t`
- Port: `22`

Usage:

```bash
tools/cp2local.sh <remote_absolute_path> [-o <local_dir>] [-p]
```

Examples:

```bash
tools/cp2local.sh /home/u93142@sp.se/https_hello/cert.pem
tools/cp2local.sh /var/log/syslog -o ~/Downloads
tools/cp2local.sh /etc/nginx/nginx.conf -o ./backup -p
```

Options:
- `-o <local_dir>`: local destination directory (default: current directory).
- `-p`: preserve remote directory structure under `local_dir`.
- `-h`: print help.

Notes:
- The remote path must be absolute (must start with `/`).
- Without `-p`, only the file is copied into `local_dir`.
- With `-p`, the script recreates the remote path structure locally.

## `tools/ssh_connect.sh`

Opens an interactive SSH session to the server.

Usage:

```bash
tools/ssh_connect.sh
```

Current command:

```bash
ssh U93142@SRV-L055-T
```

## Troubleshooting

- Permission denied (`publickey`): set up an SSH key for the target account, or use password authentication if allowed.
- Host key verification failed: remove/update stale host key entry in `~/.ssh/known_hosts`.
- Connection timeout/refused: verify network access, host name, and SSH port.
