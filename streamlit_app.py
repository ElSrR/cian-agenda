# -*- coding: utf-8 -*-
import os
import datetime as dt
from typing import Any, Dict, List
import pandas as pd
import altair as alt
import streamlit as st

# SQLAlchemy (Neon/Postgres)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

APP_TITLE = "CIAN — Agenda de Pacientes (MVP)"
DEFAULT_BLOCK_MIN = int(st.secrets.get("block_minutes", 30))

# ---------- Auth (simple) ----------
def require_auth():
    if "authed" not in st.session_state:
        st.session_state.authed = False
    if not st.session_state.authed:
        st.title(APP_TITLE)
        st.subheader("Acceso")
        st.caption("Ingreso protegido por clave (configura `app_password` en *Secrets* de Streamlit).")
        email = st.text_input("Email (solo referencia)")
        pwd = st.text_input("Clave", type="password")
        if st.button("Entrar", use_container_width=True):
            expected = st.secrets.get("app_password", None)
            if expected and pwd == expected:
                st.session_state.authed = True
                st.session_state.user_email = email
                st.success("Acceso concedido")
                st.rerun()
            else:
                st.error("Clave incorrecta o no configurada.")
        st.stop()

# ---------- DB (Neon/Postgres via SQLAlchemy) + CSV fallback ----------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_engine: Engine | None = None
def get_engine() -> Engine | None:
    """Return SQLAlchemy engine if DB URL exists in secrets; else None."""
    global _engine
    if _engine is not None:
        return _engine
    # Secrets format: [db] url="postgresql+psycopg2://USER:PASS@HOST/DB?sslmode=require"
    db_url = None
    try:
        db_url = st.secrets["db"]["url"]
    except Exception:
        pass
    if db_url:
        _engine = create_engine(db_url, pool_pre_ping=True)
        return _engine
    return None

def csv_path(name:str) -> str:
    return os.path.join(DATA_DIR, f"{name}.csv")

def fetch_table(name:str) -> pd.DataFrame:
    eng = get_engine()
    if eng is not None:
        with eng.begin() as conn:
            df = pd.read_sql(text(f"select * from {name}"), conn)
        return df
    # CSV fallback (local testing)
    p = csv_path(name)
    if os.path.exists(p):
        return pd.read_csv(p)
    # default empty schemas
    cols = {
        "patients": ["id","full_name","rut","birth_date","phone","email","created_at"],
        "professionals": ["id","full_name","specialty","created_at"],
        "services": ["id","name","duration_minutes","price","created_at"],
        "appointments": ["id","patient_id","professional_id","service_id","date","start_time","end_time","status","notes","price","created_at"],
    }
    return pd.DataFrame(columns=cols.get(name, []))

def insert_row(table:str, data:Dict[str,Any]) -> bool:
    eng = get_engine()
    if eng is not None:
        # Let Postgres generate UUID by default; only send fields present in columns
        keys = ", ".join(data.keys())
        params = ", ".join([f":{k}" for k in data.keys()])
        sql = text(f"insert into {table} ({keys}) values ({params})")
        with eng.begin() as conn:
            conn.execute(sql, data)
        return True
    # CSV fallback
    df = fetch_table(table)
    if "id" not in data or not data.get("id"):
        data["id"] = str(int(dt.datetime.now().timestamp()*1000))
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_csv(csv_path(table), index=False)
    return True

def upsert_row(table:str, data:Dict[str,Any], pk:str="id") -> bool:
    eng = get_engine()
    if eng is not None:
        # Build an UPSERT statement
        cols = list(data.keys())
        set_cols = [c for c in cols if c != pk]
        insert_cols = ", ".join(cols)
        insert_vals = ", ".join([f":{c}" for c in cols])
        set_clause = ", ".join([f"{c}=excluded.{c}" for c in set_cols])
        sql = text(f"""
            insert into {table} ({insert_cols}) values ({insert_vals})
            on conflict ({pk}) do update set {set_clause}
        """)
        with eng.begin() as conn:
            conn.execute(sql, data)
        return True
    # CSV fallback
    df = fetch_table(table)
    if pk not in data or not str(data.get(pk)).strip():
        data[pk] = str(int(dt.datetime.now().timestamp()*1000))
    if df.empty:
        df = pd.DataFrame([data])
    else:
        mask = df[pk].astype(str) == str(data[pk])
        if mask.any():
            for k,v in data.items():
                df.loc[mask, k] = v
        else:
            df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_csv(csv_path(table), index=False)
    return True

