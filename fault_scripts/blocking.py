import oracledb
import os
import time

from argparse import ArgumentParser
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

dsn = os.getenv("DB_URL")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

canary = Path("DONE")

parser = ArgumentParser()
parser.add_argument("--wait", action="store_true")
parser.add_argument("description", type=str)
args = parser.parse_args()

with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE test_table
            SET description = :new_desc
            WHERE id = 1;
            """,
            new_desc=args.description,
        )
        if args.wait:
            count = 0
            while not canary.exists() and count < 500:
                time.sleep(1)
                count += 1
