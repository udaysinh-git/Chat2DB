from langchain_groq import ChatGroq
from groq import Groq  # Import Groq client for the new function
import os
import re

# Renamed function: Generates both SQL DDL and Mermaid from description
def generate_sql_and_mermaid_from_description(description):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    model_name = "llama3-70b-8192" 

    # Prompt remains the same as before, asking for both SQL and Mermaid
    prompt = f"""
You are a deterministic assistant that converts database descriptions into:
1. Valid, production-ready MySQL DDL statements (CREATE TABLE, PK, FK, etc).
2. Valid Mermaid JS ER diagrams.

**SQL DDL Generation Rules:**
- Use only MySQL syntax.
- Always specify primary keys (PK) and foreign keys (FK) explicitly using CONSTRAINT syntax (e.g., CONSTRAINT pk_users PRIMARY KEY (user_id), CONSTRAINT fk_orders_users FOREIGN KEY (user_id) REFERENCES users(user_id)).
- Use `INT`, `VARCHAR(n)`, `DATE`, `DECIMAL(x,y)`, `ENUM`, `TEXT`, `TIMESTAMP`, etc. Use reasonable lengths for VARCHAR.
- For `DECIMAL`, use the standard format `DECIMAL(x,y)`.
- For `ENUM`, include the values like `ENUM('value1', 'value2')`.
- Use backticks around table and column names (e.g., `users`, `user_id`).
- Each statement must end with a semicolon.
- Use only ASCII characters.
- Include `CREATE TABLE IF NOT EXISTS` for table creation.
- Add `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;` at the end of each CREATE TABLE statement.

**Mermaid ER Diagram Rules:**
- Start the diagram with `erDiagram`.
- Each table must be represented as an entity block:
  ```
  <table_name> {{
      <data_type> <attribute_name> [optional annotations such as PK, FK]
      ...
  }}
  ```
- Use standard Mermaid data types (e.g., `INT`, `VARCHAR`, `DATE`, `DECIMAL`). Do NOT include lengths or precision (e.g., use `VARCHAR` not `VARCHAR(255)`).
- Mark primary keys with `PK` and foreign keys with `FK`.
- Automatically detect relationships using foreign keys (FK) and primary keys (PK).
- Use this Mermaid syntax for relationships:
  ```
  parent_table ||--o{{ child_table : "references"
  ```
- For each foreign key in a table, create a one-to-many relationship line.
- The entire Mermaid diagram must be enclosed in a single pair of triple backticks.

Given this database description, first infer the tables, columns, primary keys, and foreign keys, then generate:
1. The SQL DDL statements (MySQL) to create all tables and relationships, following the SQL rules.
2. A Mermaid ER diagram representing the schema, following the Mermaid rules.

Description:
{description}

Respond *strictly* in this format, including the labels and code blocks. Provide both sections even if one part fails:
SQL:
```sql
<sql>
```
MERMAID:
```mermaid
<mermaid>
```
"""

    llm = ChatGroq(model=model_name, groq_api_key=groq_api_key, temperature=0)
    
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # --- Debugging: Print raw response ---
        print("--- Raw Groq Response (generate_sql_and_mermaid) ---")
        print(content)
        print("----------------------------------------------------")

        # --- Updated Regex ---
        # Allow optional asterisks around the labels (e.g., **SQL:** or SQL:)
        sql_match = re.search(r"\**SQL\**:\s*```(?:sql)?\s*([\s\S]+?)\s*```", content, re.IGNORECASE)
        mermaid_match = re.search(r"\**MERMAID\**:\s*```(?:mermaid)?\s*([\s\S]+?)\s*```", content, re.IGNORECASE)
        
        schema_sql = sql_match.group(1).strip() if sql_match else ""
        mermaid = mermaid_match.group(1).strip() if mermaid_match else ""

        # --- Debugging: Print parsed results ---
        print(f"Parsed SQL (empty? {not schema_sql}):\n{schema_sql[:200]}...") # Print first 200 chars
        print(f"Parsed Mermaid (empty? {not mermaid}):\n{mermaid[:200]}...") # Print first 200 chars
        print("----------------------------------------------------")

        # --- Fallback if parsing failed ---
        if not schema_sql:
            schema_sql = "-- Failed to parse SQL from Groq response. --"
        if not mermaid:
            mermaid = "erDiagram\n  %% Failed to parse Mermaid diagram from Groq response. %%"
        
        # Basic cleanup for Mermaid (redundant if fallback used, but safe)
        if mermaid.startswith("erDiagram"):
             mermaid = "erDiagram\n" + mermaid[len("erDiagram"):].strip()
        elif "erDiagram" in mermaid: # Try to find it if not at start
             er_pos = mermaid.find("erDiagram")
             mermaid = mermaid[er_pos:]
        # Ensure it still starts with erDiagram if possible after cleanup
        if not mermaid.startswith("erDiagram") and "%%" not in mermaid:
             mermaid = "erDiagram\n" + mermaid

    except Exception as e:
        print(f"ERROR in generate_sql_and_mermaid_from_description: {e}")
        schema_sql = f"-- Error during Groq call: {e} --"
        mermaid = f"erDiagram\n  %% Error during Groq call: {e} %%"
        
    return schema_sql, mermaid

