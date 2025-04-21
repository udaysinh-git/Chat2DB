from langchain_groq import ChatGroq
import os
import re

def generate_schema_from_description(description):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    model_name = "mistral-saba-24b"

    # Prompt with detailed rules for both SQL DDL and Mermaid ER diagram generation
    prompt = f"""
You are a deterministic assistant that converts database descriptions into:
1. Valid, production-ready MySQL DDL statements (CREATE TABLE, PK, FK, etc).
2. Valid Mermaid JS ER diagrams.

**SQL DDL Generation Rules:**
- Use only MySQL syntax.
- Always specify primary keys (PK) and foreign keys (FK) explicitly.
- Use `INT`, `VARCHAR(n)`, `DATE`, `DECIMAL(x_y)`, `ENUM`, etc. Use reasonable lengths.
- For `DECIMAL`, replace commas in size with underscores, e.g. `DECIMAL(10_2)`.
- For `ENUM`, do not include enumeration values or quotes, just use `ENUM` as the type.
- Do not use backticks or quotes around identifiers.
- Do not include stray backticks or extra formatting.
- Each statement must end with a semicolon.
- Use only ASCII characters.

**Mermaid ER Diagram Rules:**
- Each table must be represented as an entity block:
  ```
  <table_name> {{
      <data_type> <attribute_name> [optional annotations such as PK, FK]
      ...
  }}
  ```
- Automatically detect relationships using foreign keys (FK) and primary keys (PK).
- Use this Mermaid syntax for relationships:
  ```
  parent_table ||--o{{ child_table : "FK relationship"
  ```
- For each foreign key in a table, create a one-to-many relationship.
- Replace any commas in data type definitions with an underscore (e.g. `decimal(10_2)`).
- For enums, output as `enum <attribute_name>`.
- The entire Mermaid diagram must be enclosed in a single pair of triple backticks, with no stray backticks inside.
- No enumeration values or quotes in enum types.
- No extra formatting tokens (such as stray backticks) within the Mermaid code.
- Ensure every table appears as an entity block, all attributes have sanitized data types, and all FK relationships are represented.

Given this database description, first infer the tables, columns, primary keys, and foreign keys, then generate:
1. The SQL DDL statements (MySQL) to create all tables and relationships, following the above rules.
2. A Mermaid ER diagram (erDiagram) representing the schema, following the above rules.

Description:
{description}

Respond in this format:
SQL:
```
<sql>
```
MERMAID:
```
<mermaid>
```
"""

    llm = ChatGroq(model=model_name, groq_api_key=groq_api_key, temperature=1)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else response["content"]

    sql_match = re.search(r"SQL:\s*```(?:sql)?\s*([\s\S]+?)\s*```", content)
    mermaid_match = re.search(r"MERMAID:\s*```(?:mermaid)?\s*([\s\S]+?)\s*```", content)
    schema_sql = sql_match.group(1).strip() if sql_match else ""
    mermaid = mermaid_match.group(1).strip() if mermaid_match else ""
    return schema_sql, mermaid

def generate_schema_commands_from_description(description):
    # Call the existing function
    schema_sql, mermaid = generate_schema_from_description(description)
    # Split the generated SQL into individual commands (each ending with a semicolon)
    # NOTE: The 'mermaid' output is a formatted diagram representation, not a list of executable commands.
    commands = [stmt.strip() + ';' for stmt in schema_sql.split(';') if stmt.strip()]
    return commands, mermaid
