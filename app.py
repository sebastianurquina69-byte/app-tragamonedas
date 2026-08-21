import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from database import init_db, get_connection
from utils import export_to_excel
import io

# Page config
st.set_page_config(page_title="Máquinas Tragamonedas", layout="wide", initial_sidebar_state="expanded")

# Initialize database
init_db()

# Initialize session state for confirmations
if "confirm_delete_machine" not in st.session_state:
    st.session_state.confirm_delete_machine = None
if "confirm_delete_location" not in st.session_state:
    st.session_state.confirm_delete_location = None
if "confirm_delete_income" not in st.session_state:
    st.session_state.confirm_delete_income = None
if "confirm_delete_expense" not in st.session_state:
    st.session_state.confirm_delete_expense = None

# Sidebar navigation
st.sidebar.title("🎰 Control de Máquinas")
page = st.sidebar.radio("Navegación", 
    ["Dashboard", "Máquinas", "Ubicaciones", "Finanzas", "Reportes"])

def get_machines_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM machines")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(amount) FROM income")
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(amount) FROM expenses")
    total_expenses = cursor.fetchone()[0] or 0
    
    conn.close()
    return total_income, total_expenses, total_income - total_expenses

# ============ DASHBOARD ============
if page == "Dashboard":
    st.title("📊 Dashboard de Rentabilidad")
    
    total_income, total_expenses, net = get_total_stats()
    machines_count = get_machines_count()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Ingresos Totales", f"${total_income:,.0f}", delta=None)
    col2.metric("💸 Gastos Totales", f"${total_expenses:,.0f}", delta=None)
    col3.metric("📈 Rentabilidad Neta", f"${net:,.0f}", 
                delta=f"{(net/total_income*100) if total_income > 0 else 0:.1f}%")
    col4.metric("🎰 Máquinas Activas", f"{machines_count}", delta=None)
    
    # Rentability by machine type
    st.subheader("Rentabilidad por Tipo de Máquina")
    conn = get_connection()
    query = """
    SELECT m.type, COUNT(m.id) as count, COALESCE(SUM(i.amount), 0) as income, 
           COALESCE(SUM(e.amount), 0) as expenses
    FROM machines m
    LEFT JOIN income i ON m.id = i.machine_id
    LEFT JOIN expenses e ON m.id = e.machine_id
    GROUP BY m.type
    """
    df_type = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df_type.empty:
        df_type['Rentabilidad'] = df_type['income'] - df_type['expenses']
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(df_type, x='type', y='Rentabilidad', 
                        title="Rentabilidad por Tipo", color='Rentabilidad',
                        color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(df_type[['type', 'count', 'income', 'expenses', 'Rentabilidad']], 
                        use_container_width=True, hide_index=True)
    
    # Top machines by profitability
    st.subheader("Top 10 Máquinas por Rentabilidad")
    conn = get_connection()
    query = """
    SELECT m.id, m.type, COALESCE(SUM(i.amount), 0) as income,
           COALESCE(SUM(e.amount), 0) as expenses
    FROM machines m
    LEFT JOIN income i ON m.id = i.machine_id
    LEFT JOIN expenses e ON m.id = e.machine_id
    GROUP BY m.id
    ORDER BY (income - expenses) DESC
    LIMIT 10
    """
    df_top = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df_top.empty:
        df_top['Rentabilidad'] = df_top['income'] - df_top['expenses']
        fig = px.bar(df_top, x='id', y='Rentabilidad', color='type',
                    title="Top 10 Máquinas por Rentabilidad")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_top, use_container_width=True, hide_index=True)

