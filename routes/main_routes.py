from flask import Blueprint, render_template, request, jsonify, session, current_app
from uuid import uuid4
from langchain_core.messages import AIMessage, HumanMessage
from core.database import init_database
from core.chains import get_response
from core.utils import format_ai_response
from core.sqlite_db import init_chat_history_db, save_message, get_chat_history
import re

# Initialize the chat history database once
init_chat_history_db()

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())  # auto-assign session_id on first visit
    if 'chat_history' not in session:
        session['chat_history'] = [{"role": "ai", "content": "Hello! I'm a SQL assistant. Ask me anything about your database."}]
    return render_template('index.html', chat_history=session['chat_history'])

@main_bp.route('/connect', methods=['POST'])
def connect():
    data = request.form
    user = data.get('user')
    password = data.get('password')
    host = data.get('host')
    port = data.get('port')
    database = data.get('database')
    try:
        db = init_database(user, password, host, port, database)
        session['db_params'] = {
            'user': user,
            'password': password,
            'host': host,
            'port': port,
            'database': database
        }
        return jsonify({"success": True, "message": "Connected to database!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Connection error: {str(e)}"})

@main_bp.route('/databases', methods=['POST'])
def databases():
    data = request.form
    user = data.get('user')
    password = data.get('password')
    host = data.get('host')
    port = data.get('port')
    try:
        import pymysql
        conn = pymysql.connect(host=host, port=int(port), user=user, password=password)
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES;")
        dbs = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({"success": True, "databases": dbs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@main_bp.route('/chat', methods=['POST'])
def chat():
    user_query = request.form.get('message')
    if not user_query or user_query.strip() == "":
        return jsonify({"success": False, "message": "Empty message"})
    if 'db_params' not in session:
        return jsonify({"success": False, "message": "Please connect to the database first"})
    
    # Ensure a unique session_id is set for persistent chat history
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
    
    try:
        db_params = session['db_params']
        db = init_database(
            db_params['user'],
            db_params['password'],
            db_params['host'],
            db_params['port'],
            db_params['database']
        )
        langchain_history = []
        for msg in session.get('chat_history', []):
            if msg['role'] == 'human':
                langchain_history.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'ai':
                langchain_history.append(AIMessage(content=msg['content']))
        session['chat_history'] = session.get('chat_history', [])
        session['chat_history'].append({"role": "human", "content": user_query})
        # Save human message in SQLite
        save_message(session['session_id'], "human", user_query)
        try:
            ai_response = get_response(user_query, db, langchain_history, current_app.logger)
            ai_response = format_ai_response(ai_response)
        except Exception as e:
            current_app.logger.error(f"Error during response generation: {str(e)}")
            ai_response = f"I'm sorry, I encountered an error while processing your query. Please try again or check the database connection. Error: {str(e)}"
        # Extract only SQL query content (inside a ```sql ... ``` block)
        sql_match = re.search(r"```sql\s*([\s\S]+?)\s*```", ai_response)
        ai_query = sql_match.group(1).strip() if sql_match else ai_response.strip()
        session['chat_history'].append({"role": "ai", "content": ai_response})
        # Save only the SQL query in SQLite history
        save_message(session['session_id'], "ai", ai_query)
        session.modified = True
        return jsonify({"success": True, "message": ai_response})
    except Exception as e:
        current_app.logger.error(f"Chat error: {str(e)}")
        # If an error occurs, store it as an AI message
        error_msg = f"Error: {str(e)}"
        session['chat_history'].append({"role": "ai", "content": error_msg})
        save_message(session['session_id'], "ai", error_msg)
        return jsonify({"success": False, "message": error_msg})

@main_bp.route('/history')
def history():
    if 'session_id' not in session:
        return "No chat history available", 400
    # Retrieve chat history from SQLite
    history_data = get_chat_history(session['session_id'])
    return render_template('history.html', chat_history=history_data)
