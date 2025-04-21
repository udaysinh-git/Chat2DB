import mysql.connector
from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from core.groq_model import generate_schema_from_description  # You will create this utility

create_database_bp = Blueprint('create_database', __name__)

@create_database_bp.route('/create_database', methods=['GET', 'POST'])
def create_database():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    if request.method == 'POST':
        db_name = request.form.get('db_name')
        description = request.form.get('description')
        # Call Groq model to generate schema SQL and ER diagram
        schema_sql, mermaid = generate_schema_from_description(description)
        # Store in session for later use
        session['pending_db'] = {
            'db_name': db_name,
            'description': description,
            'schema_sql': schema_sql,
            'mermaid': mermaid
        }
        return render_template('preview_schema.html', db_name=db_name, schema_sql=schema_sql, mermaid=mermaid)
    return render_template('create_database.html')

@create_database_bp.route('/regenerate_schema', methods=['POST'])
def regenerate_schema():
    # Use the description from session to regenerate the schema and ER diagram
    if 'pending_db' not in session or 'description' not in session['pending_db']:
        return jsonify({'success': False, 'message': 'No description found in session.'})
    description = session['pending_db']['description']
    schema_sql, mermaid = generate_schema_from_description(description)
    # Update session with the new schema and diagram
    session['pending_db']['schema_sql'] = schema_sql
    session['pending_db']['mermaid'] = mermaid
    return jsonify({'success': True, 'schema_sql': schema_sql, 'mermaid': mermaid})

@create_database_bp.route('/finalize_database', methods=['POST'])
def finalize_database():
    if 'pending_db' not in session:
        return redirect(url_for('create_database.create_database'))
    db_info = session['pending_db']
    db_name = db_info['db_name']
    # Instead of executing SQL immediately, render a progress page
    return render_template('progress.html', db_name=db_name)

def execute_schema_commands(cursor, commands):
    # Iterates over each SQL command and executes it.
    # If a command fails, log the error and skip that command.
    for cmd in commands:
        try:
            cursor.execute(cmd)
        except Exception as e:
            print(f"Skipping command due to error: {cmd} Error: {e}")
            continue    

@create_database_bp.route('/execute_finalize_database', methods=['POST'])
def execute_finalize_database():
    if 'pending_db' not in session:
        return jsonify({'success': False, 'message': 'No pending database info.'})
    db_info = session['pending_db']
    db_name = db_info['db_name']
    description = db_info['description']
    # Use the new function to get the list of commands instead of raw SQL
    from core.groq_model import generate_schema_commands_from_description
    commands, mermaid = generate_schema_commands_from_description(description)
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=session['root_password']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
        cursor.execute(f"USE {db_name};")
        execute_schema_commands(cursor, commands)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    session.pop('pending_db', None)
    return jsonify({'success': True})
