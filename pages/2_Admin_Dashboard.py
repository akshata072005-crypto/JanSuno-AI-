from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from database.db import (
    get_dashboard_stats,
    initialize_database,
    list_incidents,
    set_manual_priority_override,
    update_incident_status,
)
from modules.priority_engine import PRIORITY_LEVELS

st.set_page_config(page_title="Admin Dashboard", page_icon="📊", layout="wide")
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

st.title("Admin Dashboard")
st.caption("Review civic incidents, linked complaint counts, rule-based priorities, and service status.")

stats = get_dashboard_stats()
incidents = list_incidents()
df = pd.DataFrame(incidents)


def metric_card(label: str, value: str | int) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div style="font-size:0.8rem; color:#4d6a89; text-transform:uppercase;">{label}</div>
            <div style="font-size:2rem; font-weight:700; color:#0d2f5b; margin-top:0.4rem;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


metric_cols = st.columns(5)
metric_values = [
    ("Total complaints", stats.get("total_complaints", 0)),
    ("Total incidents", stats.get("total_incidents", 0)),
    ("Critical incidents", stats.get("critical_priority", 0)),
    ("High-priority incidents", stats.get("high_priority", 0)),
    ("Resolved incidents", stats.get("resolved", 0)),
]
for index, (label, value) in enumerate(metric_values):
    with metric_cols[index]:
        metric_card(label, value)

if df.empty:
    st.info("No incidents have been recorded yet.")
    st.caption("Incident priorities are rule-based suggestions, not official service or safety determinations.")
    st.stop()

priority_df = pd.DataFrame(stats.get("priority_distribution", []))
if not priority_df.empty:
    priority_order = ["Critical", "High", "Medium", "Low"]
    priority_df["priority_level"] = pd.Categorical(
        priority_df["priority_level"],
        categories=priority_order,
        ordered=True,
    )
    priority_df = priority_df.sort_values("priority_level")
    st.subheader("Priority distribution")
    figure = px.bar(
        priority_df,
        x="priority_level",
        y="count",
        color="priority_level",
        category_orders={"priority_level": priority_order},
        title="Incidents by current priority",
    )
    st.plotly_chart(figure, width="stretch")

category_df = pd.DataFrame(stats.get("category_distribution", []))
if not category_df.empty:
    st.subheader("Incident categories")
    figure = px.bar(
        category_df,
        x="category",
        y="count",
        color="category",
        title="Incidents by category",
    )
    st.plotly_chart(figure, width="stretch")

status_options = ["Reported", "Under Review", "Assigned", "In Progress", "Resolved"]
current_priorities = set(df["priority_level"].fillna("Low").astype(str))
priority_options = [level for level in PRIORITY_LEVELS if level in current_priorities]
categories = sorted(df["category"].fillna("Uncategorized").astype(str).unique())

st.subheader("Filter incidents")
filter_cols = st.columns(3)
with filter_cols[0]:
    selected_status = st.multiselect(
        "Status",
        status_options,
        default=status_options,
    )
with filter_cols[1]:
    selected_priorities = st.multiselect(
        "Priority",
        PRIORITY_LEVELS,
        default=priority_options or list(PRIORITY_LEVELS),
    )
with filter_cols[2]:
    selected_categories = st.multiselect(
        "Category",
        categories,
        default=categories,
    )
search_text = st.text_input("Search by incident ID, title, or area")

filtered_df = df.copy()
filtered_df = filtered_df[
    filtered_df["status"].fillna("Reported").isin(selected_status)
    & filtered_df["priority_level"].fillna("Low").isin(selected_priorities)
    & filtered_df["category"].fillna("Uncategorized").isin(selected_categories)
]
if search_text.strip():
    search_columns = ["incident_id", "title", "location"]
    matches_search = pd.Series(False, index=filtered_df.index)
    for column in search_columns:
        matches_search |= filtered_df[column].fillna("").astype(str).str.contains(
            search_text.strip(),
            case=False,
            regex=False,
        )
    filtered_df = filtered_df[matches_search]
filtered_df = filtered_df.sort_values("created_at", ascending=False)

st.subheader("Incident list")
if filtered_df.empty:
    st.info("No incidents match the selected filters.")
else:
    incident_columns = [
        "incident_id",
        "title",
        "category",
        "report_count",
        "suggested_priority_level",
        "priority_level",
        "priority_override",
        "status",
        "department",
        "updated_at",
    ]
    visible_columns = [column for column in incident_columns if column in filtered_df.columns]
    st.dataframe(filtered_df[visible_columns], width="stretch")
    st.caption("Complaint counts are calculated from complaints linked to each incident, not legacy counters.")

    st.subheader("Priority explanation")
    detail_id = st.selectbox(
        "Select an incident to inspect",
        filtered_df["incident_id"].tolist(),
        key="priority_detail_id",
    )
    detail = next(
        incident for incident in incidents if incident["incident_id"] == detail_id
    )
    st.write(f"**Rule-based suggestion:** {detail.get('suggested_priority_level') or 'N/A'}")
    st.write(f"**Suggested score:** {detail.get('suggested_priority_score') or 0}/100")
    st.write(f"**Why:** {detail.get('priority_reason') or 'No explanation has been recorded yet.'}")
    st.write(
        "**Current priority:** "
        f"{detail.get('priority_level') or 'N/A'} "
        f"({'manually overridden' if detail.get('priority_override') else 'automatic suggestion'})"
    )

    st.subheader("Update incident status")
    with st.form("status_update"):
        incident_id = st.selectbox(
            "Incident",
            filtered_df["incident_id"].tolist(),
            key="status_incident_id",
        )
        next_status = st.selectbox("New status", status_options)
        status_submitted = st.form_submit_button("Update status")
    if status_submitted:
        update_incident_status(incident_id, next_status)
        st.success(f"Incident {incident_id} updated to {next_status}.")
        st.rerun()

    st.subheader("Manual priority override")
    st.caption(
        "A manual priority changes the displayed priority but keeps the rule-based "
        "suggestion and its explanation for comparison."
    )
    with st.form("priority_override"):
        override_incident_id = st.selectbox(
            "Incident to override",
            filtered_df["incident_id"].tolist(),
            key="override_incident_id",
        )
        override_incident = next(
            incident
            for incident in incidents
            if incident["incident_id"] == override_incident_id
        )
        current_manual = override_incident.get("manual_priority_level")
        selected_default = current_manual or override_incident.get("suggested_priority_level")
        manual_default_index = (
            PRIORITY_LEVELS.index(selected_default)
            if selected_default in PRIORITY_LEVELS
            else 0
        )
        manual_level = st.selectbox(
            "Set current priority to",
            PRIORITY_LEVELS,
            index=manual_default_index,
        )
        override_cols = st.columns(2)
        with override_cols[0]:
            override_submitted = st.form_submit_button("Save manual override")
        with override_cols[1]:
            clear_override_submitted = st.form_submit_button("Use suggested priority")
    if override_submitted:
        set_manual_priority_override(override_incident_id, manual_level)
        st.success(f"Incident {override_incident_id} now uses the manual {manual_level} priority.")
        st.rerun()
    if clear_override_submitted:
        set_manual_priority_override(override_incident_id, None)
        st.success(f"Incident {override_incident_id} now uses its rule-based suggestion.")
        st.rerun()

st.caption("Priorities are transparent, rule-based triage suggestions; they are not official policy.")