def delete_row(table:str, pk_value:Any, pk:str="id"):
    eng = get_engine()
    if eng is not None:
        sql = text(f"delete from {table} where {pk}=:pk")
        with eng.begin() as conn:
            conn.execute(sql, {"pk": pk_value})
        return
    # CSV fallback
    df = fetch_table(table)
    if df.empty: 
        return
    df = df[df[pk].astype(str) != str(pk_value)]
    df.to_csv(csv_path(table), index=False)

# ---------- Domain helpers ----------
def generate_slots(block_minutes:int, start="09:00", end="18:30") -> List[str]:
    s_h, s_m = map(int, start.split(":"))
    e_h, e_m = map(int, end.split(":"))
    cur = dt.datetime.combine(dt.date.today(), dt.time(s_h, s_m))
    end_dt = dt.datetime.combine(dt.date.today(), dt.time(e_h, e_m))
    slots = []
    while cur <= end_dt:
        slots.append(cur.strftime("%H:%M"))
        cur += dt.timedelta(minutes=block_minutes)
    return slots

def overlaps(a_start:str, a_end:str, b_start:str, b_end:str) -> bool:
    return not (a_end <= b_start or b_end <= a_start)

def title_bar():
    st.markdown(f"### {APP_TITLE}")
    st.caption("MVP gratuito con Streamlit + Neon (Postgres serverless).")

# ---------- Pages ----------
def page_pacientes():
    title_bar()
    st.subheader("Pacientes")
    df = fetch_table("patients")
    with st.expander("➕ Agregar / Editar paciente"):
        cols = st.columns(3)
        name = cols[0].text_input("Nombre completo")
        rut = cols[1].text_input("RUT (opcional)")
        bdate = cols[2].date_input("Fecha de nacimiento", value=None, min_value=dt.date(1900,1,1))
        cols2 = st.columns(3)
        phone = cols2[0].text_input("Teléfono")
        email = cols2[1].text_input("Email")
        btn = cols2[2].button("Guardar", use_container_width=True)
        if btn:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                upsert_row("patients", {
                    # id: lo genera Postgres si no se envía
                    "full_name": name.strip(),
                    "rut": rut.strip() or None,
                    "birth_date": str(bdate) if bdate else None,
                    "phone": phone.strip() or None,
                    "email": email.strip() or None,
                    "created_at": dt.datetime.utcnow().isoformat()
                })
                st.success("Paciente guardado.")
                st.rerun()

    st.text_input("Buscar por nombre", key="patient_search")
    if not df.empty:
        mask = df["full_name"].str.contains(st.session_state.get("patient_search",""), case=False, na=False)
        st.dataframe(df[mask].sort_values("full_name"))
    else:
        st.info("No hay pacientes registrados aún.")

def page_config():
    title_bar()
    st.subheader("Configuración (Profesionales & Servicios)")

    # Professionals
    st.markdown("#### Profesionales")
    pro_df = fetch_table("professionals")
    with st.expander("➕ Agregar profesional", expanded=False):
        c = st.columns(3)
        pname = c[0].text_input("Nombre")
        spec = c[1].text_input("Especialidad (TO, Fonoaudiología, Psicología, etc.)")
        if c[2].button("Guardar profesional", use_container_width=True):
            if pname.strip():
                upsert_row("professionals", {
                    "full_name": pname.strip(),
                    "specialty": spec.strip() or None,
                    "created_at": dt.datetime.utcnow().isoformat()
                })
                st.success("Profesional guardado.")
                st.rerun()
            else:
                st.error("El nombre es obligatorio.")

    if not pro_df.empty:
        st.dataframe(pro_df[["full_name","specialty","id"]].sort_values("full_name"))
    else:
        st.info("Agrega tus profesionales.")

    st.markdown("---")
    st.markdown("#### Servicios")
    srv_df = fetch_table("services")
    with st.expander("➕ Agregar servicio", expanded=False):
        c = st.columns(4)
        sname = c[0].text_input("Nombre servicio (p.ej. 'Terapia 30min')")
        dur = c[1].number_input("Duración (min)", min_value=15, max_value=240, step=15, value=DEFAULT_BLOCK_MIN)
        price = c[2].number_input("Precio", min_value=0, step=1000, value=30000)
        if c[3].button("Guardar servicio", use_container_width=True):
            if sname.strip():
                upsert_row("services", {
                    "name": sname.strip(),
                    "duration_minutes": int(dur),
                    "price": float(price),
                    "created_at": dt.datetime.utcnow().isoformat()
                })
                st.success("Servicio guardado.")
                st.rerun()
            else:
                st.error("El nombre del servicio es obligatorio.")

    if not srv_df.empty:
        st.dataframe(srv_df[["name","duration_minutes","price","id"]].sort_values("name"))
    else:
        st.info("Agrega tus servicios.")

