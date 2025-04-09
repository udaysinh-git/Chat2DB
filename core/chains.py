from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from flask import current_app
from core.database import execute_safe_query

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
    llm = ChatGroq(model="qwen-2.5-coder-32b", temperature=0)
    def get_schema(_):
        return db.get_table_info()
    return (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )

def get_response(user_query, db, chat_history, app_logger):
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
    # llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
    llm = ChatGroq(model="mistral-saba-24b", temperature=0)
    def safe_db_run(vars):
        try:
            query = vars["query"]
            return execute_safe_query(db, query)
        except Exception as e:
            app_logger.error(f"Error executing query: {str(e)}")
            return f"Error executing query: {str(e)}"
    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _: db.get_table_info(),
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
        app_logger.error(f"Chain execution error: {str(e)}")
        return f"I'm sorry, I encountered an error processing your query. The database may be experiencing connectivity issues. Please try reconnecting to the database. Error: {str(e)}"
