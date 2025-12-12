# Oracle Diagnostics MCP Server

An MCP (Model Context Protocol) server that provides comprehensive Oracle database diagnostics for query performance analysis. This server connects to Oracle databases and performs systematic diagnostic checks to identify performance issues.

## Features

### Diagnostic Tools

1. **Blocking Sessions Analysis** - Identifies wait chains and blocking sessions
2. **CPU Saturation Analysis** - Analyzes AWR data for CPU bottlenecks during incident windows
3. **SQL Monitoring** - Monitors active sessions and identifies long-running SQL
4. **Long Operations Tracking** - Tracks progress of long-running operations via gv$longops
5. **Parallelism Analysis** - Analyzes Degree of Parallelism (DOP) mismatches and PX resource pressure
6. **Full Table Scan Analysis** - Finds FTS operations that should use parallel execution

## Installation

### Prerequisites

- Python 3.12+
- Access to a Oracle database
- [uv package manager](https://docs.astral.sh/uv/)

### Setup

1. Clone or download this repository
2. Install dependencies:
   ```bash
   uv sync
   ```

## Database Permissions Required

The database user needs access to these views:
- `gv$session`
- `gv$sql`
- `gv$longops`
- `gv$px_session`
- `gv$sql_plan`
- `dba_hist_sysmetric_summary`

### Configuration

Create file named `.env` in the execution directory, containing the following
variables.  Alternatively, export the variables into the shell environment:
```bash
COMPARTMENT_ID="your-oci-compartment-id"
DB_URL="your-oracle-database-host"
DB_USER="your-database-username"
DB_PASSWORD="your-database-password"
```

### Running the Chat Interface

```bash
uv run streamlit run app.py
```

## License

Licensed under the Universal Permissive License (UPL), Version 1.0.

See [LICENSE](./LICENSE.txt) for more details.
