# WellCare: End-to-End Technical Guide

This document explains **exactly how this project functions from the ground up**, covering the user experience, frontend code, backend server, AI/agent logic, and data storage.

---

## 1. High-Level Architecture

The project has three main layers:

```
[ User Browser ]
   │
   ├── 1. Website Page (HTML/CSS) -> Shows clinic info, hours, and doctors
   ├── 2. Booking Modal           -> Opens when clicking "Request appointment"
   └── 3. AI Chatbot Widget       -> Interactive chat for questions & bookings
         │
         ▼  (HTTP REST API calls)
[ FastAPI Backend (Python) ]
   │
   ├── Safety Interceptor        -> Instantly catches medical emergencies
   ├── Booking Engine            -> Enforces capacity, weekdays, and CSV locks
   ├── Agent & Tooling Layer     -> Reads facts & manages bookings
   └── OpenAI / Local Agent      -> Generates intelligent responses
         │
         ▼  (File Read / Write)
[ Data Storage ]
   ├── data/clinic_info.md       -> Clinic facts (hours, address, services)
   └── data/bookings.csv         -> Appointments database (thread-safe CSV)
```

---

## 2. File-by-File Breakdown

### Frontend (`web/`)

#### 1. `web/index.html` (The Webpage Skeleton)
- **Top Navigation**: Clinic logo ("WellCare"), links to sections (`Services`, `Our team`, `Visit info`, `Contact`), and the primary `"Request appointment"` button.
- **Hero Section**:
  - Left column: Headline, summary, action buttons, and a live information row showing **Hours (Monday to Friday, 7 AM to 8 PM)**, **Address (Bangalore)**, and **Phone (674-252-024)**.
  - Right column: The embedded **AI Clinic Assistant Chat Widget**.
- **Services Section**: Three cards detailing primary care services: General check-ups, Vaccinations, and Ongoing care.
- **Doctors Section (`#doctors-section`)**:
  - An animated showcase featuring medical doctors.
  - Contains vector avatars, names, credentials, specialties, gold star ratings (e.g. `★★★★★ 4.9`), and a direct `"Request Appointment"` button on each doctor card.
- **Create Appointment Modal (`#booking-modal`)**:
  - A hidden dialog (`style="display: none;"`) positioned over the entire screen with a semi-transparent blur backdrop.
  - It contains the appointment request form.

#### 2. `web/styles.css` (The Visual Styling & Animations)
- **Theme Variables**: Consistent teal/mint palette (`--accent: #1F7A6B`, `--ink: #12302B`, `--card-white: #FFFFFF`).
- **Doctor Marquee Animation**:
  - Uses CSS keyframes:
    ```css
    @keyframes marquee-scroll-left {
      0% { transform: translateX(0); }
      100% { transform: translateX(-50%); }
    }
    ```
  - The doctor cards are duplicated inside the track. As the track translates from `0%` to `-50%`, it loops continuously to create a seamless infinite scroll to the left.
  - When a user hovers their mouse over any doctor card, `animation-play-state: paused;` stops the scroll so they can comfortably read or click.
- **Modal Dialog Styling**: Uses `@keyframes modalFadeIn` and `@keyframes modalSlideUp` for a smooth, native app-like pop-up animation.

#### 3. `web/app.js` (The Client-Side Controller)
- **Initial Load (`init`)**:
  - Calls `GET /api/config` to fetch clinic metadata and populate the hours, address, and phone numbers.
  - Resets the booking form and sets the minimum and maximum date limits (weekdays up to 60 days in advance).
  - Greets the user in chat and displays initial prompt chips (*"Opening hours"*, *"What services do you offer?"*, *"Preparing for my visit"*, *"Request an appointment"*).
- **Modal Logic**:
  - `openBookingModal()`: Reveals the modal, prevents background scrolling (`document.body.style.overflow = 'hidden'`), auto-fills the hidden timestamp, and focuses the Name input.
  - `closeBookingModal()`: Hides the modal and restores scrolling.
  - Listens to clicks on nav buttons, hero buttons, doctor cards, the close button (`×`), the Cancel button, the dark backdrop, and the `Escape` key.
- **Form Submission**:
  - Gathers the visible fields: `name`, `phone`, `preferred_date`, and `reason`.
  - Automatically includes the background fields: `booking_id` (empty for new bookings), `status` (`"Accepted"`), and `created_at` (current ISO timestamp).
  - Validates formatting client-side before sending `POST /api/bookings`.
  - On success, displays a confirmation message and auto-closes the modal after 2.4 seconds.
- **Zero `innerHTML` Policy**:
  - All text is inserted using `element.textContent` or by creating DOM nodes (`document.createElement`). This completely protects against Cross-Site Scripting (XSS) attacks.

