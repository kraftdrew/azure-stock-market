#!/usr/bin/env python3
import os
import socket
import subprocess
import time
import signal

# ──────────────────────────────────────────────────────────────────────────────
# 🛠  Adjust these to your repo root:
root_path       = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market"
metastore_path  = f"{root_path}/metastore_db"
warehouse_path  = f"{root_path}/spark-warehouse"
# ──────────────────────────────────────────────────────────────────────────────

def resolve_spark_prefix() -> str:
    prefix = (
        subprocess.check_output(["brew", "--prefix", "apache-spark"])
                  .decode()
                  .strip()
    )
    return os.path.join(prefix, "libexec")

def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0

def thrift_process_pid(port: int = 10000) -> int | None:
    # try jps first
    try:
        out = subprocess.check_output(["jps"], text=True)
        for line in out.splitlines():
            pid, name = line.split(maxsplit=1)
            if "HiveThriftServer2" in name:
                return int(pid)
    except subprocess.CalledProcessError:
        pass
    # fallback to lsof
    try:
        pid = subprocess.check_output(
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
            text=True
        ).strip()
        return int(pid) if pid else None
    except Exception:
        return None

def start_thriftserver(
    port: int = 10000,
    timeout: int = 60
) -> None:
    # if already up, skip
    if is_port_open("127.0.0.1", port) or thrift_process_pid(port):
        print(f"▶️  Thrift Server already listening on port {port}")
        return

    # set SPARK_HOME & PATH
    spark_home = resolve_spark_prefix()
    os.environ["SPARK_HOME"] = spark_home
    os.environ["PATH"] = os.path.join(spark_home, "sbin") + os.pathsep + os.environ.get("PATH", "")

    # build the command with shared metastore & warehouse
    cmd = [
        "start-thriftserver.sh",
        "--master", "local[*]",
        # use the Hive (Derby) catalog
        "--conf", f"spark.sql.catalogImplementation=hive",
        # point managed tables at your project folder
        "--conf", f"spark.sql.warehouse.dir={warehouse_path}",
        "--conf", f"hive.metastore.warehouse.dir={warehouse_path}",
        # point Derby at your project’s metastore_db
        "--conf", f"javax.jdo.option.ConnectionURL=jdbc:derby:{metastore_path};create=true",
        "--hiveconf", f"hive.server2.thrift.port={port}"
    ]

    # launch it
    proc = subprocess.Popen(cmd, env=os.environ)

    # wait for the port to open
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_open("127.0.0.1", port):
            print(f"✅  Thrift Server started (PID {proc.pid}) on port {port}")
            return
        time.sleep(1)

    proc.terminate()
    raise RuntimeError(f"❌  Thrift Server failed to start on port {port} within {timeout}s")

def stop_thriftserver(port: int = 10000, timeout: int = 30) -> None:
    pid = thrift_process_pid(port)
    if not pid:
        print(f"ℹ️  No Thrift Server listening on port {port}; skipping stop")
        return

    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not thrift_process_pid(port):
            print(f"✅  Thrift Server (PID {pid}) stopped cleanly")
            return
        time.sleep(1)

    os.kill(pid, signal.SIGKILL)
    print(f"⚠️  Thrift Server (PID {pid}) didn’t stop gracefully; killed")

# Now you can import these functions from your script:
#
#   from start_thrift_server import start_thriftserver, stop_thriftserver
#
# and call them in your workflow:
#
#   start_thriftserver()
#   … run your notebook queries …
#   stop_thriftserver()

stop_thriftserver()