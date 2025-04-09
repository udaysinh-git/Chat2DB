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