def page_agenda():
    title_bar()
    st.subheader("Agenda (por día)")
    block = int(st.sidebar.number_input("Tamaño de bloque (min)", min_value=15, max_value=120, value=DEFAULT_BLOCK_MIN, step=15))
    jornada_cols = st.sidebar.columns(2)
    start_day = jornada_cols[0].text_input("Inicio día", value="09:00")
    end_day = jornada_cols[1].text_input("Fin día", value="18:30")

    day = st.date_input("Fecha", value=dt.date.today())
    pros = fetch_table("professionals")
    pats = fetch_table("patients")
    srvs = fetch_table("services")
    apps = fetch_table("appointments")

    with st.expander("➕ Agendar nueva cita"):
        c = st.columns(3)
        psel = c[0].selectbox("Paciente", options=["—"] + (pats["full_name"].tolist() if not pats.empty else []))
        prosel = c[1].selectbox("Profesional", options=["—"] + (pros["full_name"].tolist() if not pros.empty else []))
        ssel = c[2].selectbox("Servicio", options=["—"] + (srvs["name"].tolist() if not srvs.empty else []))

        slots = generate_slots(block, start_day, end_day)
        c2 = st.columns(3)
        slot = c2[0].selectbox("Hora inicio", options=slots if slots else ["09:00"])
        dur = c2[1].number_input("Duración (min)", min_value=block, step=block, value=block)
        notes = c2[2].text_input("Notas")
        if st.button("Crear cita", use_container_width=True):
            if "—" in (psel, prosel, ssel):
                st.error("Completa paciente, profesional y servicio.")
            else:
                # Resolve ids
                pid = pats[pats["full_name"] == psel]["id"].iloc[0]
                prid = pros[pros["full_name"] == prosel]["id"].iloc[0]
                sr = srvs[srvs["name"] == ssel].iloc[0]
                price = float(sr.get("price", 0))
                start_t = slot + ":00"
                hh, mm = map(int, slot.split(":"))
                end_dt = dt.datetime.combine(day, dt.time(hh, mm)) + dt.timedelta(minutes=int(dur))
                end_t = end_dt.strftime("%H:%M:%S")

                # Overlap check for same professional/day
                same_day = apps[(apps.get("professional_id","").astype(str)==str(prid)) & (apps.get("date","")==str(day))]
                conflict = False
                for _, row in same_day.iterrows():
                    s2 = str(row.get("start_time",""))
                    e2 = str(row.get("end_time",""))
                    if not s2 or not e2:
                        continue
                    if overlaps(start_t, end_t, s2, e2):
                        conflict = True
                        break
                if conflict:
                    st.error("Conflicto de horario con otra cita del mismo profesional.")
                else:
                    insert_row("appointments", {
                        "patient_id": pid,
                        "professional_id": prid,
                        "service_id": sr["id"],
                        "date": str(day),
                        "start_time": start_t,
                        "end_time": end_t,
                        "status": "programada",
                        "notes": notes or None,
                        "price": price,
                        "created_at": dt.datetime.utcnow().isoformat()
                    })
                    st.success("Cita creada.")
                    st.rerun()

    st.markdown("#### Citas del día")
    day_str = str(day)
    day_df = apps[apps.get("date","")==day_str].copy()
    if not day_df.empty:
        if not pats.empty: day_df = day_df.merge(pats[["id","full_name"]].rename(columns={"id":"patient_id","full_name":"Paciente"}), on="patient_id", how="left")
        if not pros.empty: day_df = day_df.merge(pros[["id","full_name"]].rename(columns={"id":"professional_id","full_name":"Profesional"}), on="professional_id", how="left")
        if not srvs.empty: day_df = day_df.merge(srvs[["id","name"]].rename(columns={"id":"service_id","name":"Servicio"}), on="service_id", how="left")
        show = day_df[["start_time","end_time","Paciente","Profesional","Servicio","status","price","notes","id"]].sort_values("start_time")
        st.dataframe(show, use_container_width=True)
    else:
        st.info("No hay citas para esta fecha.")

