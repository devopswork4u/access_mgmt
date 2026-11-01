import getpass
import random
from datetime import date, timedelta

import provisioner
from config import AURORA, DEPARTMENTS, SCOPES

ROWS_PER_TABLE = 2000
SECTIONS = SCOPES[1:]
USERNAME = AURORA["user"] or input("Admin user: ")
PASSWORD = AURORA["password"] or getpass.getpass("Password: ")
AURORA["user"], AURORA["password"] = USERNAME, PASSWORD
random.seed(7)

c = provisioner._connect()
with c.cursor() as cur:
    for dept in DEPARTMENTS.values():
        for db, tables in dept["databases"].items():
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
            for t in tables:
                cur.execute(f"""CREATE TABLE IF NOT EXISTS `{db}`.`{t}` (
                    id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
                    section VARCHAR(40) NOT NULL, detail VARCHAR(100), created_on DATE, INDEX (section))""")
                cur.execute(f"SELECT COUNT(*) FROM `{db}`.`{t}`")
                if cur.fetchone()[0] == 0:
                    rows = [(f"{t[:-1].title()} {i}", random.choice(SECTIONS), f"{t} record {i}",
                             date(2025, 1, 1) + timedelta(days=random.randint(0, 600))) for i in range(1, ROWS_PER_TABLE + 1)]
                    cur.executemany(f"INSERT INTO `{db}`.`{t}` (name, section, detail, created_on) VALUES (%s,%s,%s,%s)", rows)
                print(f"ready: {db}.{t}")
c.close()
