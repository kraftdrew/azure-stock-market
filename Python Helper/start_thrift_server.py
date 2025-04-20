#!/usr/bin/env python3
import os
import socket
import subprocess
import time
import signal


def resolve_spark_prefix():
    """Locate the Spark installation prefix via Homebrew."""
    prefix = subprocess.check_output(["brew", "--prefix", "apache-spark"]).decode().strip()
    return os.path.join(prefix, "libexec")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if host:port is accepting TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def thrift_process_pid(port: int = 10000) -> int | None:
    """Return PID of a running HiveThriftServer2 process listening on the given port, or None if not found."""
    # 1) Try jps lookup
    try:
        output = subprocess.check_output(["jps"], text=True)
        for line in output.splitlines():
            pid_str, name = line.split(maxsplit=1)
            if "HiveThriftServer2" in name:
                return int(pid_str)
    except subprocess.CalledProcessError:
        pass

    # 2) Fallback to lsof on the port
    try:
        pid_str = subprocess.check_output(
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
            text=True
        ).strip()
        return int(pid_str) if pid_str else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def start_thriftserver(port: int = 10000, timeout: int = 60) -> None:
    """
    Start Spark Thrift Server on the given port if not already running.
    Raises RuntimeError on failure.
    """
    if is_port_open("127.0.0.1", port) or thrift_process_pid(port) is not None:
        print(f"Thrift Server already running on port {port}; skipping start.")
        return

    spark_home = resolve_spark_prefix()
    os.environ["SPARK_HOME"] = spark_home
    os.environ["PATH"] = os.path.join(spark_home, "sbin") + os.pathsep + os.environ.get("PATH", "")

    cmd = [
        "start-thriftserver.sh",
        "--master", "local[*]",
        "--hiveconf", f"hive.server2.thrift.port={port}"
    ]
    proc = subprocess.Popen(cmd, env=os.environ)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_open("127.0.0.1", port):
            print(f"✅ Thrift Server started (PID {proc.pid}) and listening on port {port}")
            return
        time.sleep(2)

    proc.terminate()
    raise RuntimeError(f"Thrift Server did not start within {timeout}s on port {port}")


def stop_thriftserver(port: int = 10000, timeout: int = 30) -> None:
    """
    Stop the running Spark Thrift Server on the given port, if any.
    Raises RuntimeError if unable to stop.
    """
    pid = thrift_process_pid(port)
    if pid is None:
        print(f"No Thrift Server process found on port {port}; skipping stop.")
        return

    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if thrift_process_pid(port) is None:
            print(f"✅ Thrift Server (PID {pid}) stopped successfully.")
            return
        time.sleep(1)

    os.kill(pid, signal.SIGKILL)
    print(f"⚠️ Thrift Server (PID {pid}) did not stop gracefully; killed.")

# Module API: start_thriftserver, stop_thriftserver