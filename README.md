# CIAN — Agenda de Pacientes (MVP con Streamlit + Neon/Postgres)

**100% web** usando **Neon (Postgres serverless, plan gratuito)** + **GitHub** + **Streamlit Cloud**. Sin Supabase.

- Agenda por bloques, pacientes/profesionales/servicios, reporte KPIs.
- Autenticación simple mediante `app_password` (Streamlit Secrets).
- BD: Neon (Postgres). Puedes usar cualquier Postgres que exponga URL SSL.

---

## 🚀 Despliegue en la nube (sin local)
### 1) Crea BD gratuita en Neon
1. Ve a https://neon.tech → *Sign up* (Free Tier).
2. Crea un **Project** y una **Branch** (por defecto `main`).
3. Copia el **Connection string** en formato Python, por ejemplo:
   `postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require`
4. En el panel, abre **SQL Editor** y pega **`neon_schema.sql`** → **Run**.
5. (Opcional) Ejecuta **`seed.sql`** para datos de ejemplo.

### 2) Sube el código a GitHub
1. Crea repo público `cian-agenda-neon`.
2. Sube **todos** los archivos de este proyecto a la **raíz** del repo:
```
streamlit_app.py
requirements.txt
README.md
neon_schema.sql
seed.sql
.streamlit/
data/
```

### 3) Despliega en Streamlit Cloud
1. https://streamlit.io/cloud → **Deploy an app**.
2. Selecciona el repo y `streamlit_app.py` como **Main file**.
3. En **Advanced settings → Secrets** pega (ajusta con tus datos):
```toml
app_password = "TuClaveSuperSegura123"
block_minutes = 30
workday_start = "09:00"
workday_end   = "18:30"

[db]
url = "postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```
4. **Deploy** y entra con `app_password`.

---

## 📑 Esquema de BD (Postgres)
Tablas: `patients`, `professionals`, `services`, `appointments` (UUID por defecto), vista `v_appointments_full`.
Ejecuta `neon_schema.sql` en el SQL Editor de Neon antes de usar la app.

---

## 🧰 Uso
1. Configura profesionales y servicios.
2. Crea pacientes.
3. Agenda citas (evita choques por profesional).
4. Cambia estados en **Citas**.
5. Revisa KPIs en **Reportes**.

---

## 🔐 Seguridad
- Clave simple (`app_password`) en Secrets.
- Mantén privada la URL del DB en Secrets.
- Para producción, agrega RLS/políticas si las implementas en tu propio backend y vistas limitadas.

---

## 🐞 Problemas frecuentes
- **Repo no existe**: repo público o dar permisos a Streamlit; `streamlit_app.py` en la raíz.
- **Módulos**: `requirements.txt` presente.
- **DB**: revisa que `[db].url` tenga `sslmode=require` y credenciales correctas.
- **Sin datos**: ejecuta `seed.sql` o crea registros desde la app.
