from __future__ import annotations

from pathlib import Path

import streamlit as st

from database.db import get_duplicate_complaint_candidates, initialize_database
from modules.complaint_service import save_confirmed_complaint
from modules.duplicate_detector import find_possible_duplicate_complaint
from modules.geocoder import GeocodingError, build_address_query, geocode_address
from modules.voice_processor import render_voice_input
from utils.helpers import get_project_root, validate_image

st.set_page_config(page_title="Citizen Portal", page_icon="🧾", layout="wide")
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

st.title("Citizen Complaint Portal")
st.caption("Submit a civic issue, confirm its address, and review possible duplicates before saving.")
st.caption("Address lookup: OpenStreetMap Nominatim. Map and geocoding data © OpenStreetMap contributors (ODbL).")

ALLOWED_CATEGORIES = [
    "Road Damage",
    "Garbage / Sanitation",
    "Water Leakage",
    "Drainage",
    "Electricity / Streetlights",
    "Public Safety",
    "Other",
]

st.session_state.setdefault("pending_complaint", None)
st.session_state.setdefault("pending_duplicate", None)
st.session_state.setdefault("last_complaint_result", None)
form_locked = (
    st.session_state["pending_complaint"] is not None
    or st.session_state["pending_duplicate"] is not None
)

with st.form("complaint_form"):
    citizen_name = st.text_input(
        "Citizen name (optional)",
        key="citizen_name",
        disabled=form_locked,
    )
    title = st.text_input(
        "Complaint title",
        placeholder="Example: Pothole near college gate",
        key="complaint_title",
        disabled=form_locked,
    )
    category = st.selectbox(
        "Civic issue category",
        ALLOWED_CATEGORIES,
        key="complaint_category",
        disabled=form_locked,
    )
    description = st.text_area(
        "Complaint description",
        placeholder="Describe the issue clearly and include any safety risks you notice.",
        height=160,
        key="complaint_description",
        disabled=form_locked,
    )
    if not form_locked:
        st.markdown("#### Optional voice input")
        voice_text = render_voice_input(default_value=description)
    else:
        voice_text = ""

    st.markdown("#### Location")
    address_col, city_col = st.columns(2)
    with address_col:
        address = st.text_input(
            "Address or area name",
            placeholder="Street, landmark, or neighborhood",
            key="complaint_address",
            disabled=form_locked,
        )
        district = st.text_input(
            "District (optional)",
            key="complaint_district",
            disabled=form_locked,
        )
        country = st.text_input(
            "Country (optional)",
            key="complaint_country",
            disabled=form_locked,
        )
    with city_col:
        city = st.text_input(
            "City (optional)",
            key="complaint_city",
            disabled=form_locked,
        )
        state = st.text_input(
            "State / province (optional)",
            key="complaint_state",
            disabled=form_locked,
        )
        st.caption("City, district, state, and country help distinguish similar place names.")

    uploaded_file = st.file_uploader(
        "Upload complaint image (optional)",
        type=["png", "jpg", "jpeg", "webp"],
        disabled=form_locked,
    )
    find_location = st.form_submit_button(
        "Find and confirm address",
        disabled=form_locked,
    )


def save_complaint(complaint: dict, selected_location: dict, duplicate_incident_id: str | None):
    result = save_confirmed_complaint(
        complaint=complaint,
        selected_location=selected_location,
        uploads_dir=get_project_root() / "uploads",
        duplicate_incident_id=duplicate_incident_id,
    )
    st.session_state["last_complaint_result"] = result
    st.session_state["map_focus_incident_id"] = result["incident_id"]
    st.session_state["pending_complaint"] = None
    st.session_state["pending_duplicate"] = None


if find_location:
    errors = []
    if not title.strip():
        errors.append("Complaint title is required.")
    complaint_description = description.strip() or voice_text.strip()
    if not complaint_description:
        errors.append("Complaint description is required.")
    if not address.strip():
        errors.append("Address or area name is required.")

    image_bytes = None
    image_name = ""
    if uploaded_file is not None:
        valid_image, error_message = validate_image(uploaded_file)
        if not valid_image:
            errors.append(error_message)
        else:
            image_bytes = uploaded_file.getvalue()
            image_name = uploaded_file.name

    if errors:
        st.session_state["pending_complaint"] = None
        st.session_state["pending_duplicate"] = None
        st.session_state["last_complaint_result"] = None
        for error in errors:
            st.error(error)
    else:
        address_query = build_address_query(
            address=address,
            city=city,
            district=district,
            state=state,
            country=country,
        )
        complaint = {
            "citizen_name": citizen_name.strip(),
            "title": title.strip(),
            "description": complaint_description,
            "category": category,
            "location": address.strip(),
            "image_bytes": image_bytes,
            "image_name": image_name,
        }
        try:
            with st.spinner("Looking up this address on OpenStreetMap..."):
                matches = geocode_address(address_query)
        except GeocodingError as error:
            st.session_state["pending_complaint"] = None
            st.session_state["last_complaint_result"] = None
            st.error(str(error))
        else:
            st.session_state["pending_duplicate"] = None
            st.session_state["last_complaint_result"] = None
            if not matches:
                st.session_state["pending_complaint"] = None
                st.error(
                    "No matching address was found. Check the spelling and add a city, "
                    "district, state, or country, then submit again."
                )
            else:
                st.session_state["pending_complaint"] = {
                    "complaint": complaint,
                    "matches": matches,
                }

