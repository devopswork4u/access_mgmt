import getpass
import os
import socket
import ssl
import sys

import pymysql

from config import AURORA

host, port = AURORA["host"], AURORA["port"]
user = AURORA["user"] or input("Admin user: ")
password = AURORA["password"] or getpass.getpass("Password: ")

print(f"1) DNS: {host}")
try:
    print("   resolves to", socket.gethostbyname(host))
except OSError as e:
    sys.exit(f"   DNS FAILED: {e}")

print(f"2) Network: port {port}")
try:
    socket.create_connection((host, port), timeout=10).close()
    print("   reachable")
except OSError as e:
    sys.exit(f"   NOT reachable ({e}). Check the internet access gateway / security group.")

print("3) Login + SSL")
ctx = ssl.create_default_context()
if os.path.exists("global-bundle.pem"):
    ctx.load_verify_locations("global-bundle.pem")
else:
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
try:
    c = pymysql.connect(host=host, port=port, user=user, password=password, ssl=ctx, connect_timeout=10)
except pymysql.err.OperationalError as e:
    sys.exit(f"   LOGIN FAILED: {e}")
with c.cursor() as cur:
    cur.execute("SELECT VERSION(), CURRENT_USER()")
    print("   connected:", cur.fetchone())
    cur.execute("SHOW DATABASES")
    print("   databases:", [r[0] for r in cur.fetchall()])
c.close()