---

### Backend (`app/`)

#### 1. `app/main.py` (The API Server Gateway)
- Built with **FastAPI**.
- Hosts the static files from `web/` at `/`.
- **IP Rate Limiter**: Limits requests to `/api/chat` to a maximum of 20 requests per 60 seconds per IP address to prevent abuse.
- Defines the REST API endpoints:
  - `GET /api/config`: Returns clinic details (hours, address, phone).
  - `POST /api/chat`: Runs safety checks, calls the AI/Agent engine, and returns answers.
  - `GET /api/bookings`: Returns all current appointments from `bookings.csv`.
  - `POST /api/bookings`: Creates or updates an appointment in `bookings.csv`.
  - `PUT /api/bookings/{id}`: Dedicated endpoint to update an existing booking.

#### 2. `app/safety.py` (Emergency Interceptor)
- Runs **before** any AI or tool is called.
- Uses strict regex pattern matching for life-threatening keywords:
  - Chest pain, heart attack, stroke, can't breathe, severe bleeding, unconsciousness, overdose, coughing blood, anaphylaxis.
- If an emergency keyword is detected, it **bypasses the AI entirely** and instantly returns an emergency warning instructing the user to call `8785415621` or go to the nearest emergency room.

#### 3. `app/bookings.py` (The Booking Engine & Business Logic)
- **Validation Rules**:
  - Name: Must be between 2 and 80 characters.
  - Phone: Must be 7–20 characters matching valid telephone formats, containing at least 5 digits.
  - Date: Must be in `YYYY-MM-DD` format, cannot be in the past, cannot be more than 60 days ahead, and **must be a weekday (Monday to Friday)**.
- **Duplicate Prevention**: Rejects any request if an accepted booking for the same phone number on that date already exists.
- **Daily Capacity Management**:
  - Counts bookings on that date with status `Accepted`.
  - If capacity reaches 8 appointments (`DAILY_CAPACITY = 8`), rejects the request with HTTP `409 Conflict` and calculates the next 3 available weekday dates with open slots.
- **Thread Safety (`csv_lock`)**:
  - Uses Python's `threading.Lock()`.
  - If multiple patients submit bookings at the exact same millisecond, the lock queues them one at a time, ensuring ID numbers never collide and the CSV file is never corrupted.
- **CSV Injection Sanitization**:
  - If a user enters `=SUM(...)` or `@HYPERLINK(...)` in their name or reason, the engine prefixes it with a `'` quote so spreadsheet software like Excel does not execute it as a formula.

