// Clinic Website AI Assistant Front-end Logic
// Strictly follows rule: textContent used for all text insertion, never innerHTML.

(function () {
  'use strict';

  // DOM Elements
  const navClinicName = document.getElementById('nav-clinic-name');
  const infoHours = document.getElementById('info-hours');
  const infoAddress = document.getElementById('info-address');
  const infoPhone = document.getElementById('info-phone');
  const footerEmergencyNum = document.getElementById('footer-emergency-number');

  const chatCard = document.getElementById('chat-card');
  const messagesArea = document.getElementById('messages-area');
  const chipsContainer = document.getElementById('chips-container');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatSendBtn = document.getElementById('chat-send-btn');

  const navBookBtn = document.getElementById('nav-book-btn');
  const heroBookBtn = document.getElementById('hero-book-btn');

  // Booking Modal & Form Elements
  const bookingModal = document.getElementById('booking-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const mainBookingForm = document.getElementById('main-booking-form');
  const fieldBookingId = document.getElementById('field-booking-id');
  const fieldName = document.getElementById('field-name');
  const fieldPhone = document.getElementById('field-phone');
  const fieldPreferredDate = document.getElementById('field-preferred-date');
  const fieldReason = document.getElementById('field-reason');
  const fieldStatus = document.getElementById('field-status');
  const fieldCreatedAt = document.getElementById('field-created-at');
  const bookingFeedbackMsg = document.getElementById('booking-feedback-msg');
  const bookingAltDatesRow = document.getElementById('booking-alt-dates-row');
  const mainBookingSubmitBtn = document.getElementById('main-booking-submit-btn');

  // In-memory conversation history
  const conversationHistory = [];

  // Configuration state
  let clinicConfig = {
    clinic_name: 'WELL Care',
    hours: 'Monday to Friday, 7 AM to 8 PM',
    address: 'Bangalore',
    phone: '674-252-024',
    emergency_number: '8785415621',
    today: new Date().toISOString().split('T')[0],
  };

  // Helper: scroll chat to newest message
  function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  // Load clinic config
  async function loadConfig() {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        clinicConfig = { ...clinicConfig, ...data };
        updateUIConfig();
      }
    } catch (err) {
      console.warn('Could not load /api/config, using defaults:', err);
    }
  }

  function updateUIConfig() {
    if (navClinicName) navClinicName.textContent = clinicConfig.clinic_name;
    if (infoHours) infoHours.textContent = clinicConfig.hours;
    if (infoAddress) infoAddress.textContent = clinicConfig.address;
    if (infoPhone) infoPhone.textContent = clinicConfig.phone;
    if (footerEmergencyNum) footerEmergencyNum.textContent = clinicConfig.emergency_number;
    document.title = `${clinicConfig.clinic_name} | Family & Primary Care`;
  }

  // Message bubble creation
  function appendMessage(role, text, sourceText = null) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role === 'user' ? 'user-bubble' : 'assistant-bubble'}`;

    const textSpan = document.createElement('span');
    textSpan.textContent = text;
    bubble.appendChild(textSpan);

    if (sourceText) {
      const sourceDiv = document.createElement('div');
      sourceDiv.className = 'message-source';
      sourceDiv.textContent = `Source: ${sourceText}`;
      bubble.appendChild(sourceDiv);
    }

    messagesArea.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  // Animated typing indicator
  let activeTypingIndicator = null;

  function showTypingIndicator() {
    if (activeTypingIndicator) return;
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';

    for (let i = 0; i < 3; i++) {
      const dot = document.createElement('div');
      dot.className = 'typing-dot';
      indicator.appendChild(dot);
    }

    messagesArea.appendChild(indicator);
    activeTypingIndicator = indicator;
    scrollToBottom();

    chatInput.disabled = true;
    chatSendBtn.disabled = true;
  }

  function hideTypingIndicator() {
    if (activeTypingIndicator) {
      activeTypingIndicator.remove();
      activeTypingIndicator = null;
    }
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
    chatInput.focus();
  }

  // Suggestion chips setup
  function showInitialChips() {
    chipsContainer.textContent = ''; // clear

    const chips = [
      { text: 'Opening hours', action: () => sendUserQuestion('Opening hours') },
      { text: 'What services do you offer?', action: () => sendUserQuestion('What services do you offer?') },
      { text: 'Preparing for my visit', action: () => sendUserQuestion('Preparing for my visit') },
      { text: 'Request an appointment', action: () => handleRequestAppointmentClick() },
    ];

    chips.forEach((c) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip-btn';
      btn.textContent = c.text;
      btn.addEventListener('click', () => {
        removeChips();
        c.action();
      });
      chipsContainer.appendChild(btn);
    });
  }

  function removeChips() {
    chipsContainer.textContent = '';
  }

  // Calculate min and max dates
  function getDateLimits() {
    const today = clinicConfig.today ? new Date(clinicConfig.today) : new Date();
    const minDate = today.toISOString().split('T')[0];

    const max = new Date(today);
    max.setDate(max.getDate() + 60);
    const maxDate = max.toISOString().split('T')[0];

    return { minDate, maxDate };
  }

  // Render Appointment Request Card
  function renderAppointmentCard(prefilledReason = null) {
    // Check if an active card already exists
    const existing = messagesArea.querySelector('.appointment-card');
    if (existing) {
      existing.scrollIntoView({ behavior: 'smooth' });
      return existing;
    }

    const { minDate, maxDate } = getDateLimits();

    const card = document.createElement('div');
    card.className = 'appointment-card';

    const title = document.createElement('div');
    title.className = 'appointment-title';
    title.textContent = 'Appointment request';
    card.appendChild(title);

    const form = document.createElement('form');
    form.noValidate = true;

    // Full name field
    const nameField = document.createElement('div');
    nameField.className = 'form-field';
    const nameLabel = document.createElement('label');
    nameLabel.className = 'form-label';
    nameLabel.textContent = 'Full name';
    nameLabel.setAttribute('for', 'booking-name');
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.id = 'booking-name';
    nameInput.className = 'form-input';
    nameInput.placeholder = 'Jane Doe';
    nameInput.required = true;
    nameField.appendChild(nameLabel);
    nameField.appendChild(nameInput);
    form.appendChild(nameField);

    // Side by side row: Phone & Preferred day
    const row = document.createElement('div');
    row.className = 'form-row-side-by-side';
    row.style.marginTop = '8px';

    const phoneField = document.createElement('div');
    phoneField.className = 'form-field';
    const phoneLabel = document.createElement('label');
    phoneLabel.className = 'form-label';
    phoneLabel.textContent = 'Phone';
    phoneLabel.setAttribute('for', 'booking-phone');
    const phoneInput = document.createElement('input');
    phoneInput.type = 'tel';
    phoneInput.id = 'booking-phone';
    phoneInput.className = 'form-input';
    phoneInput.placeholder = '+1-555-0100';
    phoneInput.required = true;
    phoneField.appendChild(phoneLabel);
    phoneField.appendChild(phoneInput);
    row.appendChild(phoneField);

    const dateField = document.createElement('div');
    dateField.className = 'form-field';
    const dateLabel = document.createElement('label');
    dateLabel.className = 'form-label';
    dateLabel.textContent = 'Preferred day';
    dateLabel.setAttribute('for', 'booking-date');
    const dateInput = document.createElement('input');
    dateInput.type = 'date';
    dateInput.id = 'booking-date';
    dateInput.className = 'form-input';
    dateInput.min = minDate;
    dateInput.max = maxDate;
    dateInput.required = true;
    dateField.appendChild(dateLabel);
    dateField.appendChild(dateInput);
    row.appendChild(dateField);

    form.appendChild(row);

    // Hidden or optional reason
    let reasonValue = prefilledReason || '';

    // Error / Notice display area
    const errorMsg = document.createElement('div');
    errorMsg.className = 'form-error-msg';
    form.appendChild(errorMsg);

    // Next available dates container
    const altDatesContainer = document.createElement('div');
    altDatesContainer.className = 'available-chips-row';
    form.appendChild(altDatesContainer);

    // Submit button
    const submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.className = 'btn btn-primary form-submit-btn';
    submitBtn.textContent = 'Send request';
    form.appendChild(submitBtn);

    card.appendChild(form);
    messagesArea.appendChild(card);
    scrollToBottom();

    // Form submission handler
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorMsg.style.display = 'none';
      errorMsg.textContent = '';
      altDatesContainer.textContent = '';

      const nameVal = nameInput.value.trim();
      const phoneVal = phoneInput.value.trim();
      const dateVal = dateInput.value.trim();

      // Client-side validation in plain language
      if (!nameVal || nameVal.length < 2 || nameVal.length > 80) {
        showFormError('Please enter your full name (2 to 80 characters).');
        nameInput.focus();
        return;
      }

      const phonePattern = /^[0-9+\-()\s]{7,20}$/;
      if (!phoneVal || !phonePattern.test(phoneVal)) {
        showFormError('Please enter a valid phone number (at least 7 digits, +, -, or parentheses).');
        phoneInput.focus();
        return;
      }

      if (!dateVal) {
        showFormError('Please select a preferred date.');
        dateInput.focus();
        return;
      }

      const selectedDate = new Date(dateVal + 'T00:00:00');
      const dayOfWeek = selectedDate.getDay(); // 0 is Sunday, 6 is Saturday
      if (dayOfWeek === 0 || dayOfWeek === 6) {
        showFormError('The clinic is closed on weekends. Please choose a weekday (Monday to Friday).');
        dateInput.focus();
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';

      try {
        const payload = {
          name: nameVal,
          phone: phoneVal,
          preferred_date: dateVal,
          reason: reasonValue || undefined,
        };

        const res = await fetch('/api/bookings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (res.status === 201) {
          // Success: replace form card with assistant confirmation bubble
          card.remove();
          appendMessage(
            'assistant',
            `Your request ${data.booking_id} for ${data.preferred_date} is accepted. The front desk will contact you at ${phoneVal} to confirm the time.`
          );
        } else if (res.status === 409) {
          // Conflict (capacity full or duplicate)
          showFormError(data.detail || 'The selected date is unavailable.');
          if (data.next_available_dates && data.next_available_dates.length > 0) {
            altDatesContainer.textContent = '';
            const chipLabel = document.createElement('span');
            chipLabel.className = 'form-label';
            chipLabel.style.width = '100%';
            chipLabel.textContent = 'Next available dates:';
            altDatesContainer.appendChild(chipLabel);

            data.next_available_dates.forEach((d) => {
              const chip = document.createElement('button');
              chip.type = 'button';
              chip.className = 'chip-btn';
              chip.textContent = d;
              chip.addEventListener('click', () => {
                dateInput.value = d;
                errorMsg.style.display = 'none';
                altDatesContainer.textContent = '';
              });
              altDatesContainer.appendChild(chip);
            });
          }
        } else if (res.status === 422) {
          showFormError(data.detail || 'Please check your information and try again.');
        } else {
          showFormError('Could not process appointment request. Please try again or phone the clinic.');
        }
      } catch (err) {
        showFormError('Network error connecting to booking service. Please try again.');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send request';
      }
    });

    function showFormError(msg) {
      errorMsg.textContent = msg;
      errorMsg.style.display = 'block';
      scrollToBottom();
    }

    return card;
  }

  // ==========================================
  // Booking Modal Management (CSV Operations)
  // ==========================================

  function openBookingModal(prefilledReason = '') {
    resetBookingForm();
    if (prefilledReason && fieldReason) {
      fieldReason.value = prefilledReason;
    }
    if (bookingModal) {
      bookingModal.style.display = 'flex';
      bookingModal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      if (fieldName) {
        setTimeout(() => fieldName.focus(), 150);
      }
    }
  }

  function closeBookingModal() {
    if (bookingModal) {
      bookingModal.style.display = 'none';
      bookingModal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
    hideBookingFeedback();
  }

  function handleRequestAppointmentClick() {
    openBookingModal();
  }

  if (navBookBtn) navBookBtn.addEventListener('click', handleRequestAppointmentClick);
  if (heroBookBtn) heroBookBtn.addEventListener('click', handleRequestAppointmentClick);
  if (btnCloseModal) btnCloseModal.addEventListener('click', closeBookingModal);
  if (btnCancelModal) btnCancelModal.addEventListener('click', closeBookingModal);

  if (bookingModal) {
    bookingModal.addEventListener('click', (e) => {
      if (e.target === bookingModal) closeBookingModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && bookingModal && bookingModal.style.display === 'flex') {
      closeBookingModal();
    }
  });

  // Doctor cards book appointment buttons
  function bindDoctorButtons() {
    document.querySelectorAll('.btn-doctor-book').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const card = e.target.closest('.doctor-card');
        const docName = card ? card.querySelector('.doctor-name')?.textContent : '';
        openBookingModal(docName ? `Consultation with ${docName}` : 'Doctor consultation');
      });
    });
  }
  bindDoctorButtons();

  function showBookingFeedback(type, text, altDates = []) {
    if (!bookingFeedbackMsg) return;
    bookingFeedbackMsg.className = `booking-feedback feedback-${type}`;
    bookingFeedbackMsg.textContent = text;
    bookingFeedbackMsg.style.display = 'block';

    if (bookingAltDatesRow) {
      bookingAltDatesRow.textContent = '';
      if (altDates && altDates.length > 0) {
        bookingAltDatesRow.style.display = 'flex';
        const label = document.createElement('span');
        label.className = 'form-label';
        label.style.width = '100%';
        label.textContent = 'Next available dates:';
        bookingAltDatesRow.appendChild(label);

        altDates.forEach((d) => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'chip-btn';
          chip.textContent = d;
          chip.addEventListener('click', () => {
            if (fieldPreferredDate) fieldPreferredDate.value = d;
            bookingFeedbackMsg.style.display = 'none';
            bookingAltDatesRow.style.display = 'none';
          });
          bookingAltDatesRow.appendChild(chip);
        });
      } else {
        bookingAltDatesRow.style.display = 'none';
      }
    }
  }

  function hideBookingFeedback() {
    if (bookingFeedbackMsg) {
      bookingFeedbackMsg.style.display = 'none';
      bookingFeedbackMsg.textContent = '';
    }
    if (bookingAltDatesRow) {
      bookingAltDatesRow.style.display = 'none';
      bookingAltDatesRow.textContent = '';
    }
  }

  function resetBookingForm() {
    if (!mainBookingForm) return;
    mainBookingForm.reset();
    if (fieldBookingId) fieldBookingId.value = '';
    if (fieldStatus) fieldStatus.value = 'Accepted';

    const { minDate, maxDate } = getDateLimits();
    if (fieldPreferredDate) {
      fieldPreferredDate.min = minDate;
      fieldPreferredDate.max = maxDate;
    }

    if (fieldCreatedAt) {
      // Auto-set ISO timestamp in background
      const now = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      fieldCreatedAt.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    }

    if (mainBookingSubmitBtn) mainBookingSubmitBtn.textContent = 'Confirm Appointment';
    hideBookingFeedback();
  }

  // Handle Main Booking Form Submit
  if (mainBookingForm) {
    mainBookingForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideBookingFeedback();

      const bookingIdVal = fieldBookingId ? fieldBookingId.value.trim() : '';
      const nameVal = fieldName ? fieldName.value.trim() : '';
      const phoneVal = fieldPhone ? fieldPhone.value.trim() : '';
      const dateVal = fieldPreferredDate ? fieldPreferredDate.value.trim() : '';
      const reasonVal = fieldReason ? fieldReason.value.trim() : '';
      const statusVal = fieldStatus ? fieldStatus.value.trim() : 'Accepted';
      const createdAtVal = fieldCreatedAt ? fieldCreatedAt.value.trim() : '';

      // Validation
      if (!nameVal || nameVal.length < 2 || nameVal.length > 80) {
        showBookingFeedback('error', 'Please enter a valid patient name (2 to 80 characters).');
        if (fieldName) fieldName.focus();
        return;
      }

      const phonePattern = /^[0-9+\-()\s]{7,20}$/;
      if (!phoneVal || !phonePattern.test(phoneVal)) {
        showBookingFeedback('error', 'Please enter a valid phone number (at least 7 digits, +, -, or parentheses).');
        if (fieldPhone) fieldPhone.focus();
        return;
      }

      if (!dateVal) {
        showBookingFeedback('error', 'Please select a preferred appointment date.');
        if (fieldPreferredDate) fieldPreferredDate.focus();
        return;
      }

      // Weekend check
      const selectedDate = new Date(dateVal + 'T00:00:00');
      const dayOfWeek = selectedDate.getDay();
      if (dayOfWeek === 0 || dayOfWeek === 6) {
        showBookingFeedback('error', 'The clinic is closed on weekends. Please choose a weekday (Monday to Friday).');
        if (fieldPreferredDate) fieldPreferredDate.focus();
        return;
      }

      if (mainBookingSubmitBtn) {
        mainBookingSubmitBtn.disabled = true;
        mainBookingSubmitBtn.textContent = 'Recording in CSV...';
      }

      try {
        const payload = {
          booking_id: bookingIdVal || undefined,
          name: nameVal,
          phone: phoneVal,
          preferred_date: dateVal,
          reason: reasonVal || undefined,
          status: statusVal,
          created_at: createdAtVal || undefined,
        };

        const res = await fetch('/api/bookings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (res.status === 200 || res.status === 201) {
          showBookingFeedback(
            'success',
            `Appointment request ${data.booking_id} for ${data.name} on ${data.preferred_date} has been confirmed and saved to our clinic schedule!`
          );
          setTimeout(() => {
            closeBookingModal();
            resetBookingForm();
          }, 2400);
        } else if (res.status === 409) {
          showBookingFeedback('error', data.detail || 'The selected date/slot is unavailable.', data.next_available_dates);
        } else if (res.status === 422) {
          showBookingFeedback('error', data.detail || 'Please check your information and try again.');
        } else {
          showBookingFeedback('error', 'Could not save appointment to CSV. Please try again.');
        }
      } catch (err) {
        showBookingFeedback('error', 'Network error connecting to booking service. Please try again.');
      } finally {
        if (mainBookingSubmitBtn) {
          mainBookingSubmitBtn.disabled = false;
          mainBookingSubmitBtn.textContent = 'Confirm Appointment';
        }
      }
    });
  }

  // ==========================================
  // Chat Assistant Logic
  // ==========================================

  // Send a user question to /api/chat
  async function sendUserQuestion(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    removeChips();

    // Add user bubble
    appendMessage('user', trimmed);
    conversationHistory.push({ role: 'user', content: trimmed });

    showTypingIndicator();

    try {
      // Send last 10 messages from history
      const recentMessages = conversationHistory.slice(-10);
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: recentMessages }),
      });

      hideTypingIndicator();

      if (res.ok) {
        const data = await res.json();
        appendMessage('assistant', data.reply, data.source);
        conversationHistory.push({ role: 'assistant', content: data.reply });

        // If assistant identified booking intent, render booking card
        if (data.intent === 'booking') {
          renderAppointmentCard(data.booking_reason);
        }
      } else if (res.status === 503) {
        appendMessage(
          'assistant',
          `The assistant is temporarily offline (API key setup required). Please call our clinic at ${clinicConfig.phone} or use the "Request appointment" button above.`
        );
      } else if (res.status === 429) {
        appendMessage(
          'assistant',
          'You are sending messages too quickly. Please wait a moment before asking another question.'
        );
      } else {
        const errorData = await res.json().catch(() => ({}));
        appendMessage(
          'assistant',
          errorData.detail || `I'm having trouble right now. Please phone our clinic at ${clinicConfig.phone}.`
        );
      }
    } catch (err) {
      hideTypingIndicator();
      appendMessage(
        'assistant',
        `Unable to reach the assistant server. Please check your connection or phone our clinic at ${clinicConfig.phone}.`
      );
    }
  }

  // Handle chat form submit
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const val = chatInput.value;
    chatInput.value = '';
    sendUserQuestion(val);
  });

  // Initialization
  async function init() {
    await loadConfig();
    resetBookingForm();

    // Initial greeting
    appendMessage(
      'assistant',
      'Hello! I can answer questions about our clinic and help you request an appointment.'
    );

    // Initial suggestion chips
    showInitialChips();
  }

  init();
})();
