"""Streamlit UI: chat + sources panel; each citation opens the full provision text."""

from __future__ import annotations

import hmac
import os

import requests
import streamlit as st

API = os.environ.get("API_URL", "http://127.0.0.1:8000")
PW = os.environ.get("APP_PASSWORD", "")
AUTH = (os.environ.get("APP_USER", "laborlex"), PW) if PW else None
LEVEL = {1: "พระราชบัญญัติ", 2: "พระราชกฤษฎีกา", 3: "กฎกระทรวง", 4: "ประกาศ"}

st.set_page_config(page_title="LaborLex-TH", layout="wide")
st.title("LaborLex-TH · ผู้ช่วยกฎหมายแรงงานไทย")
st.caption("คำตอบอ้างอิงเฉพาะตัวบทในฐานข้อมูล · ไม่ใช่คำปรึกษาทางกฎหมาย")

# The UI holds the API password, so the UI itself must be gated when exposed (tunnel/VM).
if PW and not st.session_state.get("authed"):
    entered = st.text_input("รหัสผ่าน", type="password")
    if entered and hmac.compare_digest(entered, PW):
        st.session_state.authed = True
        st.rerun()
    elif entered:
        st.error("รหัสผ่านไม่ถูกต้อง")
    st.stop()

if "history" not in st.session_state:
    st.session_state.history = []

chat, side = st.columns([3, 2])

with chat:
    for item in st.session_state.history:
        st.chat_message("user").write(item["q"])
        st.chat_message("assistant").markdown(item["md"])
    q = st.chat_input("พิมพ์คำถามกฎหมายแรงงาน…")
    if q:
        st.chat_message("user").write(q)
        with st.spinner("กำลังวิเคราะห์ (ข้อเท็จจริง → ประเด็น → ตัวบท → ปรับบท → สรุป)…"):
            r = requests.post(f"{API}/ask", json={"question": q}, auth=AUTH, timeout=600)
        if r.ok:
            data = r.json()
            st.session_state.history.append({"q": q, "md": data["markdown"],
                                             "citations": data["citations"],
                                             "trace": data["trace"]})
            st.rerun()
        else:
            st.error(f"เกิดข้อผิดพลาด ({r.status_code})")

with side:
    st.subheader("แหล่งที่มา")
    if st.session_state.history:
        last = st.session_state.history[-1]
        for c in last["citations"]:
            if c.get("kind") == "case":
                with st.expander(f"⚖️ {c['label']}"):
                    st.markdown(f"[เปิดคำพิพากษาต้นฉบับ]({c['source_url']})")
                continue
            title = f"📜 {c.get('label') or c['citation_key']} · {LEVEL.get(c['level'], '')}"
            with st.expander(title):
                st.markdown(f"**{c['law_name']}**  \n{c.get('chapter') or ''} "
                            f"{c.get('chapter_title') or ''}")
                full = requests.get(f"{API}/provision/{c['citation_key']}", auth=AUTH, timeout=30)
                if full.ok:
                    for p in full.json()["section"]:
                        mark = "➤ " if p["citation_key"].startswith(
                            c["citation_key"].rsplit(":", 1)[0]) and \
                            p["paragraph_no"] == c["paragraph_no"] else ""
                        st.markdown(f"{mark}วรรค {p['paragraph_no']}: {p['text']}")
                if c.get("amendment_notes"):
                    st.caption("ประวัติการแก้ไข: " + " · ".join(c["amendment_notes"]))
                st.caption(f"มีผล: {c.get('valid_from') or 'ไม่ระบุ'} – {c.get('valid_to') or 'ปัจจุบัน'}")
        with st.expander("ขั้นตอนการคิดของระบบ (trace)"):
            for t in last["trace"]:
                st.write(f"**{t['node']}** · {t['ms']} ms · LLM {t['llm_calls']}")
                if t.get("summary"):
                    st.json(t["summary"], expanded=False)
