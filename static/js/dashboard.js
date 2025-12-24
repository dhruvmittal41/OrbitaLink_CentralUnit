document.addEventListener("DOMContentLoaded", () => {
    const socket = io();
    const scheduleCache = {};

    /* CONNECTION */
    socket.on("connect", () => {
        document.getElementById("status").textContent = "🟢 CONNECTED";
    });

    socket.on("disconnect", () => {
        document.getElementById("status").textContent = "🔴 DISCONNECTED";
    });

    /* LOGS */
    socket.on("log_update", log => {
        const box = document.getElementById("log-box");
        const line = document.createElement("div");
        line.textContent = `[${log.time}] ${log.level} | ${log.message}`;
        box.appendChild(line);
        box.scrollTop = box.scrollHeight;
    });

    /* FU REGISTRY */
    socket.on("fu_registry_update", fus => {
        const container = document.getElementById("client-container");
        container.innerHTML = "";

        fus.forEach(fu => {
            container.appendChild(renderFU(fu));
        });
    });

    /* SCHEDULES */
    socket.on("fu_schedule_update", payload => {
        Object.assign(scheduleCache, payload);
        Object.keys(payload).forEach(renderSchedule);
    });

    /* RENDERERS */
    function renderFU(fu) {
        const div = document.createElement("div");
        div.className = "card";

        div.innerHTML = `
      <h3>📡 ${fu.fu_id}</h3>
      <span class="badge ${fu.state}">${fu.state}</span>
      <p>📍 ${fu.location?.latitude ?? "--"}, ${fu.location?.longitude ?? "--"}</p>
      <div id="schedule-${fu.fu_id}"></div>
    `;

        renderSchedule(fu.fu_id);
        return div;
    }

    function renderSchedule(fu_id) {
        const container = document.getElementById(`schedule-${fu_id}`);
        if (!container) return;

        const schedule = scheduleCache[fu_id] || [];
        container.innerHTML = "";

        schedule.forEach(act => {
            const div = document.createElement("div");
            div.className = `schedule-entry ${act.state || "PLANNED"}`;
            div.innerHTML = `
        <span>${act.start_time.split("T")[1]} → ${act.end_time.split("T")[1]}</span>
        <span>${act.satellite}</span>
      `;
            container.appendChild(div);
        });
    }

    /* CONTROLS */
    window.runScheduler = () => {
        fetch("/api/scheduler/run", { method: "POST" });
    };

    window.disconnectAll = () => {
        fetch("/api/control/disconnect_all", { method: "POST" });
    };
});
