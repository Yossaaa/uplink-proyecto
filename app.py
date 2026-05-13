import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL (PORTAL UP) ---
st.set_page_config(page_title="UP Self-Service Portal", layout="wide", page_icon="🎓")

# Colores oficiales
azul_up = "#002b54"
rojo_up = "#b31d1d"
dorado_up = "#b38e5d"
gris_fondo = "#f4f4f4"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {gris_fondo}; }}
    
    /* Encabezado estilo Credencial/Portal */
    .portal-header {{
        background-color: {azul_up};
        color: white;
        padding: 20px;
        border-radius: 8px 8px 0 0;
        font-family: 'Arial', sans-serif;
        border-bottom: 4px solid {dorado_up};
    }}
    
    /* Tarjetas blancas con línea dorada */
    .up-card {{
        background-color: #ffffff;
        padding: 25px;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }}
    
    .up-title {{
        font-family: 'Times New Roman', serif;
        font-size: 26px;
        color: #333;
        margin-bottom: 5px;
    }}
    
    .gold-line {{
        width: 45px;
        height: 3px;
        background-color: {dorado_up};
        margin-bottom: 20px;
    }}

    /* Estilo del Chat */
    .chat-bubble-in {{ background-color: #f1f1f1; padding: 10px; border-radius: 10px; margin: 5px; border-left: 4px solid {dorado_up}; color: black; }}
    .chat-bubble-out {{ background-color: {azul_up}; color: white !important; padding: 10px; border-radius: 10px; margin: 5px; text-align: right; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS Y SEGURIDAD ---
def get_db():
    conn = sqlite3.connect('uplink_final_v16.db')
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Usuarios (con asesor asignado)
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (email TEXT PRIMARY KEY, password TEXT, rol TEXT, nombre TEXT, asesor_email TEXT)''')
    # Citas y Smart Quiz Integrado
    c.execute('''CREATE TABLE IF NOT EXISTS citas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_email TEXT, asesor_email TEXT, 
                  fecha TEXT, hora TEXT, q1 TEXT, q2 TEXT, otros TEXT, estructura TEXT, estado TEXT)''')
    # Disponibilidad de Asesores
    c.execute('''CREATE TABLE IF NOT EXISTS disponibilidad 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asesor_email TEXT, fecha TEXT, hora TEXT, estado TEXT,
                  UNIQUE(asesor_email, fecha, hora))''')
    # Chat
    c.execute('''CREATE TABLE IF NOT EXISTS mensajes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, emisor TEXT, receptor TEXT, mensaje TEXT, fecha_msj TEXT)''')
    conn.commit()
    conn.close()

def hash_pw(pw): return hashlib.sha256(str.encode(pw)).hexdigest()

init_db()

# --- 3. LÓGICA DE NEGOCIO (CALCULOS Y VALIDACIONES) ---
def calcular_15_min(q1, q2, otros):
    # Lógica de distribución proporcional del tiempo
    puntos = {"😫": 10, "☹️": 7, "😐": 4, "🙂": 2, "🤩": 1}
    v1 = puntos.get(q1, 5)
    v2 = puntos.get(q2, 5)
    v3 = 8 if otros else 2
    total = v1 + v2 + v3
    t_acad = round((v1/total)*15)
    t_soc = round((v2/total)*15)
    t_ext = 15 - t_acad - t_soc
    return f"📚 Académico: {t_acad}m | 🤝 Social: {t_soc}m | 💡 Extra: {t_ext}m"

# --- 4. COMPONENTE DE CHAT ---
def mostrar_chat(yo, otro):
    st.markdown("### 💬 Chat Institucional")
    conn = get_db()
    msjs = pd.read_sql_query(f"SELECT * FROM mensajes WHERE (emisor='{yo}' AND receptor='{otro}') OR (emisor='{otro}' AND receptor='{yo}') ORDER BY id ASC", conn)
    
    chat_container = st.container(height=350)
    with chat_container:
        for _, m in msjs.iterrows():
            clase = "chat-bubble-out" if m['emisor'] == yo else "chat-bubble-in"
            st.markdown(f'<div class="{clase}">{m["mensaje"]}<br><small style="font-size:10px;">{m["fecha_msj"]}</small></div>', unsafe_allow_html=True)
    
    with st.form("send_msg", clear_on_submit=True):
        c1, c2 = st.columns([4,1])
        texto = c1.text_input("Escribe mensaje...")
        if c2.form_submit_button("Enviar") and texto:
            c = conn.cursor()
            c.execute("INSERT INTO mensajes (emisor, receptor, mensaje, fecha_msj) VALUES (?,?,?,?)",
                      (yo, otro, texto, datetime.now().strftime("%H:%M")))
            conn.commit()
            st.rerun()
    conn.close()

# --- 5. VISTA ALUMNO ---
def vista_alumno():
    # Sidebar con diseño UP
    with st.sidebar:
        if os.path.exists("logo_up.png"): st.image("logo_up.png")
        st.markdown(f"**Bienvenido:**\n{st.session_state.nombre}")
        st.divider()
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    # Si no tiene asesor, forzar elección
    if not st.session_state.asesor_email:
        st.markdown('<div class="portal-header">Asignación de Asesor</div>', unsafe_allow_html=True)
        with st.container(border=True):
            conn = get_db()
            asesores = pd.read_sql_query("SELECT nombre, email FROM usuarios WHERE rol='Asesor'", conn)
            if not asesores.empty:
                dict_ase = {r['nombre']: r['email'] for _, r in asesores.iterrows()}
                sel_ase = st.selectbox("Selecciona tu asesor institucional para continuar:", list(dict_ase.keys()))
                if st.button("Confirmar Asesor"):
                    conn.execute("UPDATE usuarios SET asesor_email=? WHERE email=?", (dict_ase[sel_ase], st.session_state.user_email))
                    conn.commit()
                    st.session_state.asesor_email = dict_ase[sel_ase]
                    st.success("Asesor asignado.")
                    st.rerun()
            else: st.error("No hay asesores registrados aún.")
            conn.close()
            return

    # TABS PRINCIPALES
    st.markdown(f'<div class="portal-header">Panel de Alumno - Universidad Panamericana</div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Agendar Cita", "🗓️ Mi Calendario", "💬 Mensajes", "📊 Historial"])

    with tab1:
        st.markdown('<div class="up-card"><div class="up-title">Smart Quiz y Agendado</div><div class="gold-line"></div>', unsafe_allow_html=True)
        conn = get_db()
        # Validación: ¿Ya tiene una cita pendiente?
        ya_cita = pd.read_sql_query(f"SELECT * FROM citas WHERE alumno_email='{st.session_state.user_email}' AND estado='Pendiente'", conn)
        
        if not ya_cita.empty:
            st.warning("Ya tienes una cita agendada. Termina esa antes de pedir otra.")
        else:
            disp = pd.read_sql_query(f"SELECT * FROM disponibilidad WHERE asesor_email='{st.session_state.asesor_email}' AND estado='Libre'", conn)
            if not disp.empty:
                opciones = {f"{r['fecha']} a las {r['hora']}": r['id'] for _, r in disp.iterrows()}
                seleccion = st.selectbox("Espacios disponibles de tu asesor:", list(opciones.keys()))
                
                st.write("**Smart Quiz: Optimiza tus 15 minutos**")
                q1 = st.select_slider("¿Nivel de estrés académico?", options=["🤩", "🙂", "😐", "☹️", "😫"], value="😐")
                q2 = st.select_slider("¿Nivel de satisfacción social?", options=["🤩", "🙂", "😐", "☹️", "😫"], value="😐")
                otros = st.text_area("Notas adicionales o temas específicos:")
                
                if st.button("Confirmar Cita"):
                    estruc = calcular_15_min(q1, q2, otros)
                    f_c, h_c = seleccion.split(" a las ")
                    c = conn.cursor()
                    c.execute("UPDATE disponibilidad SET estado='Ocupado' WHERE id=?", (opciones[seleccion],))
                    c.execute("INSERT INTO citas (alumno_email, asesor_email, fecha, hora, q1, q2, otros, estructura, estado) VALUES (?,?,?,?,?,?,?,?,?)",
                              (st.session_state.user_email, st.session_state.asesor_email, f_c, h_c, q1, q2, otros, estruc, "Pendiente"))
                    conn.commit()
                    st.success(f"Cita agendada. Estructura: {estruc}")
                    st.rerun()
            else: st.info("Tu asesor no tiene horarios disponibles por ahora.")
        conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="up-card"><div class="up-title">Calendario de Sesiones</div><div class="gold-line"></div>', unsafe_allow_html=True)
        conn = get_db()
        citas_df = pd.read_sql_query(f"SELECT fecha, hora, estado FROM citas WHERE alumno_email='{st.session_state.user_email}'", conn)
        if not citas_df.empty:
            st.table(citas_df)
        else: st.write("No hay eventos en tu calendario.")
        conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        mostrar_chat(st.session_state.user_email, st.session_state.asesor_email)

    with tab4:
        conn = get_db()
        hist = pd.read_sql_query(f"SELECT * FROM citas WHERE alumno_email='{st.session_state.user_email}' AND estado='Completada'", conn)
        st.dataframe(hist)
        conn.close()

# --- 6. VISTA ASESOR ---
def vista_asesor():
    with st.sidebar:
        if os.path.exists("logo_up.png"): st.image("logo_up.png")
        st.markdown(f"**Asesor(a):**\n{st.session_state.nombre}")
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    st.markdown(f'<div class="portal-header">Portal de Facultad y Asesoría</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📋 Citas Pendientes", "🕒 Gestionar Disponibilidad", "💬 Chats"])

    with t1:
        st.markdown('<div class="up-card"><div class="up-title">Próximas Sesiones</div><div class="gold-line"></div>', unsafe_allow_html=True)
        conn = get_db()
        pendientes = pd.read_sql_query(f"SELECT * FROM citas WHERE asesor_email='{st.session_state.user_email}' AND estado='Pendiente'", conn)
        for _, r in pendientes.iterrows():
            with st.expander(f"Cita con {r['alumno_email']} - {r['fecha']}"):
                st.write(f"**Plan de 15 min:** {r['estructura']}")
                st.write(f"**Notas del alumno:** {r['otros']}")
                if st.button("Finalizar y Archivar", key=f"fin_{r['id']}"):
                    conn.execute("UPDATE citas SET estado='Completada' WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
        conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="up-card"><div class="up-title">Abrir Horarios</div><div class="gold-line"></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        f_nueva = c1.date_input("Día", min_value=datetime.now())
        h_nueva = c2.time_input("Hora")
        if st.button("Publicar Espacio"):
            conn = get_db()
            try:
                conn.execute("INSERT INTO disponibilidad (asesor_email, fecha, hora, estado) VALUES (?,?,?,?)",
                             (st.session_state.user_email, str(f_nueva), str(h_nueva)[:5], "Libre"))
                conn.commit()
                st.success("Horario abierto.")
            except: st.error("Ese horario ya lo habías publicado.")
            conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        conn = get_db()
        alums = pd.read_sql_query(f"SELECT email FROM usuarios WHERE asesor_email='{st.session_state.user_email}'", conn)
        if not alums.empty:
            target = st.selectbox("Selecciona alumno para chatear:", alums['email'])
            mostrar_chat(st.session_state.user_email, target)
        conn.close()

# --- 7. PÁGINA DE LOGIN Y REGISTRO (RÉPLICA FIEL) ---
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'user_email': '', 'rol': '', 'nombre': '', 'asesor_email': ''})

if not st.session_state.autenticado:
    # Centrar logo e imagen de bienvenida
    col_a, col_b, col_c = st.columns([1,2,1])
    with col_b:
        if os.path.exists("logo_up.png"): st.image("logo_up.png")
        st.markdown('<h1 style="text-align:center; font-family:serif;">Self-Service Portal</h1>', unsafe_allow_html=True)
        st.markdown('<center><div class="gold-line" style="width:100px; height:4px;"></div></center>', unsafe_allow_html=True)
        
        opcion = st.radio("Acción", ["Entrar al Portal", "Crear Nueva Cuenta"], horizontal=True)
        
        with st.container(border=True):
            if opcion == "Entrar al Portal":
                u = st.text_input("Correo Institucional (@up.edu.mx)")
                p = st.text_input("Contraseña", type="password")
                if st.button("Acceder", use_container_width=True):
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("SELECT password, rol, nombre, asesor_email FROM usuarios WHERE email=?", (u,))
                    res = c.fetchone()
                    if res and res[0] == hash_pw(p):
                        st.session_state.update({'autenticado': True, 'user_email': u, 'rol': res[1], 'nombre': res[2], 'asesor_email': res[3]})
                        st.rerun()
                    else: st.error("Credenciales incorrectas.")
                    conn.close()
            else:
                n_reg = st.text_input("Nombre Completo")
                u_reg = st.text_input("Correo @up.edu.mx")
                p_reg = st.text_input("Define Contraseña", type="password")
                r_reg = st.selectbox("Tipo de perfil", ["Alumno", "Asesor"])
                if st.button("Registrarme", use_container_width=True):
                    if u_reg.endswith("@up.edu.mx") and n_reg:
                        conn = get_db()
                        try:
                            conn.execute("INSERT INTO usuarios VALUES (?,?,?,?,?)", (u_reg, hash_pw(p_reg), r_reg, n_reg, ""))
                            conn.commit()
                            st.success("Cuenta creada. Ahora entra al portal.")
                        except: st.error("Este correo ya está registrado.")
                        conn.close()
                    else: st.error("Datos inválidos o no es correo institucional.")
else:
    if st.session_state.rol == "Alumno": vista_alumno()
    else: vista_asesor()