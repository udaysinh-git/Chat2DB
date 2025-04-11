import mysql.connector
from flask import Blueprint, render_template, redirect, session, url_for
from groq import Groq
import re  # Added for regex operations

schema_bp = Blueprint('schema', __name__)

@schema_bp.route('/schema/<db_name>')
def schema(db_name):
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    schema_details = {}
    table_count = 0
    column_count = 0
    primary_keys = {}
    foreign_keys = {}
    
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
        table_count = len(tables)
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DESCRIBE {table_name};")
            columns = cursor.fetchall()
            schema_details[table_name] = columns
            column_count += len(columns)
            
            # Track primary keys
            for col in columns:
                if col[3] == "PRI":
                    if table_name not in primary_keys:
                        primary_keys[table_name] = []
                    primary_keys[table_name].append(col[0])
                    
            # Get foreign keys
            try:
                cursor.execute(f"""
                    SELECT 
                        COLUMN_NAME, 
                        REFERENCED_TABLE_NAME, 
                        REFERENCED_COLUMN_NAME 
                    FROM 
                        INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                    WHERE 
                        TABLE_SCHEMA = '{db_name}' AND 
                        TABLE_NAME = '{table_name}' AND 
                        REFERENCED_TABLE_NAME IS NOT NULL
                """)
                fk_results = cursor.fetchall()
                if fk_results:
                    foreign_keys[table_name] = fk_results
            except Exception as e:
                print(f"Error fetching foreign keys for {table_name}: {str(e)}")
    except Exception as e:
        print(f"Error in schema view: {str(e)}")
        schema_details = {}

    # Build schema text for Groq prompt (keeping this unchanged)
    schema_text = f"Schema for Database: {db_name}\n"
    for table, columns in schema_details.items():
        schema_text += table + "\n"
        for col in columns:
            annotation = ""
            if col[3] == "PRI":
                annotation = " PK"
            elif col[3] == "MUL":
                annotation = " FK"
            schema_text += f"{col[0]} - {col[1]}{annotation}\n"
        schema_text += "\n"

    # Define prompt messages with instructions and schema text (keeping this unchanged)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a deterministic assistant that converts database schemas into valid Mermaid JS ER diagrams. Follow these precise rules:\n\n"
                "1. **Entity Blocks:**\n"
                "   - Each table must be represented as an entity block with the following format:\n"
                "     ```\n"
                "     <table_name> {\n"
                "         <data_type> <attribute_name> [optional annotations such as PK, FK]\n"
                "         ...\n"
                "     }\n"
                "     ```\n\n"
                "2. **Relationships (Auto-detection from Schema):**\n"
                "   - Automatically detect relationships using foreign keys (FK) and primary keys (PK).\n"
                "   - Use this Mermaid syntax to define the relationships:\n"
                "     ```\n"
                "     parent_table ||--o{ child_table : \"FK relationship\"\n"
                "     ```\n"
                "   - For each foreign key in a table, create a one-to-many relationship.\n\n"
                "3. **Sanitization Rules:**\n\n"
                "   a. **Data Types:**\n"
                "      - Replace any commas in data type definitions with an underscore. For example, instead of outputting:\n"
                "        ```\n"
                "        decimal(10,2) Total\n"
                "        ```\n"
                "        output:\n"
                "        ```\n"
                "        decimal(10_2) Total\n"
                "        ```\n\n"
                "   b. **Enum Definitions:**\n"
                "      - Do not include enumeration values and single quotes in the data type definition. For example, instead of outputting:\n"
                "        ```\n"
                "        enum('G','PG','PG-13','R') content_rating\n"
                "        ```\n"
                "        simply output:\n"
                "        ```\n"
                "        enum content_rating\n"
                "        ```\n\n"
                "   c. **Backticks and Formatting:**\n"
                "      - The entire Mermaid diagram must be enclosed in a single pair of triple backticks.\n"
                "      - Do not include any additional or stray backticks within the diagram code.\n\n"
                "4. **Output Verification:**\n"
                "   - Ensure every table defined in the schema appears as an entity block.\n"
                "   - Confirm that all attributes have data types that do not include commas or any disallowed punctuation.\n"
                "   - Verify that no extra formatting tokens (such as stray backticks) are present within the Mermaid code.\n"
                "   - Ensure that enum types are output simply as \"enum\" (without parentheses or enumeration values).\n"
                "   - Automatically detect and represent FK relationships as Mermaid relationships.\n\n"
                "Now, please generate a Mermaid JS ER diagram for the following schema:\n\n" + schema_text
            )
        },
        {
            "role": "user",
            "content": schema_text
        }
    ]

    client = Groq()
    completion = client.chat.completions.create(
        model="mistral-saba-24b",
        messages=messages,
        temperature=0,
        max_completion_tokens=11360,
        top_p=1,
        stream=False
    )
    mermaid_diagram = completion.choices[0].message.content
    # Remove leading and trailing triple backticks if present
    if mermaid_diagram.startswith("```") and mermaid_diagram.endswith("```"):
        mermaid_diagram = mermaid_diagram[3:-3].strip()
    print("Schema input:", schema_text)         # <-- Print input on terminal
    print("Mermaid diagram response:", mermaid_diagram)  # <-- Print response on terminal
    
    # Additional metadata for enhanced UI
    schema_metadata = {
        'table_count': table_count,
        'column_count': column_count,
        'primary_keys': primary_keys,
        'foreign_keys': foreign_keys
    }
    
    return render_template(
        'view_schema.html', 
        db_name=db_name, 
        schema_details=schema_details, 
        schema_metadata=schema_metadata,
        mermaid_diagram=mermaid_diagram
    )