#### 4. `app/tools.py` (Autonomous Agent Tools)
Provides five modular tools used by the AI assistant:
1. `get_clinic_info(topic)`: Reads [`data/clinic_info.md`](file:///d:/New%20folder/data/clinic_info.md) and extracts facts about services, hours, location, or visit preparation.
2. `check_booking_status(query)`: Searches [`data/bookings.csv`](file:///d:/New%20folder/data/bookings.csv) by Booking ID (e.g. `B1001`), phone number, or patient name.
3. `update_booking_status(booking_id, new_status)`: Updates an existing record's status (e.g. from `Accepted` to `Cancelled`) in [`data/bookings.csv`](file:///d:/New%20folder/data/bookings.csv).
4. `book_appointment_tool(name, phone, preferred_date, reason)`: Directly books an appointment and saves it into [`data/bookings.csv`](file:///d:/New%20folder/data/bookings.csv).
5. `get_available_dates_tool(from_date)`: Calculates upcoming open appointment slots.

#### 5. `app/llm.py` (Dual-Mode Assistant Engine)
- **Mode A (OpenAI with Structured Output)**:
  - If an active OpenAI API key with credit is provided, it calls `gpt-4o-mini` with Pydantic structured output (`LLMStructuredOutput`).
- **Mode B (Autonomous Tool-Calling Agent)**:
  - If the OpenAI API key has no credit (`RateLimitError: 429`), times out, or is offline, the system **automatically switches to the local autonomous agent**.
  - The local agent analyzes the user's intent and executes the appropriate tool:
    - Asking about services -> calls `get_clinic_info("services")`.
    - Asking about hours -> calls `get_clinic_info("hours")`.
    - Checking booking status -> calls `check_booking_status("B1001")`.
    - Cancelling an appointment -> calls `update_booking_status(...)`.
    - Booking an appointment -> calls `book_appointment_tool(...)`.
  - **Result**: The user never gets an error message even if the OpenAI API is down!

---

## 3. Step-by-Step Execution Scenarios

### Scenario 1: A Patient Books via the Website Modal
1. The user clicks **"Request appointment"** on the navbar or hero section.
2. `web/app.js` runs `openBookingModal()`:
   - Displays `#booking-modal`.
   - Fills hidden fields: `field-status` (`Accepted`), `field-created-at` (current timestamp), and `field-booking-id` (`""`).
3. The user enters:
   - Name: `Sarah Connor`
   - Phone: `+1-555-4321`
   - Preferred Date: `2026-11-20` (a Friday)
   - Reason: `General check-up`
4. The user clicks **"Confirm Appointment"**.
5. The browser sends `POST /api/bookings` with JSON payload.
6. `app/main.py` forwards the request to `app/bookings.py`:
   - Validates that `2026-11-20` is a weekday and not in the past.
   - Acquires `csv_lock`.
   - Reads `data/bookings.csv` and finds the highest ID (`B1020`), generating `B1021`.
   - Appends the new row to `data/bookings.csv`.
   - Releases `csv_lock`.
7. Backend returns HTTP `201 Created` with booking confirmation details.
8. `web/app.js` displays a success alert, waits 2.4 seconds, and closes the modal.

---

### Scenario 2: A Patient Asks "What services do you offer?"
1. The user types *"What services do you offer?"* in the chat widget and clicks **Send**.
2. `web/app.js` appends the user bubble and shows the 3-dot typing indicator.
3. The browser sends `POST /api/chat` with message history.
4. `app/main.py` checks IP rate limit (under 20 req/min) -> **Passed**.
5. `app/safety.py` scans for emergency keywords -> **None found**.
6. `app/llm.py` attempts OpenAI:
   - If OpenAI returns credits exhausted (HTTP 429), `run_autonomous_agent()` is invoked.
7. The autonomous agent identifies the `services` intent:
   - Calls `get_clinic_info(topic="services")` from `app/tools.py`.
   - Reads the facts directly from `data/clinic_info.md`.
8. The server responds with:
   ```json
   {
     "reply": "We offer the following primary care services at our clinic:\n• General check-ups: routine visits and health reviews.\n• Vaccinations: seasonal and travel vaccines.\n• Ongoing care: follow-ups for long-term conditions.\n\nWould you like to schedule an appointment for any of these?",
     "intent": "faq",
     "source": "Services",
     "booking_reason": null
   }
   ```
9. `web/app.js` hides the typing indicator and displays the assistant bubble with the source badge `"Source: Services"`.

---

### Scenario 3: A Patient Reports an Emergency
1. The user types: *"I am experiencing severe chest pain and can't breathe"*.
2. The browser sends `POST /api/chat`.
3. `app/safety.py` detects `"chest pain"` and `"can't breathe"`.
4. It **instantly returns an emergency response without calling the LLM**:
   ```json
   {
     "reply": "This sounds like a medical emergency. Please call 8785415621 or your local emergency number immediately, or go to the nearest emergency department.",
     "intent": "emergency",
     "source": "Emergencies",
     "booking_reason": null
   }
   ```
5. Response time is sub-millisecond, preventing any AI hallucination or delay.

---

### Scenario 4: A Patient Inquires About or Cancels a Booking via Chat
1. User types: *"What is the status of my booking B1001?"*
2. `app/llm.py` extracts the booking ID `B1001`.
3. Calls tool `check_booking_status("B1001")`.
4. Tool inspects `data/bookings.csv` and finds:
   - Name: `Aisha Khan`
   - Date: `2026-11-04`
   - Status: `Accepted`
5. Assistant replies:
   *"Booking B1001 for Aisha Khan on 2026-11-04 is currently Accepted."*
6. If the user replies: *"Please cancel booking B1001"*:
   - Agent calls `update_booking_status("B1001", "Cancelled")`.
   - The row in `data/bookings.csv` is updated to `Cancelled`.
   - Assistant replies:
     *"Your booking B1001 has been successfully cancelled in our schedule."*

---

## 4. Key Design Strengths

| Aspect | Implementation | Benefit |
|---|---|---|
| **Speed & Reliability** | Dual-mode agent (OpenAI + Local Tool Fallback) | The chatbot never goes down when API quotas run out. |
| **Data Integrity** | Thread mutex lock (`threading.Lock`) | Guarantees safe CSV operations even under high concurrency. |
| **Security** | Zero `innerHTML` DOM manipulation | Immune to DOM-based Cross-Site Scripting (XSS). |
| **Abuse Protection** | In-memory sliding window IP rate limiter | Prevents bot spam and denial of service. |
| **Accessibility** | ARIA roles, high-contrast indicators, reduced motion | Fully usable across devices, screen sizes, and screen readers. |
| **Spreadsheet Safety** | Prefix quote sanitization for `=, +, -, @` | Eliminates CSV formula injection vulnerabilities. |
