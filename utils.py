import pandas as pd
from database import get_connection
import io

def export_to_excel():
    """Export all database tables to Excel file"""
    conn = get_connection()
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Machines
        df_machines = pd.read_sql_query("SELECT * FROM machines", conn)
        df_machines.to_excel(writer, sheet_name='Máquinas', index=False)
        
        # Locations
        df_locations = pd.read_sql_query("""
            SELECT l.*, m.type as machine_type 
            FROM locations l 
            LEFT JOIN machines m ON l.machine_id = m.id
        """, conn)
        df_locations.to_excel(writer, sheet_name='Ubicaciones', index=False)
        
        # Income
        df_income = pd.read_sql_query("""
            SELECT i.*, m.type 
            FROM income i 
            LEFT JOIN machines m ON i.machine_id = m.id
        """, conn)
        df_income.to_excel(writer, sheet_name='Ingresos', index=False)
        
        # Expenses
        df_expenses = pd.read_sql_query("""
            SELECT e.*, m.type 
            FROM expenses e 
            LEFT JOIN machines m ON e.machine_id = m.id
        """, conn)
        df_expenses.to_excel(writer, sheet_name='Gastos', index=False)
        
        # Summary
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM income")
        total_income = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM expenses")
        total_expenses = cursor.fetchone()[0] or 0
        
        summary_data = {
            'Concepto': ['Total Ingresos', 'Total Gastos', 'Ganancia Neta'],
            'Monto': [total_income, total_expenses, total_income - total_expenses]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Resumen', index=False)
    
    conn.close()
    output.seek(0)
    return output.getvalue()
