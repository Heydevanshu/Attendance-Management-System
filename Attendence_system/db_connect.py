import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        # 1. Port
        port_env = os.environ.get("MYSQLPORT")
        port_to_use = int(port_env) if port_env else 50532

        # 2. Host
        host_to_use = os.environ.get("MYSQLHOST") or "ballast.proxy.rlwy.net"

        # 3. Connection
        connection = mysql.connector.connect(
            host=host_to_use,
            user=os.environ.get("MYSQLUSER"),
            password=os.environ.get("MYSQLPASSWORD"),
            database=os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE"),
            port=port_to_use
        )

        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Connection Error: {e}")
        return None

if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("Success! Database connected.")
        conn.close()
    else:
        print("Still failing. Check Railway Environment Variables.")
