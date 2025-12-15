"""
Small MCP server to demonstrate the capabilities of debugging databases.

For full usage, this requires a connection with a user that can access the following views/tables:
* `GV$SESSION`
* `V$SESSION_LONGOPS`
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
async def long_operations() -> Dict[str, Any]:
    """Track long operations via v$session_longops"""
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


if __name__ == "__main__":
    # Can be invoked with `python -m oci_db_doctor.server`
    app.run()