# ============ MÁQUINAS ============
elif page == "Máquinas":
    st.title("🎰 Gestión de Máquinas")
    
    tab1, tab2 = st.tabs(["Inventario", "Agregar Máquina"])
    
    with tab1:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.type, m.status, COALESCE(l.landlord, 'Sin asignar') as landlord
            FROM machines m
            LEFT JOIN locations l ON m.id = l.machine_id
            ORDER BY m.id
        """)
        machines = cursor.fetchall()
        conn.close()
        
        if machines:
            df = pd.DataFrame(machines, columns=["ID", "Tipo", "Estado", "Arrendatario"])
            # Reordenar columnas: ID, Arrendatario, Tipo, Estado
            df = df[['ID', 'Arrendatario', 'Tipo', 'Estado']]
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Delete machine section
            st.subheader("⚠️ Eliminar Máquina")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                machine_to_delete = st.selectbox(
                    "Selecciona máquina a eliminar",
                    [m[0] for m in machines],
                    format_func=lambda x: f"#{x} - {df[df['ID']==x]['Arrendatario'].values[0]}",
                    key="delete_machine"
                )
            with col2:
                if st.button("🗑️ Eliminar", use_container_width=True, key="btn_delete_machine"):
                    st.session_state.confirm_delete_machine = machine_to_delete
            with col3:
                if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_delete_machine"):
                    st.session_state.confirm_delete_machine = None
            
            # Confirmation dialog
            if st.session_state.confirm_delete_machine is not None:
                st.warning(f"⚠️ ¿CONFIRMÁS que deseas eliminar la Máquina #{st.session_state.confirm_delete_machine}?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✓ SÍ, Eliminar", use_container_width=True, key="btn_confirm_delete"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        try:
                            cursor.execute("DELETE FROM machines WHERE id = ?", (st.session_state.confirm_delete_machine,))
                            conn.commit()
                            st.success(f"✓ Máquina #{st.session_state.confirm_delete_machine} eliminada")
                            st.session_state.confirm_delete_machine = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                        finally:
                            conn.close()
                with col2:
                    if st.button("✗ NO, Cancelar", use_container_width=True, key="btn_cancel_confirm"):
                        st.session_state.confirm_delete_machine = None
                        st.rerun()
            
            # Filter by type
            st.subheader("Filtrar por Tipo")
            machine_types = df['Tipo'].unique()
            selected_type = st.selectbox("Tipo de Máquina", machine_types, key="filter_machine_type")
            df_filtered = df[df['Tipo'] == selected_type]
            st.write(f"Total {selected_type}: {len(df_filtered)}")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        else:
            st.info("No hay máquinas registradas")
    
    with tab2:
        st.subheader("Agregar Nueva Máquina")
        machine_type = st.selectbox("Tipo de Máquina", ["Pikachu", "Pinball"], key="add_machine_type")
        status = st.selectbox("Estado", ["Activa", "Mantenimiento", "Inactiva"], key="add_machine_status")
        
        if st.button("➕ Agregar Máquina", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO machines (type, status) VALUES (?, ?)", 
                          (machine_type, status))
            conn.commit()
            machine_id = cursor.lastrowid
            conn.close()
            st.success(f"✓ Máquina #{machine_id} agregada exitosamente")
            st.rerun()

# ============ UBICACIONES ============
elif page == "Ubicaciones":
    st.title("📍 Gestión de Ubicaciones y Alquileres")
    
    tab1, tab2 = st.tabs(["Ubicaciones", "Agregar Ubicación"])
    
    with tab1:
        conn = get_connection()
        query = """
        SELECT l.id, l.city, l.neighborhood, l.landlord, l.phone, m.id as machine_id, m.type
        FROM locations l
        LEFT JOIN machines m ON l.machine_id = m.id
        ORDER BY l.city
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Delete location section
            st.subheader("⚠️ Eliminar Ubicación/Arrendatario")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                location_to_delete = st.selectbox(
                    "Selecciona ubicación a eliminar",
                    df['id'].values,
                    format_func=lambda x: f"{df[df['id']==x]['landlord'].values[0]} - {df[df['id']==x]['city'].values[0]}",
                    key="delete_location"
                )
            with col2:
                if st.button("🗑️ Eliminar", use_container_width=True, key="btn_delete_location"):
                    st.session_state.confirm_delete_location = location_to_delete
            with col3:
                if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_delete_location"):
                    st.session_state.confirm_delete_location = None
            
            # Confirmation dialog
            if st.session_state.confirm_delete_location is not None:
                landlord_name = df[df['id'] == st.session_state.confirm_delete_location]['landlord'].values[0]
                city_name = df[df['id'] == st.session_state.confirm_delete_location]['city'].values[0]
                st.warning(f"⚠️ ¿CONFIRMÁS que deseas eliminar a {landlord_name} de {city_name}?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✓ SÍ, Eliminar", use_container_width=True, key="btn_confirm_delete_loc"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        try:
                            cursor.execute("DELETE FROM locations WHERE id = ?", (st.session_state.confirm_delete_location,))
                            conn.commit()
                            st.success(f"✓ Ubicación eliminada")
                            st.session_state.confirm_delete_location = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                        finally:
                            conn.close()
                with col2:
                    if st.button("✗ NO, Cancelar", use_container_width=True, key="btn_cancel_confirm_loc"):
                        st.session_state.confirm_delete_location = None
                        st.rerun()
        else:
            st.info("No hay ubicaciones registradas")
    
    with tab2:
        st.subheader("Registrar Nueva Ubicación")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, type FROM machines WHERE id NOT IN (SELECT machine_id FROM locations)")
        available_machines = cursor.fetchall()
        conn.close()
        
        city = st.text_input("Ciudad/Pueblo", placeholder="ej. Neiva")
        neighborhood = st.text_input("Barrio", placeholder="ej. Centro")
        landlord = st.text_input("Nombre del Arrendatario")
        phone = st.text_input("Celular de Contacto", placeholder="ej. 3101234567")
        
        if available_machines:
            machine_choice = st.selectbox("Máquina a Asignar", 
                                         [(m[0], f"#{m[0]} ({m[1]})") for m in available_machines],
                                         format_func=lambda x: x[1])
            machine_id = machine_choice[0]
            
            if st.button("➕ Registrar Ubicación", use_container_width=True):
                if city and neighborhood and landlord and phone:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO locations (city, neighborhood, landlord, phone, machine_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (city, neighborhood, landlord, phone, machine_id))
                    conn.commit()
                    conn.close()
                    st.success("✓ Ubicación registrada exitosamente")
                    st.rerun()
                else:
                    st.error("Completa todos los campos")
        else:
            st.warning("No hay máquinas disponibles sin asignar")

# ============ FINANZAS ============
elif page == "Finanzas":
    st.title("💵 Control Financiero")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Ingresos", "Gastos", "Eliminar", "Resumen"])
    
    with tab1:
        st.subheader("Registrar Ingreso (Recaudo)")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM machines")
        machines = [m[0] for m in cursor.fetchall()]
        conn.close()
        
        if machines:
            machine_id = st.selectbox("Máquina", machines, key="income_machine_select")
            amount = st.number_input("Cantidad ($)", min_value=0.0, step=1000.0)
            date = st.date_input("Fecha del Recaudo", datetime.now())
            
            if st.button("💰 Registrar Ingreso", use_container_width=True):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO income (machine_id, amount, date)
                    VALUES (?, ?, ?)
                """, (machine_id, amount, date))
                conn.commit()
                conn.close()
                st.success("✓ Ingreso registrado")
                st.rerun()
    
    with tab2:
        st.subheader("Registrar Gasto (Mantenimiento/Repuestos)")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM machines")
        machines = [m[0] for m in cursor.fetchall()]
        conn.close()
        
        if machines:
            machine_id = st.selectbox("Máquina", machines, key="expense_machine_select")
            expense_type = st.selectbox("Tipo de Gasto", ["Repuestos", "Mantenimiento", "Transporte"], key="expense_type_select")
            amount = st.number_input("Cantidad ($)", min_value=0.0, step=1000.0, key="expense_amount")
            date = st.date_input("Fecha del Gasto", datetime.now(), key="expense_date")
            description = st.text_area("Descripción")
            
            if st.button("📝 Registrar Gasto", use_container_width=True):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO expenses (machine_id, expense_type, amount, date, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (machine_id, expense_type, amount, date, description))
                conn.commit()
                conn.close()
                st.success("✓ Gasto registrado")
                st.rerun()
    
    with tab3:
        st.subheader("⚠️ Eliminar Ingresos o Gastos")
        
        delete_type = st.radio("¿Qué deseas eliminar?", ["Ingresos", "Gastos"], horizontal=True)
        
        conn = get_connection()
        
        if delete_type == "Ingresos":
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.machine_id, i.amount, i.date
                FROM income i
                ORDER BY i.date DESC
            """)
            records = cursor.fetchall()
            
            if records:
                df_records = pd.DataFrame(records, columns=["ID", "Máquina", "Monto", "Fecha"])
                st.dataframe(df_records, use_container_width=True, hide_index=True)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    income_to_delete = st.selectbox(
                        "Selecciona ingreso a eliminar",
                        [r[0] for r in records],
                        format_func=lambda x: f"Máquina #{df_records[df_records['ID']==x]['Máquina'].values[0]} - ${df_records[df_records['ID']==x]['Monto'].values[0]:,.0f} ({df_records[df_records['ID']==x]['Fecha'].values[0]})",
                        key="delete_income"
                    )
                with col2:
                    if st.button("🗑️ Eliminar", use_container_width=True, key="btn_delete_income"):
                        st.session_state.confirm_delete_income = income_to_delete
                with col3:
                    if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_delete_income"):
                        st.session_state.confirm_delete_income = None
                
                if st.session_state.confirm_delete_income is not None:
                    income_amount = df_records[df_records['ID'] == st.session_state.confirm_delete_income]['Monto'].values[0]
                    st.warning(f"⚠️ ¿CONFIRMÁS que deseas eliminar este ingreso de ${income_amount:,.0f}?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✓ SÍ, Eliminar", use_container_width=True, key="btn_confirm_delete_income"):
                            cursor = conn.cursor()
                            try:
                                cursor.execute("DELETE FROM income WHERE id = ?", (st.session_state.confirm_delete_income,))
                                conn.commit()
                                st.success(f"✓ Ingreso eliminado")
                                st.session_state.confirm_delete_income = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    with col2:
                        if st.button("✗ NO, Cancelar", use_container_width=True, key="btn_cancel_confirm_income"):
                            st.session_state.confirm_delete_income = None
                            st.rerun()
            else:
                st.info("No hay ingresos registrados")
        
        else:  # Gastos
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.id, e.machine_id, e.expense_type, e.amount, e.date
                FROM expenses e
                ORDER BY e.date DESC
            """)
            records = cursor.fetchall()
            
            if records:
                df_records = pd.DataFrame(records, columns=["ID", "Máquina", "Tipo", "Monto", "Fecha"])
                st.dataframe(df_records, use_container_width=True, hide_index=True)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    expense_to_delete = st.selectbox(
                        "Selecciona gasto a eliminar",
                        [r[0] for r in records],
                        format_func=lambda x: f"Máquina #{df_records[df_records['ID']==x]['Máquina'].values[0]} - {df_records[df_records['ID']==x]['Tipo'].values[0]} ${df_records[df_records['ID']==x]['Monto'].values[0]:,.0f}",
                        key="delete_expense"
                    )
                with col2:
                    if st.button("🗑️ Eliminar", use_container_width=True, key="btn_delete_expense"):
                        st.session_state.confirm_delete_expense = expense_to_delete
                with col3:
                    if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_delete_expense"):
                        st.session_state.confirm_delete_expense = None
                
                if st.session_state.confirm_delete_expense is not None:
                    expense_amount = df_records[df_records['ID'] == st.session_state.confirm_delete_expense]['Monto'].values[0]
                    expense_type = df_records[df_records['ID'] == st.session_state.confirm_delete_expense]['Tipo'].values[0]
                    st.warning(f"⚠️ ¿CONFIRMÁS que deseas eliminar este gasto de {expense_type} ${expense_amount:,.0f}?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✓ SÍ, Eliminar", use_container_width=True, key="btn_confirm_delete_expense"):
                            cursor = conn.cursor()
                            try:
                                cursor.execute("DELETE FROM expenses WHERE id = ?", (st.session_state.confirm_delete_expense,))
                                conn.commit()
                                st.success(f"✓ Gasto eliminado")
                                st.session_state.confirm_delete_expense = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    with col2:
                        if st.button("✗ NO, Cancelar", use_container_width=True, key="btn_cancel_confirm_expense"):
                            st.session_state.confirm_delete_expense = None
                            st.rerun()
            else:
                st.info("No hay gastos registrados")
        
        conn.close()
    
    with tab4:
        st.subheader("Resumen Financiero")
        conn = get_connection()
        
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM income")
        total_income = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM expenses")
        total_expenses = cursor.fetchone()[0] or 0
        
        net_profit = total_income - total_expenses
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ingresos", f"${total_income:,.0f}")
        col2.metric("Total Gastos", f"${total_expenses:,.0f}")
        col3.metric("Ganancia Neta", f"${net_profit:,.0f}")
        
        # Recent transactions
        st.subheader("Transacciones Recientes")
        cursor.execute("""
            SELECT 'Ingreso' as tipo, machine_id, amount, date FROM income
            UNION ALL
            SELECT 'Gasto', machine_id, amount, date FROM expenses
            ORDER BY date DESC LIMIT 20
        """)
        transactions = cursor.fetchall()
        conn.close()
        
        if transactions:
            df = pd.DataFrame(transactions, columns=["Tipo", "Máquina", "Monto", "Fecha"])
            st.dataframe(df, use_container_width=True, hide_index=True)

# ============ REPORTES ============
elif page == "Reportes":
    st.title("📈 Reportes y Análisis")
    
    tab1, tab2 = st.tabs(["Reporte Mensual", "Exportar a Excel"])
    
    with tab1:
        st.subheader("Reporte Mensual")
        
        col1, col2 = st.columns(2)
        with col1:
            selected_month_num = st.selectbox("Mes", range(1, 13), format_func=lambda x: datetime(2024, x, 1).strftime('%B'), index=datetime.now().month-1)
        with col2:
            selected_year = st.number_input("Año", value=datetime.now().year, min_value=2020)
        
        selected_month = datetime(selected_year, selected_month_num, 1)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Income for month
        cursor.execute("""
            SELECT SUM(amount) FROM income 
            WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
        """, (f"{selected_month.month:02d}", str(selected_year)))
        month_income = cursor.fetchone()[0] or 0
        
        # Expenses for month
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
        """, (f"{selected_month.month:02d}", str(selected_year)))
        month_expenses = cursor.fetchone()[0] or 0
        
        conn.close()
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Ingresos {selected_month.strftime('%B')}", f"${month_income:,.0f}")
        col2.metric(f"Gastos {selected_month.strftime('%B')}", f"${month_expenses:,.0f}")
        col3.metric("Ganancia Mensual", f"${month_income - month_expenses:,.0f}")
        
        # Detailed breakdown
        st.subheader("Desglose Detallado")
        conn = get_connection()
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.type, SUM(i.amount) as income, SUM(e.amount) as expenses
            FROM machines m
            LEFT JOIN income i ON m.id = i.machine_id AND strftime('%m', i.date) = ? 
                                AND strftime('%Y', i.date) = ?
            LEFT JOIN expenses e ON m.id = e.machine_id AND strftime('%m', e.date) = ? 
                                  AND strftime('%Y', e.date) = ?
            GROUP BY m.id
            ORDER BY m.id
        """, (f"{selected_month.month:02d}", str(selected_year), 
              f"{selected_month.month:02d}", str(selected_year)))
        
        data = cursor.fetchall()
        conn.close()
        
        if data:
            df = pd.DataFrame(data, columns=["ID", "Tipo", "Ingresos", "Gastos"])
            df["Ingresos"] = df["Ingresos"].fillna(0)
            df["Gastos"] = df["Gastos"].fillna(0)
            df["Rentabilidad"] = df["Ingresos"] - df["Gastos"]
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Exportar Base de Datos a Excel")
        st.write("Descarga todos los datos de tu negocio en un archivo Excel")
        
        if st.button("📥 Generar Archivo Excel", use_container_width=True):
            excel_file = export_to_excel()
            st.download_button(
                label="⬇️ Descargar Excel",
                data=excel_file,
                file_name=f"negocio_maquinas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
