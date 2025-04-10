import mysql.connector
from flask import Blueprint, render_template, redirect, session, url_for

schema_bp = Blueprint('schema', __name__)

@schema_bp.route('/schema/<db_name>')
def schema(db_name):
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    schema_details = {}
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=session['root_password'],
            database=db_name
        )
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DESCRIBE {table_name};")
            schema_details[table_name] = cursor.fetchall()
    except Exception as e:
        schema_details = {}
    return render_template('view_schema.html', db_name=db_name, schema_details=schema_details)
