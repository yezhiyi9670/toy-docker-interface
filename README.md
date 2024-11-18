# Simple Docker Interface

This is a toy Python interface to a docker container. Note that it only works with Linux hosts and specific container images.

For usage, check `docker_interface.py` and `test.py`. Mandatory requirements is the `pexpect` package.

## Configuring nested containers

To make nested containers work, the outer container must run in privileged mode. Unfortunately, Docker CLI offers few utilities for altering existing containers. One possible way on non-critical servers is to shut down Docker service and edit the configuration files.

See: https://blog.csdn.net/Enchanter06/article/details/126891141

To eliminate the hassle with systemd and filesystems, we choose `podman`, a rootless and daemonless container engine, as the inner container engine. It has a Docker-compatible interface. To install podman, simply run:

```plain
apt update
apt install podman
```

The `podman` command is nearly identical to `docker`. You may even `alias docker=podman`!
