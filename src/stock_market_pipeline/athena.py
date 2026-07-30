from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any


class AthenaQueryError(RuntimeError):
    pass


def run_query(
    client: Any,
    query: str,
    *,
    database: str,
    workgroup: str,
    timeout_seconds: int = 180,
) -> list[list[str | None]]:
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database, "Catalog": "AwsDataCatalog"},
        WorkGroup=workgroup,
    )
    query_id = response["QueryExecutionId"]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        execution = client.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state == "SUCCEEDED":
            return list(_read_rows(client, query_id))
        if state in {"FAILED", "CANCELLED"}:
            reason = execution["Status"].get("StateChangeReason", state)
            raise AthenaQueryError(f"Athena query {query_id} {state}: {reason}")
        time.sleep(1)
    client.stop_query_execution(QueryExecutionId=query_id)
    raise TimeoutError(f"Athena query {query_id} exceeded {timeout_seconds}s")


def _read_rows(client: Any, query_id: str) -> Iterable[list[str | None]]:
    paginator = client.get_paginator("get_query_results")
    first_row = True
    for page in paginator.paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            if first_row:
                first_row = False
                continue
            yield [item.get("VarCharValue") for item in row["Data"]]
