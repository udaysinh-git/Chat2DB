import mysql.connector
from flask import Blueprint, render_template, redirect, session, url_for

view_databases_bp = Blueprint('view_databases', __name__)

@view_databases_bp.route('/view_databases')
def view_databases():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=session['root_password']
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES;")
        databases = cursor.fetchall()
    except Exception as e:
        databases = []
    return render_template('view_databases.html', databases=databases)
