#!/usr/bin/env python3
"""
Oracle Database Diagnostics MCP Server

This MCP server provides comprehensive diagnostic tools for Oracle database
performance analysis, specifically focused on query slowness issues.
"""

import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import oracledb
from fastmcp import FastMCP


# Initialize FastMCP server
app = FastMCP("oracle-diagnostics")


class OracleDiagnostics:
    """Oracle database diagnostics functionality"""

    def __init__(self):
        load_dotenv()
        self.db_connection = None

    async def _get_db_connection(self) -> oracledb.Connection:
        """Get or create database connection"""
        if self.db_connection is None or self.db_connection.is_healthy() is False:
            # Get connection parameters from environment
            dsn = os.getenv("DB_URL")
            username = os.getenv("DB_USER")
            password = os.getenv("DB_PASSWORD")

            if not all([dsn, username, password]):
                raise ValueError(
                    "Database credentials not provided in environment variables"
                )

            self.db_connection = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: oracledb.connect(user=username, password=password, dsn=dsn),
            )

        return self.db_connection

    async def _execute_query(
        self, query: str, params: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a query and return results as list of dicts"""
        conn = await self._get_db_connection()

        def _execute():
            with conn.cursor() as cursor:
                cursor.execute(query, params or {})
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        return await asyncio.get_event_loop().run_in_executor(None, _execute)


# Initialize diagnostics instance
diagnostics = OracleDiagnostics()


@app.tool()
async def check_blocking_sessions() -> Dict[str, Any]:
    """Check for blocking sessions and wait chains in the database"""
    query = """
    SELECT
        s.sid,
        s.serial#,
        s.username,
        s.program,
        s.machine,
        s.sql_id,
        s.event,
        s.wait_class,
        s.seconds_in_wait,
        s.blocking_session,
        s.final_blocking_session
    FROM
        gv$session s
    WHERE
        s.wait_class != 'Idle'
        AND (s.blocking_session IS NOT NULL OR s.final_blocking_session IS NOT NULL)
    ORDER BY
        s.seconds_in_wait DESC
    """

    results = await diagnostics._execute_query(query)

    return {
        "timestamp": datetime.now().isoformat(),
        "blocking_sessions": results,
        "total_blocked": len(results),
    }


@app.tool()
async def check_cpu_saturation(start_time: str, end_time: str) -> Dict[str, Any]:
    """Generate CPU saturation analysis using AWR data for incident window"""
    query = """
    SELECT
        snap_id,
        begin_interval_time,
        end_interval_time,
        value as cpu_usage_percent
    FROM
        dba_hist_sysmetric_summary
    WHERE
        metric_name = 'Host CPU Utilization (%)'
        AND begin_interval_time >= TO_DATE(:start_time, 'YYYY-MM-DD HH24:MI:SS')
        AND end_interval_time <= TO_DATE(:end_time, 'YYYY-MM-DD HH24:MI:SS')
    ORDER BY
        begin_interval_time
    """

    params = {"start_time": start_time, "end_time": end_time}
    results = await diagnostics._execute_query(query, params)

    if results:
        cpu_values = [r["CPU_USAGE_PERCENT"] for r in results]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        peak_cpu = max(cpu_values)
    else:
        avg_cpu = peak_cpu = 0

    return {
        "analysis_period": {"start": start_time, "end": end_time},
        "average_cpu_percent": round(avg_cpu, 1),
        "peak_cpu_percent": round(peak_cpu, 1),
        "is_cpu_bottleneck": avg_cpu > 80,
        "data_points": len(results),
    }


@app.tool()
async def sql_monitoring(session_id: Optional[int] = None) -> Dict[str, Any]:
    """Monitor active sessions and identify long-running/critical SQL"""
    base_query = """
    SELECT
        s.sid,
        s.serial#,
        s.username,
        s.sql_id,
        s.last_call_et,
        s.event,
        s.wait_class,
        s.seconds_in_wait,
        t.elapsed_time,
        t.buffer_gets
    FROM
        gv$session s
    LEFT JOIN
        gv$sql t ON s.sql_id = t.sql_id
    WHERE
        s.status = 'ACTIVE'
        AND s.wait_class != 'Idle'
    """

    if session_id:
        base_query += " AND s.sid = :session_id"

    params = {"session_id": session_id} if session_id else None
    results = await diagnostics._execute_query(base_query, params)

    long_running = [r for r in results if r.get("LAST_CALL_ET", 0) > 300]

    return {
        "active_sessions": len(results),
        "long_running_sessions": len(long_running),
        # Limit output
        "session_details": results[:10] if len(results) > 10 else results,
        "session_filter": f"sid={session_id}" if session_id else "all",
    }


@app.tool()
async def long_operations() -> Dict[str, Any]:
    """Track long operations via gv$longops"""
    query = """
    SELECT
        sid,
        opname,
        target,
        sofar,
        totalwork,
        elapsed_seconds,
        sql_id
    FROM
        v$session_longops
    WHERE
        totalwork > 0
        AND sofar < totalwork
    ORDER BY
        elapsed_seconds DESC
    """

    results = await diagnostics._execute_query(query)

    for row in results:
        if row["TOTALWORK"] and row["TOTALWORK"] > 0:
            row["progress_percent"] = round((row["SOFAR"] / row["TOTALWORK"]) * 100, 1)

    return {"operations": results, "total_count": len(results)}


@app.tool()
async def parallelism_analysis() -> Dict[str, Any]:
    """Analyze Degree of Parallelism (DOP) requested vs granted and PX resource pressure"""
    query = """
    SELECT
        s.sid,
        s.sql_id,
        px.req_degree,
        px.degree,
        s.seconds_in_wait
    FROM
        gv$session s
    JOIN
        gv$px_session px ON s.sid = px.sid
    WHERE
        s.wait_class = 'Parallel Execution'
    ORDER BY
        s.seconds_in_wait DESC
    """

    results = await diagnostics._execute_query(query)

    dop_mismatches = []
    high_wait_sessions = 0

    for row in results:
        req_degree = row.get("REQ_DEGREE", 0)
        actual_degree = row.get("DEGREE", 0)

        if req_degree != actual_degree and req_degree > 0:
            dop_mismatches.append(
                {
                    "sid": row["SID"],
                    "sql_id": row["SQL_ID"],
                    "requested": req_degree,
                    "granted": actual_degree,
                }
            )

        if row.get("SECONDS_IN_WAIT", 0) > 60:
            high_wait_sessions += 1

    return {
        "parallel_sessions": len(results),
        "dop_mismatches": dop_mismatches,
        "high_wait_sessions": high_wait_sessions,
    }


@app.tool()
async def parallelism_full_scans() -> Dict[str, Any]:
    """Find Full Table Scans without Parallel Execution where PX is expected"""
    query = """
    SELECT
        s.sid,
        s.sql_id,
        p.object_name,
        p.cost,
        p.cardinality
    FROM
        gv$session s
    JOIN
        gv$sql_plan p ON s.sql_id = p.sql_id AND s.child_number = p.child_number
    WHERE
        p.operation = 'TABLE ACCESS'
        AND p.options = 'FULL'
        AND s.sql_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM gv$px_session px
            WHERE px.sid = s.sid
        )
    ORDER BY
        p.cost DESC
    """

    results = await diagnostics._execute_query(query)

    px_candidates = [
        {"sid": r["SID"], "sql_id": r["SQL_ID"], "table": r["OBJECT_NAME"]}
        for r in results
        if r.get("COST", 0) > 10000 or r.get("CARDINALITY", 0) > 100000
    ]

    return {"full_table_scans": len(results), "px_candidates": px_candidates}


def main():
    """Main entry point"""
    app.run("stdio")


if __name__ == "__main__":
    main()
