import psycopg2
import os
from datetime import datetime
from config import settings

def connect_to_db():
    """Connect to PostgreSQL database using project config"""
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database="alfaconnect_bot" 
        )
        return conn
    except Exception as e:
        return f"Database connection error: {e}"

def get_enums_structure(cursor):
    """Get all ENUM types and their values"""
    try:
        cursor.execute("""
            SELECT t.typname AS enum_name,  
                   e.enumlabel AS enum_value
            FROM pg_type t 
            JOIN pg_enum e ON t.oid = e.enumtypid  
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = 'public'
            ORDER BY t.typname, e.enumsortorder;
        """)
        
        enums = cursor.fetchall()
        if not enums:
            return None
            
        # Group enums by name
        enum_dict = {}
        for enum_name, enum_value in enums:
            if enum_name not in enum_dict:
                enum_dict[enum_name] = []
            enum_dict[enum_name].append(enum_value)
        
        return enum_dict
    except Exception as e:
        return f"Error fetching enums: {e}"

def get_table_row_count(cursor, table_name):
    """Get row count for a specific table"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except:
        return "N/A"

def get_table_structure():
    """Get structure of all tables and return as string"""
    conn = connect_to_db()
    if isinstance(conn, str):  # Error message
        return conn
    
    cursor = conn.cursor()
    output = []
    
    # Get all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    tables = cursor.fetchall()
    
    output.append("=" * 80)
    output.append("DATABASE STRUCTURE ANALYSIS")
    output.append("=" * 80)
    output.append(f"Total tables found: {len(tables)}")
    output.append("")
    
    # Get and display ENUM types first
    enums = get_enums_structure(cursor)
    if enums and not isinstance(enums, str):
        output.append("ENUM TYPES:")
        output.append("-" * 50)
        for enum_name, enum_values in enums.items():
            output.append(f"  {enum_name}:")
            for value in enum_values:
                output.append(f"    - {value}")
            output.append("")
    elif isinstance(enums, str):
        output.append(f"Error getting enums: {enums}")
        output.append("")
    
    for table in tables:
        table_name = table[0]
        row_count = get_table_row_count(cursor, table_name)
        
        output.append(f"TABLE: {table_name}")
        output.append(f"Row count: {row_count}")
        output.append("-" * 50)
        
        # Get columns for this table
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        if columns:
            output.append(f"{'Column Name':<25} {'Type':<25} {'Nullable':<10} {'Default':<15}")
            output.append("-" * 75)
            
            for col in columns:
                col_name, data_type, nullable, default, max_length, precision, scale = col
                
                # Format data type with length/precision if applicable
                if max_length and data_type in ['character varying', 'character']:
                    data_type = f"{data_type}({max_length})"
                elif precision is not None and data_type in ['numeric', 'decimal']:
                    if scale is not None:
                        data_type = f"{data_type}({precision},{scale})"
                    else:
                        data_type = f"{data_type}({precision})"
                
                # Format nullable
                nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
                
                # Format default
                default_str = str(default) if default else ""
                if len(default_str) > 12:
                    default_str = default_str[:12] + "..."
                
                output.append(f"{col_name:<25} {data_type:<25} {nullable_str:<10} {default_str:<15}")
        else:
            output.append("No columns found")
        
        output.append("")
        
        # Get indexes for this table
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes 
            WHERE tablename = %s
            AND schemaname = 'public'
        """, (table_name,))
        
        indexes = cursor.fetchall()
        if indexes:
            output.append("INDEXES:")
            for idx in indexes:
                # Simplify index definition for readability
                idx_def = idx[1]
                if "USING" in idx_def:
                    idx_def = idx_def.split("USING")[0].strip() + " ..."
                output.append(f"  - {idx[0]}: {idx_def}")
            output.append("")
        
        # Get foreign keys for this table
        cursor.execute("""
            SELECT 
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
        """, (table_name,))
        
        foreign_keys = cursor.fetchall()
        if foreign_keys:
            output.append("FOREIGN KEYS:")
            for fk in foreign_keys:
                output.append(f"  - {fk[2]} -> {fk[3]}.{fk[4]}")
            output.append("")
        
        # Get constraints (primary key, unique, check)
        cursor.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = %s
            AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'CHECK')
            ORDER BY constraint_type, constraint_name
        """, (table_name,))
        
        constraints = cursor.fetchall()
        if constraints:
            output.append("CONSTRAINTS:")
            for constraint_name, constraint_type in constraints:
                output.append(f"  - {constraint_type}: {constraint_name}")
            output.append("")
        
        output.append("=" * 80)
        output.append("")
    
    cursor.close()
    conn.close()
    return "\n".join(output)

def get_database_summary():
    """Get summary statistics about the database"""
    conn = connect_to_db()
    if isinstance(conn, str):
        return conn
    
    cursor = conn.cursor()
    output = []
    
    # Get total tables count
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    total_tables = cursor.fetchone()[0]
    
    # Get total rows across all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    total_rows = 0
    largest_table = {"name": "", "rows": 0}
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            total_rows += row_count
            if row_count > largest_table["rows"]:
                largest_table = {"name": table, "rows": row_count}
        except:
            continue
    
    # Get ENUM types count
    enums = get_enums_structure(cursor)
    enum_count = len(enums) if enums and not isinstance(enums, str) else 0
    
    output.append("DATABASE SUMMARY")
    output.append("=" * 50)
    output.append(f"Total tables: {total_tables}")
    output.append(f"Total rows: {total_rows}")
    output.append(f"Largest table: {largest_table['name']} ({largest_table['rows']} rows)")
    output.append(f"ENUM types: {enum_count}")
    output.append("")
    
    cursor.close()
    conn.close()
    return "\n".join(output)

def analyze_project_requirements(conn=None):
    """Analyze if database matches project requirements and return as string"""
    output = []
    output.append("ALFABOT PROJECT REQUIREMENTS ANALYSIS")
    output.append("=" * 80)
    
    # Get actual tables from database if connection provided
    if conn:
        actual_tables = get_all_tables(conn)
        output.append("Actual tables found in database:")
        for table in actual_tables:
            output.append(f"  ✓ {table}")
    else:
        # Fallback to expected tables based on migrations
        expected_tables = [
            "users", "tarif", "connection_orders", "technician_orders",
            "staff_orders", "materials", "material_requests",
            "regions", "user_sessions", "audit_logs"
        ]
        output.append("Expected tables based on alfabot project structure:")
        for table in expected_tables:
            output.append(f"  ✓ {table}")
    
    output.append("")
    output.append("Key features that should be supported:")
    output.append("  - Multi-role user system (admin, client, manager, technician, etc.)")
    output.append("  - Connection order management workflow")
    output.append("  - Technical service order workflow")
    output.append("  - Materials and inventory management")
    output.append("  - Regional service management")
    output.append("  - Status tracking and transitions")
    output.append("  - Telegram bot integration")
    output.append("  - Multi-language support (uz/ru)")
    
    return "\n".join(output)

def get_all_tables(conn):
    """Get all table names from the database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables
    except Exception as e:
        return []

def save_database_analysis_to_file():
    """Save complete alfabot database analysis to a text file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alfabot_database_analysis_{timestamp}.txt"
    
    # Get database structure
    structure_analysis = get_table_structure()
    
    # Get database summary
    summary = get_database_summary()
    
    # Get project requirements analysis
    conn = connect_to_db()
    requirements_analysis = analyze_project_requirements(conn)
    if isinstance(conn, str) == False:  # Close connection if it's valid
        conn.close()
    
    # Combine all analysis
    full_analysis = f"""
ALFABOT DATABASE ANALYSIS REPORT
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*80}

{summary}

{structure_analysis}

{requirements_analysis}

{'='*80}
END OF ALFABOT REPORT
"""
    
    # Write to file
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(full_analysis)
        print(f"✅ Alfabot database analysis saved to: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Error saving alfabot analysis file: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Alfabot Database Analysis Tool")
    print("=" * 50)
    
    saved_file = save_database_analysis_to_file()
    if saved_file:
        print(f"📄 Alfabot analysis completed and saved to: {saved_file}")
    else:
        print("❌ Failed to save alfabot analysis to file")