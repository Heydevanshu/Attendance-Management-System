from db_connect import get_connection

def add_teacher(name, email, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teachers(name,email,password,status) VALUES(%s,%s,%s,'Approved')",
                       (name,email,password))
        conn.commit()
        conn.close()
        print("Teacher added successfully!")
    except Exception as e:
        print("Add teacher error:", e)

def view_teachers():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teachers")
        rows = cursor.fetchall()
        conn.close()
        for r in rows: print(r)
    except Exception as e:
        print("View teacher error:", e)

def update_teacher(id,name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE teachers SET name=%s WHERE id=%s",(name,id))
        conn.commit()
        conn.close()
        print("Teacher updated!")
    except Exception as e:
        print("Update error:", e)

def delete_teacher(id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teachers WHERE id=%s",(id,))
        conn.commit()
        conn.close()
        print("Teacher deleted!")
    except Exception as e:
        print("Delete error:", e)

def teacher_menu(teacher_id=None):
    while True:
        print("\n--- Teacher Menu ---")
        print("1. View Teachers")
        print("2. Update Teacher")
        print("3. Delete Teacher")
        print("4. Exit")
        choice = input("Choice: ")

        if choice=="1": view_teachers()
        elif choice=="2":
            tid = input("Enter ID: ")
            name = input("New Name: ")
            update_teacher(tid,name)
        elif choice=="3":
            tid = input("Enter ID to delete: ")
            delete_teacher(tid)
        elif choice=="4":
            break
        else: print("Invalid Choice")
