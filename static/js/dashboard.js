// static/js/main.js
document.addEventListener("DOMContentLoaded", () => {
    const socket = io({ autoConnect: false });
    window.allSatellites = [];

    fetch("/api/satellites")
        .then(res => res.json())
        .then(data => {
            // Populate global satellite list
            window.allSatellites = data.filter(name => typeof name === "string" && name.trim().length > 0).map(name => ({ name }));
            console.log("✅ Satellites loaded:", window.allSatellites.length);
            socket.connect();
        })
        .catch(err => console.error("❌ Failed to load satellites:", err));

    socket.on("connect", () => {
        console.log("✅ Connected to server");
    });

    socket.on("log_update", (message) => {
        const log = document.getElementById("log-box");
        if (log) {
            log.innerHTML += `<div>${message}</div>`;
            log.scrollTop = log.scrollHeight;
        }
    });

    socket.on("client_data_update", (data) => {
        const clients = data.clients;
        const container = document.getElementById("client-container");
        console.log(data)
        if (!container) return;

        const seenFUIds = new Set();

        clients.forEach(fu => {
            seenFUIds.add(fu.fu_id);
            const existingCard = document.getElementById(`card-${fu.fu_id}`);

            if (existingCard) {
                // Update existing values
                existingCard.querySelector(".temp").textContent = `${fu.sensor_data?.temperature ?? "--"} °C`;
                existingCard.querySelector(".hum").textContent = `${fu.sensor_data?.humidity ?? "--"} %`;
                existingCard.querySelector(".gps-lat").textContent = `${fu.location?.latitude ?? "--"}`;
                existingCard.querySelector(".gps-lon").textContent = `${fu.location?.longitude ?? "--"}`;
                existingCard.querySelector(".az").textContent = `${fu.az ?? "--"}°`;
                existingCard.querySelector(".el").textContent = `${fu.el ?? "--"}°`;
                return;
            }

            // Otherwise, create new card
            const div = document.createElement("div");
            div.className = "card";
            div.id = `card-${fu.fu_id}`;

            const selectedSat = fu.satellite || "";

            div.innerHTML = `
        <h2>📡 Field Unit: ${fu.fu_id}</h2>
        <p>🌡️ Temperature: <span class="temp">${fu.sensor_data?.temperature ?? "--"} °C</span></p>
        <p>💧 Humidity: <span class="hum">${fu.sensor_data?.humidity ?? "--"} %</span></p>
        <p>📍 Lat: <span class="gps-lat">${fu.location?.latitude ?? "--"}</span>, Lon: <span class="gps-lon">${fu.location?.longitude ?? "--"}</span></p>
        <p>🎯 AZ: <span class="az">${fu.az ?? "--"}°</span>, EL: <span class="el">${fu.el ?? "--"}°</span></p>
        <select id="${fu.fu_id}-select" class="satellite-select" data-fu="${fu.fu_id}">
          <option value="" disabled ${selectedSat ? "" : "selected"}>Select satellite</option>
        </select>
      `;

            container.appendChild(div);

            const select = document.getElementById(`${fu.fu_id}-select`);
            if (!select) return;

            window.allSatellites.forEach((sat) => {
                const option = document.createElement("option");
                option.value = sat.name;
                option.textContent = sat.name;
                if (sat.name === selectedSat) option.selected = true;
                select.appendChild(option);
            });

            new TomSelect(select, {
                create: false,
                maxOptions: 10000,
                sortField: { field: "text", direction: "asc" },
                onChange: (satName) => {
                    const fu_id = select.dataset.fu;
                    if (!satName || satName === "undefined") return;
                    console.log("🔽 Selection change:", satName);
                    socket.emit("select_satellite", {
                        fu_id,
                        satellite_name: satName
                    });
                }
            });
        });

        // Optionally remove stale cards if needed
        document.querySelectorAll(".card").forEach(card => {
            const fu_id = card.id.replace("card-", "");
            if (!seenFUIds.has(fu_id)) {
                card.remove();
            }
        });
    });
});