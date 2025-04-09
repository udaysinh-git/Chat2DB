import os
from urllib.parse import quote_plus
import mysql.connector
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from flask import current_app, session

def init_database(user, password, host, port, database):
    encoded_password = quote_plus(password)
    db_uri = f"mysql+mysqlconnector://{user}:{encoded_password}@{host}:{port}/{database}?consume_results=True&allow_local_infile=true"
    engine = create_engine(
        db_uri,
        pool_size=1,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=300,
        pool_pre_ping=True,
        echo=False
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        db = SQLDatabase(engine=engine)
        db.get_table_info()
        return db
    except Exception as e:
        current_app.logger.error(f"Database connection error: {str(e)}")
        raise e

def direct_mysql_query(query, user, password, host, port, database):
    conn, cursor = None, None
    try:
        conn = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            consume_results=True,
            autocommit=True
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        results = cursor.fetchall()
        if results is not None:
            for row in results:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
        formatted_result = "```json\n" + __import__("json").dumps(results, indent=2) + "\n```"
        return formatted_result
    except Exception as e:
        current_app.logger.error(f"Direct MySQL query error: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def execute_safe_query(db, query):
    db_params = session['db_params']
    try:
        return db.run(query)
    except (mysql.connector.errors.InterfaceError, mysql.connector.errors.OperationalError) as e:
        if "Commands out of sync" in str(e):
            current_app.logger.warning("Commands out of sync detected, using direct MySQL connection")
            try:
                return direct_mysql_query(
                    query,
                    db_params['user'],
                    db_params['password'],
                    db_params['host'],
                    db_params['port'],
                    db_params['database']
                )
            except Exception as direct_error:
                current_app.logger.error(f"Direct MySQL query also failed: {str(direct_error)}")
                raise Exception(f"Database query failed using both methods. Error: {str(direct_error)}")
        else:
            raise e
