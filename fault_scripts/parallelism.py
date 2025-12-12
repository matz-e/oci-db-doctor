import oracledb
import os

from dotenv import load_dotenv


load_dotenv()

dsn = os.getenv("DB_URL")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")


with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE test_table PARALLEL 32;
            """
        )
        cursor.execute(
            """
            SELECT /*+ PARALLEL(test_table, 32) */
                id,
                SUM(SQRT(id)) OVER (
                    ORDER BY id
                    ROWS BETWEEN 25000 PRECEDING AND CURRENT ROW
                ) AS moving_sqrt_sum
            FROM test_table;
            """
        )
        cursor.fetchall()
