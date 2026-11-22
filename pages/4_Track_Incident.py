from __future__ import annotations

from pathlib import Path

import streamlit as st

from database.db import get_incident_by_id, initialize_database, list_incidents

st.set_page_config(page_title="Track Incident", page_icon="🔎", layout="wide")
initialize_database()

CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "style.css"
css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

st.sidebar.title("JanSuno AI")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/1_Citizen_Portal.py", label="Citizen Portal")
st.sidebar.page_link("pages/2_Admin_Dashboard.py", label="Admin Dashboard")
st.sidebar.page_link("pages/3_Civic_Map.py", label="Civic Map")
st.sidebar.page_link("pages/4_Track_Incident.py", label="Track Incident")

st.title("Track an Incident")
st.caption("Search for civic incidents using an incident ID and view current status without exposing private citizen details.")

incident_id = st.text_input("Enter incident ID", placeholder="INC-001")
if st.button("Search"):
    if not incident_id:
        st.warning("Please provide an incident ID.")
    else:
        incident = get_incident_by_id(incident_id)
        if incident is None:
            st.error(f"No incident found for ID: {incident_id}")
        else:
            st.success(f"Incident found: {incident_id}")
            st.write(f"- Title: {incident.get('title', 'N/A')}")
            st.write(f"- Category: {incident.get('category', 'N/A')}")
            st.write(f"- Issue type: {incident.get('issue_type', 'N/A')}")
            st.write(f"- Current status: {incident.get('status', 'Reported')}")
            st.write(f"- Report count: {incident.get('report_count', 0)}")
            st.write(f"- Priority level: {incident.get('priority_level', 'Low')}")
            st.write(
                f"- Priority source: "
                f"{'Manual override' if incident.get('priority_override') else 'Rule-based suggestion'}"
            )
            st.write(f"- Priority explanation: {incident.get('priority_reason') or 'No explanation recorded'}")
            st.write(f"- Responsible department: {incident.get('department', 'Civic Administration Office')}")
            st.write(f"- Recommended action: {incident.get('recommended_action', 'Review the issue site promptly.')}")
            st.write(f"- Last updated: {incident.get('updated_at', 'N/A')}")

sample_ids = [item["incident_id"] for item in list_incidents()[:5]]
if sample_ids:
    st.caption(f"Sample IDs: {', '.join(sample_ids)}")
