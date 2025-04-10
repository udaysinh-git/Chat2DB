import mysql.connector
from flask import Blueprint, render_template, request, redirect, session, url_for

create_database_bp = Blueprint('create_database', __name__)

@create_database_bp.route('/create_database', methods=['GET', 'POST'])
def create_database():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    if request.method == 'POST':
        db_name = request.form.get('db_name')
        example_schema = request.form.get('example_schema')
        try:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password=session['root_password']
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE {db_name};")
            conn.commit()
        except Exception as e:
            # ...existing error handling...
            pass
        return redirect(url_for('dashboard.dashboard'))
    return render_template('create_database.html')
