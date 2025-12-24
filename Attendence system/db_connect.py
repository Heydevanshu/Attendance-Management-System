import mysql.connector

def get_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="WJ28@krhps",
            database="teacher_db",
            port=3306
        )
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        return None
