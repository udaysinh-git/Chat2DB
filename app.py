from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from urllib.parse import quote_plus
import os
import mysql.connector
from sqlalchemy import create_engine, text
import time
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

load_dotenv()

def init_database(user, password, host, port, database):
    """Initialize database connection with proper settings to avoid out of sync errors"""
    encoded_password = quote_plus(password)
    
    # Configure connection with proper parameters
    db_uri = f"mysql+mysqlconnector://{user}:{encoded_password}@{host}:{port}/{database}?consume_results=True&allow_local_infile=true"
    
    # Create the SQLAlchemy engine with properly supported pooling settings
    # Lower pool size and recycle time to avoid issues
    engine = create_engine(
        db_uri,
        pool_size=1,         # Minimize pooling issues
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=300,    # Recycle connections every 5 minutes
        pool_pre_ping=True,  # Verify connections before use
        echo=False
    )
    
    try:
        # Test the connection with proper SQLAlchemy text object
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        
        # Create SQLDatabase with custom engine
        db = SQLDatabase(engine=engine)
        
        # Test that the database can retrieve table information
        db.get_table_info()
        
        return db
    except Exception as e:
        app.logger.error(f"Database connection error: {str(e)}")
        raise e

def direct_mysql_query(query, user, password, host, port, database):
    """Execute SQL directly using mysql-connector-python to avoid sync issues"""
    conn = None
    cursor = None
    
    try:
        # Create direct connection to MySQL
        conn = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            consume_results=True,  # Critical for preventing out-of-sync issues
            autocommit=True        # Avoid transaction issues
        )
        
        # Create cursor and execute query
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        
        # Get all results at once to avoid sync issues
        results = cursor.fetchall()
        
        # Convert to JSON-serializable format
        if results is not None:
            # Make datetime objects JSON serializable
            for row in results:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):  # Check if it's date-like
                        row[key] = value.isoformat()
                        
        # Format results nicely - wrap in a code block for markdown rendering
        formatted_result = "```json\n" + json.dumps(results, indent=2) + "\n```"
        return formatted_result
        
    except Exception as e:
        app.logger.error(f"Direct MySQL query error: {str(e)}")
        raise
    finally:
        # Ensure proper cleanup
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def execute_safe_query(db, query):
    """Execute a query with robust error handling for MySQL out-of-sync issues"""
    db_params = session['db_params']
    
    try:
        # First try with SQLAlchemy
        return db.run(query)
    except (mysql.connector.errors.InterfaceError, mysql.connector.errors.OperationalError) as e:
        if "Commands out of sync" in str(e):
            # If we get out of sync, fall back to direct MySQL connection
            app.logger.warning(f"Commands out of sync detected, using direct MySQL connection")
            
            try:
                # Use direct MySQL connection as fallback
                return direct_mysql_query(
                    query,
                    db_params['user'],
                    db_params['password'],
                    db_params['host'],
                    db_params['port'],
                    db_params['database']
                )
            except Exception as direct_error:
                app.logger.error(f"Direct MySQL query also failed: {str(direct_error)}")
                raise Exception(f"Database query failed using both methods. Error: {str(direct_error)}")
        else:
            raise e

def get_sql_chain(db):
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.
    
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History: {chat_history}
    
    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.
    
    For example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
    Question: Name 10 artists
    SQL Query: SELECT Name FROM Artist LIMIT 10;
    
    Your turn:
    
    Question: {question}
    SQL Query:
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # Use Groq model for SQL generation
    llm = ChatGroq(model="qwen-2.5-32b", temperature=0)
    
    def get_schema(_):
        return db.get_table_info()
    
    return (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )
    
