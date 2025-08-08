cat > streamlit_app.py <<'PY'
import os, requests, streamlit as st

# Cambia esta URL si tu nodo escucha en otro puerto/host
NODE_URL = os.getenv("NODE_URL", "http://localhost:5000")

st.set_page_config(page_title="547 Wallet", page_icon="🪙")
st.title("547 Wallet (demo web)")

with st.sidebar:
    NODE_URL = st.text_input("URL del nodo", NODE_URL, help="Ej: http://localhost:5000")

tab1, tab2, tab3 = st.tabs(["Balance", "Enviar", "Minar"])

with tab1:
    addr = st.text_input("Dirección")
    if st.button("Consultar balance"):
        try:
            # ⚠️ Ajusta al endpoint real de tu API
            r = requests.get(f"{NODE_URL}/balance", params={"address": addr}, timeout=10)
            r.raise_for_status()
            data = r.json()
            st.success(f"Balance: {data.get('balance', data)}")
        except Exception as e:
            st.error(f"Error: {e}")

with tab2:
    from_pk = st.text_input("Clave privada (hex)", type="password")
    to = st.text_input("Dirección destino")
    amount = st.number_input("Monto", min_value=0.0, step=0.0001, format="%.8f")
    if st.button("Enviar transacción"):
        try:
            # ⚠️ Ajusta ruta/payload a tu API real
            payload = {"from_private_key": from_pk, "to": to, "amount": amount}
            r = requests.post(f"{NODE_URL}/send", json=payload, timeout=15)
            r.raise_for_status()
            st.success(r.json())
        except Exception as e:
            st.error(f"Error: {e}")

with tab3:
    if st.button("Minar 1 bloque"):
        try:
            # ⚠️ Ajusta al endpoint real de minado
            r = requests.post(f"{NODE_URL}/mine", timeout=30)
            r.raise_for_status()
            st.success(r.json())
        except Exception as e:
            st.error(f"Error: {e}")
PY
