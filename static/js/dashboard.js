// static/js/main.js

document.addEventListener("DOMContentLoaded", () => {
    const socket = io({ autoConnect: false });

    // In-memory schedule cache (fu_id -> schedule[])
    const scheduleCache = {};

    // --------------------------------------------------
    // CONNECT
    // --------------------------------------------------
    socket.connect();

    socket.on("connect", () => {
        console.log("✅ Connected to server");
    });

    // --------------------------------------------------
    // LOG STREAM
    // --------------------------------------------------
    socket.on("log_update", (log) => {
        const logBox = document.getElementById("log-box");
        if (!logBox) return;

        const div = document.createElement("div");
        div.textContent = `[${log.time}] ${log.level} | ${log.source}: ${log.message}`;

        if (log.level === "ERROR") div.style.color = "red";
        else if (log.level === "WARNING") div.style.color = "orange";
        else if (log.level === "DEBUG") div.style.color = "#999";
        else div.style.color = "#0f0";

        logBox.appendChild(div);
        logBox.scrollTop = logBox.scrollHeight;
    });

    // --------------------------------------------------
    // SCHEDULE UPDATES (REAL-TIME)
    // --------------------------------------------------
    socket.on("fu_schedule_update", (payload) => {
        Object.entries(payload).forEach(([fu_id, schedule]) => {
            scheduleCache[fu_id] = schedule;
            renderSchedule(fu_id);
        });
    });

    // --------------------------------------------------
    // FIELD UNIT DASHBOARD
    // --------------------------------------------------
    socket.on("client_data_update", (data) => {
        const container = document.getElementById("client-container");
        if (!container) return;

        const seen = new Set();

        data.clients.forEach((fu) => {
            seen.add(fu.fu_id);

            const cardId = `card-${fu.fu_id}`;
            let card = document.getElementById(cardId);

            const trackingText = fu.satellite
                ? `🛰️ Tracking: ${fu.satellite}`
                : "🛰️ Tracking: —";

            if (!card) {
                card = createFUCard(fu);
                container.appendChild(card);
            }

            // Update live fields
            card.querySelector(".gps-lat").textContent =
                fu.location?.latitude ?? "--";
            card.querySelector(".gps-lon").textContent =
                fu.location?.longitude ?? "--";
            card.querySelector(".tracking").textContent = trackingText;

            renderSchedule(fu.fu_id);
        });

        // Remove stale cards
        document.querySelectorAll(".card").forEach((card) => {
            const fu_id = card.dataset.fuId;
            if (!seen.has(fu_id)) card.remove();
        });
    });

    // --------------------------------------------------
    // CARD CREATION
    // --------------------------------------------------
    function createFUCard(fu) {
        const div = document.createElement("div");
        div.className = "card";
        div.id = `card-${fu.fu_id}`;
        div.dataset.fuId = fu.fu_id;

        div.innerHTML = `
            <h2>📡 Field Unit ${fu.fu_id}</h2>

            <p>
              📍 Lat: <span class="gps-lat">${fu.location?.latitude ?? "--"}</span>,
              Lon: <span class="gps-lon">${fu.location?.longitude ?? "--"}</span>
            </p>

            <p class="tracking">🛰️ Tracking: —</p>

            <div class="schedule-section">
              <h3>📅 Assigned Schedule</h3>
              <div class="schedule-list" id="schedule-${fu.fu_id}">
                <div class="schedule-empty">No schedule assigned</div>
              </div>
            </div>

            <div class="fu-controls">
              <button onclick="manualPoint('${fu.fu_id}')">🎯 Manual Point</button>
              <button onclick="requestTelemetry('${fu.fu_id}')">📊 Telemetry</button>
              <button onclick="disableFU('${fu.fu_id}')">❌ Disable</button>
            </div>
        `;

        return div;
    }

    // --------------------------------------------------
    // SCHEDULE RENDERING
    // --------------------------------------------------
    function renderSchedule(fu_id) {
        const container = document.getElementById(`schedule-${fu_id}`);
        if (!container) return;

        const schedule = scheduleCache[fu_id];

        container.innerHTML = "";

        if (!schedule || schedule.length === 0) {
            container.innerHTML =
                `<div class="schedule-empty">No schedule assigned</div>`;
            return;
        }

        schedule.forEach((entry) => {
            const div = document.createElement("div");
            div.className = "schedule-entry";

            const start = entry.start_time || entry.start || "--";
            const end = entry.end_time || entry.end || "--";
            const sat = entry.satellite || entry.satellite_name || "—";

            div.innerHTML = `
                <span class="schedule-time">${start} – ${end}</span>
                <span class="schedule-sat">${sat}</span>
            `;

            container.appendChild(div);
        });
    }

    // --------------------------------------------------
    // CONTROL ACTIONS (GLOBAL FUNCTIONS)
    // --------------------------------------------------
    window.manualPoint = function (fu_id) {
        const az = prompt("Enter AZ:");
        const el = prompt("Enter EL:");
        if (az === null || el === null) return;

        socket.emit("fu_command", {
            fu_id,
            command: { type: "manual_point", az, el },
        });
    };

    window.requestTelemetry = function (fu_id) {
        socket.emit("fu_command", {
            fu_id,
            command: { type: "telemetry_request" },
        });
    };

    window.disableFU = function (fu_id) {
        if (!confirm(`Disable ${fu_id}?`)) return;

        socket.emit("fu_command", {
            fu_id,
            command: { type: "disable" },
        });
    };
});
