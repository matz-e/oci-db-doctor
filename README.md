# MCP DB Doctor

A small demo of an MCP server to run diagnostic queries against a Oracle database.

## Features

### Diagnostic Tools

1. **Blocking Sessions Analysis** - Identifies wait chains and blocking sessions
4. **Long Operations Tracking** - Tracks progress of long-running operations via `gv$longops`

## Installation

### Prerequisites

- Python 3.12+
- Access to a Oracle database
- [uv package manager](https://docs.astral.sh/uv/)
- [NPM](https://www.npmjs.com/) to inspect the MCP server

### Setup

1. Clone or download this repository.
2. Install dependencies:
   ```bash
   uv sync
   ```

## Database Permissions Required

The database user needs access to these views:
- `gv$session`
- `v$session_longops`

### Configuration

Create file named `.env` in the execution directory, containing the following
variables.  Alternatively, export the variables into the shell environment:
```bash
COMPARTMENT_ID="your-oci-compartment-id"
DB_URL="your-oracle-database-host"
DB_USER="your-database-username"
DB_PASSWORD="your-database-password"
```

### Testing the MCP server

First run the MCP server with the `DB_*` variables from above configured:
```bash
uv run python -m oci_db_doctor
```
Make a note of the connection URL printed, e.g., `http://127.0.0.1:8000`.

Then connect using the MCP inspector:
```bash
npx @modelcontextprotocol/inspector
```
This may ask to install the corresponding package on first use.  The interface
then should open directly in your browser window.

To connect to the MCP server started in the first step, select "Streamable
HTTP" as the transport, then enter the URL (`http://127.0.0.1:8000` in the
example above).  Click the "Connect" button.  Once connected, explore the
provided tools in the "Tool" tab - the tools will appear as soon as "List
Tools" is executed.

### Running the Chat Interface

A small chat interface to test the agent can be executed with:
```bash
uv run streamlit run app.py
```

### Testing for blocking and long-running sessions

To re-create scenarios with blocking and long-running sessions, this repository
contains a few scripts in [`fault_scripts`](./fault_scripts).  These scripts
use the same environment variables as outlined above to connect to the
database.

First set up a `test_table` in a connected database (dedicated to testing purposes):
```bash
uv run python fault_scripts/create_test_table.py --range 10000000
```
where the `--range` argument will create 10 million rows - if the long running
sessions test script does not run sufficiently long, one may append another 10
million rows:
```bash
uv run python fault_scripts/create_test_table.py --no-create --range 10000000
```

#### Introducing blocking sessions

To create one or multiple blocking sessions, first execute the blocking script,
instructing it to not commit the transaction:
```bash
uv run python fault_scripts/blocking.py --wait "First update"
```
Then, in a different shell, run one or more concurrent edits of the same row:
```bash
uv run python fault_scripts/blocking.py "Second update"
```
(execute this command multiple times to create more than one blocked session)

Now the MCP tool and agent should both report the presence of blocking SQL
sessions.

#### Long-running sessions

Run the following script to have both the MCP tool and agent pick up on long
running sessions:
```bash
uv run python fault_scripts/long_running.py
```
If the script terminates too early, append more rows to the test table as
described above.

## License

Licensed under the Universal Permissive License (UPL), Version 1.0.

See [LICENSE](./LICENSE.txt) for more details.