# New function: Generates only Mermaid ER diagram from schema text
def generate_mermaid_er_from_schema_text(schema_text):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    client = Groq(api_key=groq_api_key)
    model_name = "llama3-70b-8192" # Good model for structured output

    # Prompt adapted from routes/schema.py for generating Mermaid from schema text
    messages = [
        {
            "role": "system",
            "content": (
                "You are a deterministic assistant that converts database schema text into valid Mermaid JS ER diagrams. Follow these precise rules:\n\n"
                "1. **Output Format:** Start the diagram with `erDiagram` on the first line.\n"
                "2. **Entity Blocks:** Represent each table as an entity block:\n"
                "   ```\n"
                "   <table_name> {\n"
                "       <data_type> <attribute_name> [PK|FK]\n"
                "       ...\n"
                "   }\n"
                "   ```\n"
                "3. **Data Types:** Use standard Mermaid types (e.g., `INT`, `VARCHAR`, `DATE`, `DECIMAL`). Do NOT include lengths, precision, or enum values.\n"
                "4. **Keys:** Mark primary keys with `PK` and foreign keys with `FK`.\n"
                "5. **Relationships:** Automatically detect FK relationships from the schema text (look for 'FK' annotations). Use the format: `parent_table ||--o{ child_table : \"references\"` for each FK.\n"
                "6. **Enclose:** Wrap the entire Mermaid diagram code (starting with `erDiagram`) in a single pair of triple backticks ```mermaid ... ```.\n"
                "7. **Cleanliness:** Ensure no stray backticks or invalid characters are within the diagram code.\n\n"
                "Generate the Mermaid diagram for the following schema:"
            )
        },
        {
            "role": "user",
            "content": schema_text
        }
    ]

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0,
            max_tokens=4096, # Adjusted token limit
            stream=False
        )
        mermaid_diagram = completion.choices[0].message.content.strip()

        # Extract content within ```mermaid ... ```
        match = re.search(r"```(?:mermaid)?\s*([\s\S]+?)\s*```", mermaid_diagram, re.IGNORECASE)
        if match:
            mermaid_diagram = match.group(1).strip()
        else:
            # Fallback if no backticks found, assume the whole response is the diagram
            pass 

        # Ensure it starts with erDiagram
        if not mermaid_diagram.startswith("erDiagram"):
             # If it contains erDiagram later, extract from there
            er_pos = mermaid_diagram.find("erDiagram")
            if er_pos != -1:
                mermaid_diagram = mermaid_diagram[er_pos:]
            else:
                 # If not found at all, prepend it
                mermaid_diagram = "erDiagram\n" + mermaid_diagram

        # Basic cleanup (remove potential extra mermaid tags, etc.)
        mermaid_diagram = mermaid_diagram.replace("```", "").strip()
        
        return mermaid_diagram

    except Exception as e:
        print(f"Error generating Mermaid diagram: {e}")
        return f"erDiagram\n%% Error generating diagram: {e} %%"


def generate_schema_commands_from_description(description):
    # Call the renamed function to get SQL
    schema_sql, _ = generate_sql_and_mermaid_from_description(description)
    # Split the generated SQL into individual commands (each ending with a semicolon)
    # NOTE: The 'mermaid' output is a formatted diagram representation, not a list of executable commands.
    commands = [stmt.strip() + ';' for stmt in schema_sql.split(';') if stmt.strip()]
    return commands # Return only commands
