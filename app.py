from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from database.db import (
    get_dashboard_stats,
    get_public_transparency_stats,
    initialize_database,
)

st.set_page_config(page_title="JanSuno AI", page_icon="🏛️", layout="wide")

CSS_PATH = Path(__file__).resolve().parent / "assets" / "style.css"
css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

initialize_database()

st.sidebar.title("JanSuno AI")
st.sidebar.caption("Every Voice. One Action.")
st.sidebar.page_link("app.py", label="Home")
st.sidebar.page_link("pages/1_Citizen_Portal.py", label="Citizen Portal")
st.sidebar.page_link("pages/2_Admin_Dashboard.py", label="Admin Dashboard")
st.sidebar.page_link("pages/3_Civic_Map.py", label="Civic Map")
st.sidebar.page_link("pages/4_Track_Incident.py", label="Track Incident")

stats = get_dashboard_stats()
public_stats = get_public_transparency_stats()

st.markdown(
    """
    <div class="hero-card">
        <h1 style="margin-top:0;">JanSuno AI</h1>
        <p style="font-size:1.1rem; margin:0.6rem 0 1rem 0;">Every Voice. One Action.</p>
        <p style="margin:0; max-width:900px;">
            JanSuno AI turns scattered civic complaints into organized incidents, prioritizes urgent issues,
            and helps local departments act faster with clear recommendations.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1.4, 0.6])
with col1:
    st.markdown("<div class='section-title'>Project introduction</div>", unsafe_allow_html=True)
    st.write(
        "Citizens often report civic problems through different channels, and these complaints can become repetitive "
        "and difficult to prioritize. JanSuno AI converts repeated reports into one organized incident and supports "
        "faster civic action."
    )
    st.markdown("<div class='section-title'>How the platform works</div>", unsafe_allow_html=True)
    st.markdown(
        "1. Citizens report a civic issue with description, image, and location.\n"
        "2. The system analyzes the complaint and checks for duplicate incidents.\n"
        "3. Rule-based priority scoring highlights urgent issues.\n"
        "4. Admins review incidents and track them to resolution."
    )
with col2:
    st.markdown("<div class='section-title'>Key features</div>", unsafe_allow_html=True)
    st.markdown(
        "- Citizen-confirmed duplicate matching\n"
        "- Rule-based severity and priority scoring\n"
        "- Public transparency statistics\n"
        "- Incident dashboard\n"
        "- Civic map visualization"
    )

if st.button("Report a Problem", use_container_width=True):
    st.switch_page("pages/1_Citizen_Portal.py")

st.markdown("<div class='section-title'>Statistics overview</div>", unsafe_allow_html=True)
metric_cols = st.columns(5)
metric_labels = [
    ("Complaints", stats.get("total_complaints", 0)),
    ("Incidents", stats.get("total_incidents", 0)),
    ("High Priority", stats.get("high_priority", 0)),
    ("Resolved", stats.get("resolved", 0)),
    ("Pending", stats.get("pending", 0)),
]
for idx, (label, value) in enumerate(metric_labels):
    with metric_cols[idx]:
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size:0.8rem; color:#4d6a89; text-transform:uppercase;">{label}</div>
                <div style="font-size:2rem; font-weight:700; color:#0d2f5b; margin-top:0.4rem;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<div class='section-title'>Public transparency dashboard</div>", unsafe_allow_html=True)
st.caption(
    "These figures are calculated from complaint records and linked incident statuses. "
    "No citizen names, contact details, or complaint descriptions are shown."
)
transparency_cols = st.columns(5)
resolution_time = public_stats["average_resolution_hours"]
transparency_values = [
    ("Complaints received", public_stats["total_complaints"]),
    ("Resolved complaints", public_stats["resolved_complaints"]),
    ("Pending complaints", public_stats["pending_complaints"]),
    ("In progress", public_stats["in_progress_complaints"]),
    ("Resolution rate", f"{public_stats['resolution_percentage']:.1f}%"),
]
for index, (label, value) in enumerate(transparency_values):
    with transparency_cols[index]:
        st.metric(label, value)

if resolution_time is None:
    st.info("Average resolution time is unavailable until resolved complaints have valid timestamps.")
else:
    st.metric(
        "Average resolution time",
        f"{resolution_time:.1f} hours",
        help=(
            "Calculated only from resolved complaints with a valid complaint creation "
            "time and a recorded resolution time."
        ),
    )

public_category_df = pd.DataFrame(public_stats["category_distribution"])
public_area_df = pd.DataFrame(public_stats["area_distribution"]).head(10)
public_chart_cols = st.columns(2)
with public_chart_cols[0]:
    st.markdown("#### Complaints by category")
    if public_category_df.empty:
        st.info("No complaint category data is available yet.")
    else:
        category_figure = px.bar(
            public_category_df,
            x="category",
            y="count",
            title="Recorded complaints by category",
        )
        st.plotly_chart(category_figure, width="stretch")
with public_chart_cols[1]:
    st.markdown("#### Complaints by area")
    if public_area_df.empty:
        st.info("No complaint area data is available yet.")
    else:
        area_figure = px.bar(
            public_area_df.sort_values("count"),
            x="count",
            y="area",
            orientation="h",
            title="Recorded complaints by area (top 10)",
        )
        st.plotly_chart(area_figure, width="stretch")

st.markdown("<div class='section-title'>Portal navigation</div>", unsafe_allow_html=True)
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button("Citizen Portal", use_container_width=True):
        st.switch_page("pages/1_Citizen_Portal.py")
with nav_cols[1]:
    if st.button("Admin Dashboard", use_container_width=True):
        st.switch_page("pages/2_Admin_Dashboard.py")
with nav_cols[2]:
    if st.button("Civic Map", use_container_width=True):
        st.switch_page("pages/3_Civic_Map.py")

st.caption("Prototype civic coordination system for learning and demonstration. Not an official government service.")