pending = st.session_state.get("pending_complaint")
if pending:
    st.subheader("Confirm the complaint location")
    st.write("The complaint will only be saved after you review the location and duplicate check.")
    st.write(f"Complaint: {pending['complaint']['title']}")
    st.write(f"Address submitted: {pending['complaint']['location']}")
    matches = pending["matches"]

    def format_match(index: int) -> str:
        match = matches[index]
        return (
            f"{match['display_name']} "
            f"({match['latitude']:.6f}, {match['longitude']:.6f})"
        )

    selected_index = st.selectbox(
        "Select the correct matched address",
        options=list(range(len(matches))),
        format_func=format_match,
        key="geocoding_match",
    )
    selected_match = matches[selected_index]
    st.info(
        f"Matched address: {selected_match['display_name']}\n\n"
        f"Coordinates: {selected_match['latitude']:.6f}, "
        f"{selected_match['longitude']:.6f}"
    )

    if st.button("Use this location and check for duplicates", type="primary"):
        complaint = pending["complaint"]
        possible_duplicate = find_possible_duplicate_complaint(
            title=complaint["title"],
            description=complaint["description"],
            category=complaint["category"],
            location=complaint["location"],
            latitude=selected_match["latitude"],
            longitude=selected_match["longitude"],
            existing_complaints=get_duplicate_complaint_candidates(),
        )
        if possible_duplicate:
            st.session_state["pending_duplicate"] = {
                "complaint": complaint,
                "location": selected_match,
                "match": possible_duplicate,
            }
        else:
            save_complaint(complaint, selected_match, None)
            st.rerun()

    if st.button("Cancel address confirmation"):
        st.session_state["pending_complaint"] = None
        st.session_state["pending_duplicate"] = None
        st.rerun()

duplicate_review = st.session_state.get("pending_duplicate")
if duplicate_review:
    match = duplicate_review["match"]
    st.warning(
        "This complaint may describe an existing issue nearby. "
        "Please compare the details; nothing has been merged or saved yet."
    )
    with st.container(border=True):
        st.write(f"**Incident:** {match.get('incident_id', 'Unknown')}")
        st.write(f"**Existing report:** {match.get('incident_title') or match.get('title') or 'Unknown'}")
        st.write(f"**Category:** {match.get('category') or 'Unknown'}")
        st.write(f"**Area:** {match.get('location') or 'Unknown'}")
        st.write(f"**Current priority:** {match.get('priority_level') or 'Unknown'}")
        st.write(f"**Linked complaint count:** {match.get('report_count') or 0}")
        if match.get("distance_meters") is not None:
            st.write(f"**Approximate distance:** {match['distance_meters']} m")
        st.write(
            "**Text match:** "
            f"{match.get('text_similarity', 0) * 100:.0f}% "
            "(title and description similarity; this is only a warning)"
        )

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("Link my complaint to this incident"):
            save_complaint(
                duplicate_review["complaint"],
                duplicate_review["location"],
                match["incident_id"],
            )
            st.rerun()
    with action_cols[1]:
        if st.button("This is different — create a new incident"):
            save_complaint(
                duplicate_review["complaint"],
                duplicate_review["location"],
                None,
            )
            st.rerun()

    if st.button("Cancel duplicate review"):
        st.session_state["pending_duplicate"] = None
        st.rerun()

result = st.session_state.get("last_complaint_result")
if result:
    incident = result["incident"] or {}
    st.success(f"Complaint submitted successfully. Incident ID: {result['incident_id']}")
    st.info(result["group_note"])
    st.subheader("Incident summary")
    st.write(f"- Category: {result['category']}")
    st.write(f"- Severity: {result['severity']}/10")
    st.write(f"- Suggested priority: {result['priority']['priority_level']}")
    st.write(f"- Priority score: {result['priority']['priority_score']}/100")
    st.write(f"- Why: {result['priority']['priority_reason']}")
    st.write(f"- Linked complaints: {incident.get('report_count', 0)}")
    st.write(f"- Department: {incident.get('department', 'Civic Administration Office')}")
    st.write(f"- Action: {incident.get('recommended_action', 'Inspect site promptly.')}")
    st.caption("Priority is a transparent rule-based suggestion, not an official policy determination.")
    if st.button("View incident on Civic Map"):
        st.switch_page("pages/3_Civic_Map.py")
