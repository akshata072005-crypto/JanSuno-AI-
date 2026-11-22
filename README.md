# JanSuno AI

JanSuno AI is a beginner-friendly civic intelligence platform built with Streamlit and SQLite. Complaint matching and priority scoring use local Python logic and do not require a paid API or API key.

## What it does

- Citizens can submit civic complaints with text, image, and location details.
- Address lookup uses OpenStreetMap Nominatim only after form submission; citizens select and confirm a match before the complaint is saved.
- Citizens review possible duplicate matches and explicitly choose whether to link or submit separately.
- Rule-based severity and priority scores include an explanation; admins can override the suggested level.
- Admins can review incidents and update their status.
- Incidents are mapped on an interactive Folium map.
- The Home page provides complaint-level public statistics and aggregate charts without displaying citizen identities or complaint descriptions.

## Project structure

- `app.py` – homepage and navigation
- `pages/1_Citizen_Portal.py` – complaint submission
- `pages/2_Admin_Dashboard.py` – admin review and incident management
- `pages/3_Civic_Map.py` – civic incident map
- `pages/4_Track_Incident.py` – public incident lookup
- `modules/` – AI, duplicate, priority, and action logic
- `database/` – SQLite setup and schema
- `utils/` – helper and location utilities
- `uploads/` – uploaded complaint images

## How to run on Windows

1. Open PowerShell in the project folder.
2. Create a virtual environment:
   `py -m venv .venv`
3. Activate it:
   `.venv\Scripts\Activate.ps1`
4. Install dependencies:
   `python -m pip install -r requirements.txt`
5. Optionally configure a Gemini key for other existing AI modules; complaint submission and priority do not require one.
6. Start the app:
   `streamlit run app.py`
7. Open the local URL shown in the terminal.

## Optional Gemini modules

The project retains optional Gemini helper modules, but the complaint submit, duplicate, and priority workflow uses the citizen-selected category and deterministic local rules. No Gemini request is needed for these features.

## Address lookup and OpenStreetMap

The Citizen Portal sends one Nominatim search request after the citizen submits the complaint form. It combines the typed address with optional city, district, state, and country context. The exact address typed by the citizen is stored in the existing `location` columns. If there are multiple matches, the citizen selects one and confirms its formatted address and coordinates before any complaint or incident is saved. No autocomplete requests are made.

Geocoding responses, including no-result searches, are cached in SQLite in the `geocode_cache` table so repeated queries do not contact Nominatim again. Requests are serialized and spaced at least one second apart, and identify this app with a custom User-Agent. The interface displays OpenStreetMap attribution. Follow the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/); the public service is capacity-limited and intended for moderate, end-user-triggered usage.

The default search endpoint is `https://nominatim.openstreetmap.org/search`. To switch to a Nominatim-compatible provider endpoint without changing code, set `JAN_SUNO_GEOCODER_URL` in `.env` and restart the app. Existing incident and complaint records are preserved; initialization only creates the additional geocoding cache table.

### Test address lookup manually

1. Start the app and open **Citizen Portal**.
2. Enter a complaint and an address such as `Times Square`, with `New York`, `New York`, and `United States` in the city, state, and country fields.
3. Submit the form. Confirm that one or more matches and their coordinates appear, and that no incident is saved yet.
4. Choose the correct match and select **Confirm location and submit complaint**. The incident and complaint should store the typed address and selected coordinates.
5. Select **View incident on Civic Map**. The new incident should be selected, its details should be visible, and the map should zoom to its coordinates.
6. Try an intentionally nonexistent address. The page should show a no-match message and leave the database unchanged; correct the address and submit it again.
7. Submit the same address again to verify that cached results are reused. Address search is submit-triggered only; typing does not make requests.

## Duplicate detection and priority scoring

Duplicate detection compares category, title and description similarity, and distance (within 200 metres when coordinates are available). If coordinates are missing, it only proposes a match when the entered location text matches. A possible match is a warning; the citizen must explicitly link the complaint or submit it as a new incident.

Priority is a transparent rule-based heuristic using category risk points, issue/safety keywords, and linked complaint count. It outputs severity (1–10), score (0–100), level (Critical, High, Medium, Low), and a short reason. Admin overrides change the current level but preserve the original suggestion. This is triage guidance, not a machine-learning assessment or official policy.

## Database changes and data safety

Startup adds priority suggestion/override and resolution timestamp columns to existing incidents, plus the existing geocoding cache table if it is absent. Existing complaint and incident rows are not deleted. Linked complaint counts are derived from complaint rows; legacy incident counters are reconciled to those actual links. Legacy priority fields are recalculated once with the local rules.

The Home transparency section counts actual complaint rows and their linked statuses. Average resolution time is shown only when valid complaint creation and recorded resolution timestamps exist. Older resolved incidents without a recorded resolution timestamp are excluded from that average.

The project currently has no user/account tables or login flow. The Admin Dashboard, including priority overrides, remains at its existing access level; deploy behind authentication before exposing it beyond a trusted local demo.

## Test duplicate, priority, and transparency features

1. Run automated tests with `python -m unittest discover -s tests -v`. Tests use temporary SQLite files and do not add sample records to the project database.
2. In Citizen Portal, submit a complaint matching a nearby existing one in category, title, description, and coordinates. Choose **Use this location and check for duplicates**. Review the warning; explicitly choose **Link my complaint to this incident** or **This is different — create a new incident**. Confirm that linked counts update in Admin Dashboard and Civic Map.
3. Use a test database or a disposable copy of `database/jansuno.db` for live UI testing. In Admin Dashboard, inspect the suggested priority and explanation, set a manual override, then reset it with **Use suggested priority**. The map and tracking page identify whether the displayed priority is manual or rule-based.
4. Open Home and compare complaint totals and charts against the test database. Resolve a test incident from Admin Dashboard to see how the resolution percentage changes. Average resolution time appears only for complaint rows with valid creation timestamps and incidents with a valid resolution timestamp.

## Troubleshooting

- If `streamlit` is not recognized, make sure the virtual environment is active.
- If imports fail, reinstall dependencies with `python -m pip install -r requirements.txt`.
- If SQLite errors appear, back up `database/jansuno.db` before attempting repair; deleting it removes saved incidents and complaints.

## Notes

This is a prototype civic coordination system for a hackathon and is not an official government complaint service.
