========================================================================
             WELLCARE CLINIC WEBSITE & AI ASSISTANT
                  Beginner-Friendly Project Guide
========================================================================

1. WHAT IS THIS PROJECT?
------------------------
This is a complete website for a medical clinic called "WellCare".
It has three main features:

  A. A Modern Clinic Website:
     Patients can view clinic working hours (Monday to Friday, 7 AM to 8 PM),
     services (check-ups, vaccines, ongoing care), address, and an animated
     showcase of doctors with photos and ratings.

  B. Online Appointment Booking:
     Patients click "Request appointment" to open a pop-up window (modal).
     They fill in their Name, Phone, Preferred Date, and Reason.
     In the background, the system automatically assigns a Booking ID (like B1021),
     sets the status to "Accepted", and timestamps it, saving it into a file
     called "bookings.csv".

  C. Smart AI Clinic Assistant (Chatbot):
     Patients can chat in real time to ask questions like:
       - "What services do you offer?"
       - "What are your hours?"
       - "Check status of booking B1001"
       - "Cancel booking B1001"
       - "Book an appointment for Jane on 2026-11-20"
     If someone types an emergency (like "chest pain" or "can't breathe"),
     the system instantly warns them to call emergency services (8785415621)
     without delay.


2. HOW TO RUN THE PROJECT (IN 3 SIMPLE STEPS)
---------------------------------------------
Make sure you have Python 3.11+ installed.

Step 1: Open a terminal (PowerShell or Command Prompt) in this project folder:
        cd "D:\New folder"

Step 2: Activate the Python virtual environment:
        .\venv\Scripts\activate

Step 3: Start the web server:
        uvicorn app.main:app --reload

Now open your web browser (Chrome, Edge, etc.) and go to:
  http://localhost:8000/


3. FOLDER STRUCTURE (WHAT EACH FOLDER DOES)
-------------------------------------------
- web/
  This is the FRONTEND (what you see in your browser):
    * index.html  -> The web page layout and text.
    * styles.css  -> The colors, fonts, doctor animation, and modal styling.
    * app.js      -> The logic that handles button clicks, forms, and chat messages.

- app/
  This is the BACKEND (the Python server that does the heavy lifting):
    * main.py     -> The web server (FastAPI) that receives requests from the browser.
    * bookings.py -> Validates dates, prevents duplicates, and saves appointments to CSV.
    * tools.py    -> Special tools that read clinic facts, search bookings, and update CSV.
    * llm.py      -> The AI engine. Talks to OpenAI and has a built-in agent that answers
                     clinic questions and manages bookings even if OpenAI has no credits!
    * safety.py   -> Emergency detector (detects heart attacks, stroke, breathing issues).
    * schemas.py  -> Defines the data format (what fields are required).
    * config.py   -> Stores clinic settings (working hours, address, phone numbers).

- data/
  This is the STORAGE (where data lives):
    * clinic_info.md -> Official facts about the clinic (hours, services, address).
    * bookings.csv   -> The spreadsheet file where all appointments are saved.

- tests/
  Automated tests to verify that everything works correctly without errors.
  You can run them anytime by typing: pytest


4. HOW DATA FLOWS (EASY EXPLANATION)
------------------------------------
1. When you click "Request appointment":
   - A friendly pop-up form appears asking for Name, Phone, Date, and Reason.
   - When you click "Confirm", the browser sends this info to the Python server.
   - The Python server checks: Is the date on a weekday? Is capacity full?
   - If okay, it generates a Booking ID (like B1021) and saves it into bookings.csv!

2. When you chat with the Assistant:
   - You type "What services do you offer?"
   - The Python server looks up data/clinic_info.md using its built-in tools.
   - It sends back a friendly reply listing the clinic services.

3. When you ask about your booking:
   - You type "Check status of booking B1001"
   - The assistant searches bookings.csv, finds Aisha Khan, and replies:
     "Booking B1001 for Aisha Khan on 2026-11-04 is Accepted."


5. HOW TO PUSH TO GIT (GITHUB)
------------------------------
Your git repository is already set up locally.
To upload your latest changes to GitHub:

  git add .
  git commit -m "Update project files"
  git push

========================================================================
