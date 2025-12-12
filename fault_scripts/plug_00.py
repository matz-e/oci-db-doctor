import oracledb
import os

from argparse import ArgumentParser
from dotenv import load_dotenv


load_dotenv()

dsn = os.getenv("DB_URL")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")


parser = ArgumentParser()
parser.add_argument("--no-create", action="store_false", dest="create", default=True)
parser.add_argument("--range", type=int, default=10_000)
args = parser.parse_args()

with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
    with conn.cursor() as cursor:
        if args.create:
            cursor.execute(
                """
                CREATE TABLE test_table (
                  id NUMBER PRIMARY KEY,
                  description VARCHAR2(100)
                );
                """
            )

        cursor.execute("SELECT MAX(id) FROM test_table")
        last_id = cursor.fetchone()[0]

        cursor.executemany(
            """
            INSERT INTO test_table (id, description) VALUES (:row_id, :row_value);
            """,
            [
                (last_id + n + 1, f"Initial Value for row {last_id + n + 1}")
                for n in range(args.range)
            ],
        )
        conn.commit()
