import os
import mysql.connector
from mysql.connector import Error

# db_connect.py update
def get_connection():
    try:
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or "Yahan_Apna_Actual_Password_Likhein"
        
        connection = mysql.connector.connect(
            host=os.environ.get("MYSQLHOST") or "ballast.proxy.rlwy.net",
            user=os.environ.get("MYSQLUSER") or "root",
            password=password,
            database=os.environ.get("MYSQL_DATABASE") or "railway",
            port=50532
        )

        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Connection Error Detail: {e}")
        return None