def get_response(user_query, db, chat_history):
    sql_chain = get_sql_chain(db)
    
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}
    
    Important formatting instructions:
    1. When you include the SQL query in your response, format it with markdown code blocks using ```sql ... ``` syntax
    2. When the SQL response contains tabular data, format it as a markdown table
    3. For multi-row results, limit to showing at most 10 rows in your formatted table
    4. Always include the executed SQL query in your response so the user can see what was run
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # Use Groq model for response generation
    # llm = ChatGroq(model="mistral-saba-24b", temperature=0)
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
    # Create a safe query function specifically for this chain
    def safe_db_run(vars):
        try:
            query = vars["query"]
            # Use our enhanced safe query function
            return execute_safe_query(db, query)
        except Exception as e:
            app.logger.error(f"Error executing query: {str(e)}")
            # Return a user-friendly error that will be included in the response
            return f"Error executing query: {str(e)}"
    
    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _: db.get_table_info(),
            # Use our enhanced safe query execution function
            response=safe_db_run
        )
        | prompt
        | llm
        | StrOutputParser()
    )
    
    try:
        return chain.invoke({
            "question": user_query,
            "chat_history": chat_history,
        })
    except Exception as e:
        app.logger.error(f"Chain execution error: {str(e)}")
        return f"I'm sorry, I encountered an error processing your query. The database may be experiencing connectivity issues. Please try reconnecting to the database. Error: {str(e)}"

@app.route('/')
def index():
    # Initialize chat history if it doesn't exist
    if 'chat_history' not in session:
        session['chat_history'] = [
            {"role": "ai", "content": "Hello! I'm a SQL assistant. Ask me anything about your database."}
        ]
    return render_template('index.html', chat_history=session['chat_history'])

@app.route('/connect', methods=['POST'])
def connect():
    data = request.form
    user = data.get('user')
    password = data.get('password')
    host = data.get('host')
    port = data.get('port')
    database = data.get('database')
    
    try:
        db = init_database(user, password, host, port, database)
        # Store connection parameters in session
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

@app.route('/chat', methods=['POST'])
def chat():
    user_query = request.form.get('message')
    
    if not user_query or user_query.strip() == "":
        return jsonify({"success": False, "message": "Empty message"})
    
    # Check if database is connected
    if 'db_params' not in session:
        return jsonify({"success": False, "message": "Please connect to the database first"})
    
    # Initialize database connection
    try:
        db_params = session['db_params']
        db = init_database(
            db_params['user'],
            db_params['password'],
            db_params['host'],
            db_params['port'],
            db_params['database']
        )
        
        # Convert session chat history to LangChain format
        langchain_history = []
        for msg in session.get('chat_history', []):
            if msg['role'] == 'human':
                langchain_history.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'ai':
                langchain_history.append(AIMessage(content=msg['content']))
        
        # Add user message to chat history
        session['chat_history'] = session.get('chat_history', [])
        session['chat_history'].append({"role": "human", "content": user_query})
        
        # Get AI response with error handling
        try:
            ai_response = get_response(user_query, db, langchain_history)
            
            # Format the response to highlight SQL code
            ai_response = format_ai_response(ai_response)
            
        except Exception as e:
            app.logger.error(f"Error during response generation: {str(e)}")
            ai_response = f"I'm sorry, I encountered an error while processing your query. Please try again or check the database connection. Error: {str(e)}"
        
        # Add AI response to chat history
        session['chat_history'].append({"role": "ai", "content": ai_response})
        session.modified = True
        
        return jsonify({
            "success": True, 
            "message": ai_response
        })
        
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"})

def format_ai_response(response):
    """Format AI response to properly highlight SQL code and tables"""
    # No changes needed if response is already properly formatted
    if "```sql" in response:
        return response
    
    # Try to identify SQL statements that aren't properly formatted
    import re
    
    # Find SQL statements like SELECT, INSERT, UPDATE, etc.
    sql_pattern = r'(?i)(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|MERGE|WITH)[\s\S]+?(?:;|\n\n)'
    
    def replace_sql(match):
        sql = match.group(0)
        # Don't double-wrap if it's already in a code block
        if "```sql" in sql:
            return sql
        return f"```sql\n{sql}\n```"
    
    response = re.sub(sql_pattern, replace_sql, response)
    
    # Format tables in the response
    table_pattern = r'(\|.*?\|(?:\n\|.*?\|)+)'
    
    def replace_table(match):
        table = match.group(0)
        return f"\n{table}\n"
    
    response = re.sub(table_pattern, replace_table, response)
    
    return response

if __name__ == '__main__':
    app.run(debug=True)