@schema_bp.route('/er_diagram/<db_name>')
def er_diagram(db_name):
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

    # Build schema text for Groq prompt
    schema_text = f"Schema for Database: {db_name}\n"
    for table, columns in schema_details.items():
        schema_text += table + "\n"
        for col in columns:
            annotation = ""
            if col[3] == "PRI":
                annotation = " PK"
            elif col[3] == "MUL":
                annotation = " FK"
            schema_text += f"{col[0]} - {col[1]}{annotation}\n"
        schema_text += "\n"

    # Define prompt messages with instructions and schema text.
    messages = [
        {
            "role": "system",
            "content": (
                "You are a deterministic assistant (temperature = 0) that converts database schemas into valid Mermaid JS ER diagrams. Follow these precise rules:\n\n"
                "1. **Entity Blocks:**\n"
                "   - Each table must be represented as an entity block with the following format:\n"
                "     ```\n"
                "     <table_name> {\n"
                "         <data_type> <attribute_name> [optional annotations such as PK, FK]\n"
                "         ...\n"
                "     }\n"
                "     ```\n\n"
                "2. **Relationships (Auto-detection from Schema):**\n"
                "   - Automatically detect relationships using foreign keys (FK) and primary keys (PK).\n"
                "   - Use this Mermaid syntax to define the relationships:\n"
                "     ```\n"
                "     parent_table ||--o{ child_table : \"FK relationship\"\n"
                "     ```\n"
                "   - For each foreign key in a table, create a one-to-many relationship.\n\n"
                "3. **Sanitization Rules:**\n"
                "   a. Replace any commas in data type definitions with an underscore.\n"
                "   b. Enum definitions should output as 'enum' without values or quotes.\n"
                "   c. Wrap the entire Mermaid diagram in exactly one pair of triple backticks, with no stray backticks inside.\n\n"
                "4. **Output Verification:**\n"
                "   - Every table must be rendered as an entity block with sanitized data types.\n"
                "   - All FK relationships must be represented.\n\n"
                "Now, please generate a Mermaid JS ER diagram for the following schema:\n\n" + schema_text
            )
        },
        {
            "role": "user",
            "content": schema_text
        }
    ]

    client = Groq()
    completion = client.chat.completions.create(
        model="mistral-saba-24b",
        messages=messages,
        temperature=0,
        max_completion_tokens=11360,
        top_p=1,
        stream=False
    )
    mermaid_diagram = completion.choices[0].message.content
    print(mermaid_diagram)
    # Remove leading and trailing triple backticks if present
    if mermaid_diagram.startswith("```") and mermaid_diagram.endswith("```"):
        mermaid_diagram = mermaid_diagram[3:-3].strip()
    mermaid_diagram = mermaid_diagram.replace("mermaid", "")
    # Fix for Mermaid syntax error in ER diagram: remove square brackets around PK/FK
    mermaid_diagram = mermaid_diagram.replace('[PK]', 'PK').replace('[FK]', 'FK')
    # New: Remove size definitions for varchar and convert decimal commas to underscores
    mermaid_diagram = re.sub(r'varchar\(\d+\)', 'varchar', mermaid_diagram)
    mermaid_diagram = re.sub(r'decimal\((\d+),(\d+)\)', r'decimal(\1_\2)', mermaid_diagram)
    # Prepend "erDiagram" header if not already present
    if not mermaid_diagram.startswith("erDiagram"):
        mermaid_diagram = "erDiagram\n" + mermaid_diagram
    # Standardize all relationship labels to "FK relationship"
    # mermaid_diagram = re.sub(r'(:\s*").+?(")', r': "FK relationship"', mermaid_diagram)
    return render_template('er_diagram.html', db_name=db_name, mermaid_diagram=mermaid_diagram)
