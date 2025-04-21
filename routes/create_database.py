import mysql.connector
from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
# Import the renamed and new functions
from core.groq_model import generate_sql_and_mermaid_from_description, generate_schema_commands_from_description

create_database_bp = Blueprint('create_database', __name__)

@create_database_bp.route('/create_database', methods=['GET', 'POST'])
def create_database():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    if request.method == 'POST':
        db_name = request.form.get('db_name')
        description = request.form.get('description')
        # Call renamed Groq model function to generate both SQL and Mermaid
        schema_sql, mermaid = generate_sql_and_mermaid_from_description(description)
        # Store in session for later use
        session['pending_db'] = {
            'db_name': db_name,
            'description': description,
            'schema_sql': schema_sql, # Store raw SQL
            'mermaid': mermaid       # Store Mermaid diagram
        }
        # Pass both to the preview template
        return render_template('preview_schema.html', db_name=db_name, schema_sql=schema_sql, mermaid=mermaid)
    return render_template('create_database.html')

@create_database_bp.route('/regenerate_schema', methods=['POST'])
def regenerate_schema():
    if 'pending_db' not in session or 'description' not in session['pending_db']:
        return jsonify({'success': False, 'message': 'No description found in session.'})
    description = session['pending_db']['description']
    # Call renamed Groq model function to regenerate both SQL and Mermaid
    schema_sql, mermaid = generate_sql_and_mermaid_from_description(description)
    # Update session with the new schema and diagram
    session['pending_db']['schema_sql'] = schema_sql
    session['pending_db']['mermaid'] = mermaid
    # Return both for the preview update
    return jsonify({'success': True, 'schema_sql': schema_sql, 'mermaid': mermaid})

@create_database_bp.route('/finalize_database', methods=['POST'])
def finalize_database():
    if 'pending_db' not in session:
        return redirect(url_for('create_database.create_database'))
    db_info = session['pending_db']
    db_name = db_info['db_name']
    # Render the progress page, execution happens via AJAX call
    return render_template('progress.html', db_name=db_name)

def store_temp_schema(db_name, schema_sql, mermaid):
    """
    Saves the generated schema SQL and Mermaid diagram into a temporary table.
    """
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=session['root_password']
    )
    cursor = conn.cursor()
    # Create a temporary database for schema storage if not exists
    cursor.execute("CREATE DATABASE IF NOT EXISTS chat2db_temp;")
    cursor.execute("USE chat2db_temp;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temp_schemas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            db_name VARCHAR(255),
            schema_sql TEXT,
            mermaid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    insert_query = "INSERT INTO temp_schemas (db_name, schema_sql, mermaid) VALUES (%s, %s, %s);"
    # Ensure schema_sql and mermaid are strings
    cursor.execute(insert_query, (db_name, str(schema_sql), str(mermaid)))
    conn.commit()
    cursor.close()
    conn.close()


def execute_schema_commands(cursor, commands):
    for cmd in commands:
        try:
            # Ensure command is a non-empty string before executing
            if isinstance(cmd, str) and cmd.strip():
                 cursor.execute(cmd)
            else:
                 print(f"Skipping invalid command: {cmd}")
        except Exception as e:
            print(f"Skipping command due to error: {cmd} Error: {e}")
            continue


@create_database_bp.route('/execute_finalize_database', methods=['POST'])
def execute_finalize_database():
    if 'pending_db' not in session:
        return jsonify({'success': False, 'message': 'No pending database info.'})
    db_info = session['pending_db']
    db_name = db_info['db_name']
    description = db_info['description'] # Keep description in case needed later, though not used directly here now
    
    # Retrieve the previously generated schema_sql and mermaid from session
    schema_sql = db_info.get('schema_sql', '')
    mermaid = db_info.get('mermaid', '')

    # Save the schema into a temporary database table
    # Ensure schema_sql and mermaid are valid before storing
    if schema_sql and mermaid:
        try:
            store_temp_schema(db_name, schema_sql, mermaid)
        except Exception as store_e:
             print(f"Error storing temp schema: {store_e}") # Log error but continue

    # Get commands by splitting the schema_sql from session
    commands = [stmt.strip() + ';' for stmt in schema_sql.split(';') if stmt.strip()]

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=session['root_password']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;") # Use backticks for safety
        cursor.execute(f"USE `{db_name}`;") # Use backticks for safety
        
        # Execute the commands derived from the stored schema_sql
        execute_schema_commands(cursor, commands)
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        # Log the detailed error
        print(f"Database finalization error for {db_name}: {str(e)}")
        return jsonify({'success': False, 'message': f"Error creating database: {str(e)}"})
        
    session.pop('pending_db', None)
    return jsonify({'success': True})
