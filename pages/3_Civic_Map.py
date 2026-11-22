from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

from database.db import initialize_database, list_incidents
from utils.map_helpers import build_incident_map, incidents_with_coordinates

st.set_page_config(page_title="Civic Map", page_icon="🗺️", layout="wide")
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

st.title("Civic Map")
st.caption("Interactive view of reported civic incidents based on citizen-provided coordinates.")
st.caption("Map data © OpenStreetMap contributors (ODbL).")

incidents = list_incidents()
if not incidents:
    st.info("No civic incidents have been reported yet.")
else:
    mappable_incidents = incidents_with_coordinates(incidents)

    if not mappable_incidents:
        st.info(
            f"{len(incidents)} incident(s) exist, but none have valid latitude and "
            "longitude coordinates. Add coordinates to an incident to show it on the map."
        )
    else:
        incident_labels = {
            incident["incident_id"]: (
                f"{incident['incident_id']} — "
                f"{incident.get('issue_type') or incident.get('title') or 'Civic issue'} "
                f"({incident.get('location') or 'Location not provided'})"
            )
            for incident in mappable_incidents
        }
        incident_ids = list(incident_labels)
        requested_focus = st.session_state.pop("map_focus_incident_id", None)
        default_index = incident_ids.index(requested_focus) if requested_focus in incident_ids else 0
        selected_incident_id = st.selectbox(
            "Select an incident to focus on",
            options=incident_ids,
            index=default_index,
            format_func=lambda incident_id: incident_labels[incident_id],
        )
        selected_incident = next(
            incident
            for incident in mappable_incidents
            if incident["incident_id"] == selected_incident_id
        )
        with st.container(border=True):
            st.subheader(selected_incident.get("title") or "Selected incident")
            st.write(f"Incident ID: {selected_incident_id}")
            st.write(f"Issue type: {selected_incident.get('issue_type') or selected_incident.get('category') or 'Unknown'}")
            st.write(f"Address: {selected_incident.get('location') or 'Unknown'}")
            st.write(f"Coordinates: {selected_incident['latitude']:.6f}, {selected_incident['longitude']:.6f}")
            st.write(
                f"Priority: {selected_incident.get('priority_level') or 'Low'} "
                f"({selected_incident.get('priority_score') or 'N/A'})"
            )
            st.write(
                f"Priority source: "
                f"{'Manual override' if selected_incident.get('priority_override') else 'Rule-based suggestion'}"
            )
            st.write(
                f"Priority explanation: "
                f"{selected_incident.get('priority_reason') or 'No explanation recorded'}"
            )
            st.write(f"Report count: {selected_incident.get('report_count') or 0}")
            st.write(f"Status: {selected_incident.get('status') or 'Reported'}")

        civic_map, mapped_count = build_incident_map(
            incidents,
            selected_incident_id=selected_incident_id,
        )
        if mapped_count < len(incidents):
            st.info(
                f"Showing {mapped_count} of {len(incidents)} incidents. "
                "Incidents with missing or invalid coordinates are not mapped."
            )
        st_folium(civic_map, width=1200, height=700, key="civic_incident_map")
