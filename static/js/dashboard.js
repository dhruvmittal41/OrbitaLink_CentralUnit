// static/js/main.js
document.addEventListener("DOMContentLoaded", () => {
    const socket = io({ autoConnect: false });

    fetch("/api/satellites")
        .then(res => res.json())
        .then(() => {
            socket.connect();
        })
        .catch(err => console.error("❌ Failed to load satellites:", err));

    socket.on("connect", () => {
        console.log("✅ Connected to server");
    });

    // ==========================
    // LOG STREAM
    // ==========================
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

    // ==========================
    // FU DASHBOARD
    // ==========================
    socket.on("client_data_update", (data) => {
        const clients = data.clients;
        const container = document.getElementById("client-container");
        if (!container) return;

        const seenFUIds = new Set();

        clients.forEach(fu => {
            seenFUIds.add(fu.fu_id);
            const existingCard = document.getElementById(`card-${fu.fu_id}`);

            const trackingText = fu.satellite
                ? `🛰️ Tracking now: ${fu.satellite}`
                : "🛰️ Tracking now: —";

            if (existingCard) {
                existingCard.querySelector(".temp").textContent =
                    `${fu.sensor_data?.temperature ?? "--"} °C`;
                existingCard.querySelector(".hum").textContent =
                    `${fu.sensor_data?.humidity ?? "--"} %`;
                existingCard.querySelector(".gps-lat").textContent =
                    `${fu.location?.latitude ?? "--"}`;
                existingCard.querySelector(".gps-lon").textContent =
                    `${fu.location?.longitude ?? "--"}`;
                existingCard.querySelector(".az").textContent =
                    `${fu.az ?? "--"}°`;
                existingCard.querySelector(".el").textContent =
                    `${fu.el ?? "--"}°`;
                existingCard.querySelector(".tracking").textContent =
                    trackingText;
                return;
            }

            // Create new card
            const div = document.createElement("div");
            div.className = "card";
            div.id = `card-${fu.fu_id}`;

            div.innerHTML = `
                <h2>📡 Field Unit: ${fu.fu_id}</h2>
                <p>🌡️ Temperature: <span class="temp">${fu.sensor_data?.temperature ?? "--"} °C</span></p>
                <p>💧 Humidity: <span class="hum">${fu.sensor_data?.humidity ?? "--"} %</span></p>
                <p>📍 Lat: <span class="gps-lat">${fu.location?.latitude ?? "--"}</span>,
                   Lon: <span class="gps-lon">${fu.location?.longitude ?? "--"}</span></p>
                <p>🎯 AZ: <span class="az">${fu.az ?? "--"}°</span>,
                   EL: <span class="el">${fu.el ?? "--"}°</span></p>
                <p class="tracking">${trackingText}</p>
            `;

            container.appendChild(div);
        });

        // Remove stale cards
        document.querySelectorAll(".card").forEach(card => {
            const fu_id = card.id.replace("card-", "");
            if (!seenFUIds.has(fu_id)) {
                card.remove();
            }
        });
    });
});