def page_citas():
    title_bar()
    st.subheader("Listado de Citas")
    df = fetch_table("appointments")
    pats = fetch_table("patients")[["id","full_name"]].rename(columns={"id":"patient_id","full_name":"Paciente"})
    pros = fetch_table("professionals")[["id","full_name"]].rename(columns={"id":"professional_id","full_name":"Profesional"})
    srvs = fetch_table("services")[["id","name"]].rename(columns={"id":"service_id","name":"Servicio"})
    if df.empty:
        st.info("No hay citas registradas.")
        return
    c = st.columns(3)
    d1 = c[0].date_input("Desde", value=dt.date.today() - dt.timedelta(days=7))
    d2 = c[1].date_input("Hasta", value=dt.date.today() + dt.timedelta(days=7))
    status = c[2].selectbox("Estado", options=["(Todos)","programada","atendida","ausente","cancelada"])
    df = df[(df["date"]>=str(d1)) & (df["date"]<=str(d2))]
    if status != "(Todos)":
        df = df[df["status"]==status]

    df = df.merge(pats, on="patient_id", how="left").merge(pros, on="professional_id", how="left").merge(srvs, on="service_id", how="left")
    df = df.sort_values(["date","start_time"])
    st.dataframe(df[["date","start_time","end_time","Paciente","Profesional","Servicio","status","price","notes","id"]], use_container_width=True)

    st.markdown("##### Editar estado de una cita")
    ids = df["id"].astype(str).tolist()
    if ids:
        cid = st.selectbox("ID cita", options=ids)
        new_status = st.selectbox("Nuevo estado", options=["programada","atendida","ausente","cancelada"])
        if st.button("Actualizar estado"):
            upsert_row("appointments", {"id": cid, "status": new_status})
            st.success("Estado actualizado.")
            st.rerun()

def page_reportes():
    title_bar()
    st.subheader("Reportes & KPIs")
    df = fetch_table("appointments")
    pros = fetch_table("professionals")[["id","full_name"]].rename(columns={"id":"professional_id","full_name":"Profesional"})
    if df.empty:
        st.info("Aún no hay datos de citas para reportar.")
        return
    c = st.columns(3)
    d1 = c[0].date_input("Desde", value=dt.date.today().replace(day=1))
    d2 = c[1].date_input("Hasta", value=dt.date.today())
    pro = c[2].text_input("Filtrar por profesional (texto)")

    scope = df[(df["date"]>=str(d1)) & (df["date"]<=str(d2))].copy()
    if pro.strip():
        scope = scope.merge(pros, on="professional_id", how="left")
        scope = scope[scope["Profesional"].str.contains(pro, case=False, na=False)]

    if scope.empty:
        st.warning("Sin datos en el rango seleccionado.")
        return

    total_citas = len(scope)
    atendidas = (scope["status"]=="atendida").sum()
    canceladas = (scope["status"]=="cancelada").sum()
    ausentes = (scope["status"]=="ausente").sum()
    ingresos = float(scope.get("price", 0).fillna(0).sum())

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Citas", f"{total_citas}")
    kpi_cols[1].metric("Atendidas", f"{atendidas}")
    kpi_cols[2].metric("Canceladas", f"{canceladas}")
    kpi_cols[3].metric("Ausentes", f"{ausentes}")
    kpi_cols[4].metric("Ingresos aprox.", f"${ingresos:,.0f}")

    scope["Fecha"] = pd.to_datetime(scope["date"])
    by_day = scope.groupby("Fecha").size().reset_index(name="Citas")
    chart = alt.Chart(by_day).mark_line(point=True).encode(
        x="Fecha:T",
        y="Citas:Q",
        tooltip=["Fecha:T","Citas:Q"]
    )
    st.altair_chart(chart, use_container_width=True)

    block_minutes = int(st.secrets.get("block_minutes", 30))
    start_day = st.secrets.get("workday_start", "09:00")
    end_day = st.secrets.get("workday_end", "18:30")
    s_h, s_m = map(int, start_day.split(":"))
    e_h, e_m = map(int, end_day.split(":"))
    jornada_min = (e_h*60+e_m) - (s_h*60+s_m) + block_minutes
    slots_por_dia = max(1, jornada_min // block_minutes)

    pros_in_scope = scope["professional_id"].nunique()
    dias_distintos = scope["date"].nunique()
    total_slots_disp = pros_in_scope * dias_distintos * slots_por_dia
    ocup = (len(scope) / total_slots_disp)*100 if total_slots_disp>0 else 0
    st.caption(f"Ocupación aprox.: {ocup:0.1f}% (slots usados {len(scope)} de {total_slots_disp} disponibles)")

    scope = scope.merge(pros, on="professional_id", how="left")
    top_pro = scope.groupby("Profesional").size().reset_index(name="Citas").sort_values("Citas", ascending=False)
    bar = alt.Chart(top_pro).mark_bar().encode(
        x="Citas:Q",
        y=alt.Y("Profesional:N", sort='-x'),
        tooltip=["Profesional:N","Citas:Q"]
    )
    st.altair_chart(bar, use_container_width=True)

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🗓️")
    require_auth()

    pages = {
        "Agenda": page_agenda,
        "Pacientes": page_pacientes,
        "Citas": page_citas,
        "Reportes": page_reportes,
        "Configuración": page_config,
    }
    choice = st.sidebar.radio("Navegación", list(pages.keys()))
    pages[choice]()

if __name__ == "__main__":
    main()
