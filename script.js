// ════════════════════════════════════════
//  PAGE NAVIGATION
// ════════════════════════════════════════

function showPage(id) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.getElementById(id).classList.add("active");

    // Load data when switching to these pages
    if (id === "dashboard") loadDashboard();
    if (id === "sessions")  loadSessions();
}

// ════════════════════════════════════════
//  MESSAGE HELPER
// ════════════════════════════════════════

function showMsg(id, text, isError = false) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent   = text;
    el.style.display = "block";
    el.style.background = isError ? "#fee2e2" : "#d1fae5";
    el.style.color      = isError ? "#b91c1c" : "#065f46";
    setTimeout(() => el.style.display = "none", 3500);
}

// ════════════════════════════════════════
//  NAVBAR — show/hide links by login state
// ════════════════════════════════════════

function updateNav(loggedIn) {
    document.getElementById("nav-login").style.display     = loggedIn ? "none"   : "";
    document.getElementById("nav-register").style.display  = loggedIn ? "none"   : "";
    document.getElementById("nav-dashboard").style.display = loggedIn ? ""       : "none";
    document.getElementById("nav-sessions").style.display  = loggedIn ? ""       : "none";
    document.getElementById("nav-logout").style.display    = loggedIn ? ""       : "none";
}

// ════════════════════════════════════════
//  AUTH — REGISTER
// ════════════════════════════════════════

// Show/hide mentor-only fields when role changes
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("role").addEventListener("change", function () {
        document.getElementById("mentorFields").style.display =
            this.value === "mentor" ? "block" : "none";
    });
    checkLoginState();
});

async function register() {
    const name     = document.getElementById("name").value.trim();
    const email    = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const role     = document.getElementById("role").value;
    const skillsRaw= document.getElementById("skills")?.value || "";
    const bio      = document.getElementById("bio")?.value || "";

    // Split skills by comma into an array
    const skills = skillsRaw.split(",").map(s => s.trim()).filter(Boolean);

    if (!name || !email || !password) {
        showMsg("registerMsg", "Please fill in all fields.", true);
        return;
    }

    const res  = await fetch("/register", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ name, email, password, role, skills, bio })
    });
    const data = await res.json();

    if (res.ok) {
        showMsg("registerMsg", data.message);
        updateNav(true);
        setTimeout(() => showPage("dashboard"), 1200);
    } else {
        showMsg("registerMsg", data.error, true);
    }
}

// ════════════════════════════════════════
//  AUTH — LOGIN
// ════════════════════════════════════════

async function login() {
    const email    = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    if (!email || !password) {
        showMsg("loginMsg", "Please enter email and password.", true);
        return;
    }

    const res  = await fetch("/login", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (res.ok) {
        showMsg("loginMsg", data.message);
        updateNav(true);
        setTimeout(() => showPage("dashboard"), 1200);
    } else {
        showMsg("loginMsg", data.error, true);
    }
}

// ════════════════════════════════════════
//  AUTH — LOGOUT
// ════════════════════════════════════════

async function logout() {
    await fetch("/logout");
    updateNav(false);
    showPage("home");
}

// ════════════════════════════════════════
//  CHECK LOGIN STATE ON PAGE LOAD
// ════════════════════════════════════════

async function checkLoginState() {
    const res = await fetch("/me");
    if (res.ok) {
        const user = await res.json();
        updateNav(true);
        document.getElementById("welcome").textContent  = `👋 Hello, ${user.name}!`;
        document.getElementById("userRole").textContent =
            user.role === "mentor" ? "🎓 Mentor" : "🌱 Mentee";
    } else {
        updateNav(false);
    }
}

// ════════════════════════════════════════
//  DASHBOARD — load welcome + mentors
// ════════════════════════════════════════

async function loadDashboard() {
    const res  = await fetch("/me");
    const user = await res.json();

    if (!res.ok) {
        document.getElementById("welcome").textContent = "Please log in to see the dashboard.";
        document.getElementById("mentorList").innerHTML = "";
        return;
    }

    document.getElementById("welcome").textContent  = `👋 Hello, ${user.name}!`;
    document.getElementById("userRole").textContent =
        user.role === "mentor" ? "🎓 Mentor" : "🌱 Mentee";

    loadMentors();
}

// ════════════════════════════════════════
//  MENTORS — list & search
// ════════════════════════════════════════

async function loadMentors(q = "") {
    const res     = await fetch(`/mentors?q=${encodeURIComponent(q)}`);
    const mentors = await res.json();
    const list    = document.getElementById("mentorList");

    if (!Array.isArray(mentors) || !mentors.length) {
        list.innerHTML = `<p style="color:#888; margin-top:20px;">No mentors found. Try a different keyword.</p>`;
        return;
    }

    list.innerHTML = mentors.map(m => `
        <div class="card">
            <h4>${m.name}</h4>
            <p style="font-size:13px; color:#888; margin:6px 0;">${m.bio || "No bio yet."}</p>
            <div style="margin:8px 0;">
                ${m.skills.map(s => `<span class="skill-tag">${s}</span>`).join("") || ""}
            </div>
            <p style="font-size:13px; color:#555;">
                ⭐ ${m.rating > 0 ? m.rating : "New"} &nbsp;·&nbsp; ${m.review_count} review${m.review_count !== 1 ? "s" : ""}
            </p>
            <button onclick="openBooking('${m.id}', '${m.name.replace(/'/g, "\\'")}')"
                    style="margin-top:12px; font-size:13px; padding:10px 16px;">
                📅 Book Session
            </button>
        </div>
    `).join("");
}

function searchMentor() {
    const q = document.getElementById("search").value.trim();
    loadMentors(q);
}

// ════════════════════════════════════════
//  BOOKING MODAL
// ════════════════════════════════════════

function openBooking(mentorId, mentorName) {
    document.getElementById("bookingModal")?.remove();

    const overlay = document.createElement("div");
    overlay.id = "bookingModal";
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 1000;
    `;

    overlay.innerHTML = `
        <div style="background:#fff; border-radius:20px; padding:32px 28px;
                    width:340px; text-align:center;
                    box-shadow: 0 16px 48px rgba(0,0,0,0.22);">
            <h3 style="margin-bottom:6px;">Book a Session</h3>
            <p style="color:#4facfe; font-weight:700; margin-bottom:20px;">with ${mentorName}</p>

            <input type="text" id="bTopic" placeholder="Topic (e.g. Python basics)" style="border-radius:12px;">
            <input type="date" id="bDate" style="border-radius:12px;">
            <input type="time" id="bTime" style="border-radius:12px;">

            <div id="bookMsg" style="font-size:14px; padding:8px; min-height:20px;"></div>

            <button onclick="confirmBooking('${mentorId}')">✅ Confirm Booking</button>
            <button class="btn-cancel"
                    onclick="document.getElementById('bookingModal').remove()"
                    style="background:#e5e7eb; color:#333;">
                Cancel
            </button>
        </div>
    `;

    document.body.appendChild(overlay);

    // Close modal if user clicks the dark overlay
    overlay.addEventListener("click", e => {
        if (e.target === overlay) overlay.remove();
    });
}

async function confirmBooking(mentorId) {
    const topic = document.getElementById("bTopic").value.trim();
    const date  = document.getElementById("bDate").value;
    const time  = document.getElementById("bTime").value;
    const msgEl = document.getElementById("bookMsg");

    if (!date || !time) {
        msgEl.textContent = "Please pick a date and time.";
        msgEl.style.color = "#b91c1c";
        return;
    }

    const res  = await fetch("/book", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ mentor_id: mentorId, topic, date, time })
    });
    const data = await res.json();

    msgEl.textContent = data.message || data.error;
    msgEl.style.color = res.ok ? "#065f46" : "#b91c1c";

    if (res.ok) {
        setTimeout(() => {
            document.getElementById("bookingModal")?.remove();
            showMsg("dashMsg", "Session booked! Check 'My Sessions'.");
        }, 1800);
    }
}

// ════════════════════════════════════════
//  MY SESSIONS
// ════════════════════════════════════════

async function loadSessions() {
    const res = await fetch("/my-sessions");

    if (res.status === 401) {
        document.getElementById("sessionList").innerHTML =
            `<p style="color:#888;">Please <a onclick="showPage('login')" style="color:#4facfe; cursor:pointer;">log in</a> to see your sessions.</p>`;
        return;
    }

    const sessions = await res.json();
    const list     = document.getElementById("sessionList");

    if (!sessions.length) {
        list.innerHTML = `<p style="color:#888;">No sessions yet. <a onclick="showPage('dashboard')" style="color:#4facfe; cursor:pointer;">Find a mentor!</a></p>`;
        return;
    }

    list.innerHTML = sessions.map(s => `
        <div class="session-card">
            <div>
                <h4>📚 ${s.topic || "General Session"}</h4>
                <p>With <strong>${s.mentor_name || s.mentee_name}</strong></p>
                <p>🗓 ${s.scheduled_at}</p>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:8px;">
                <span class="badge badge-${s.status}">${s.status}</span>
                ${s.status === "upcoming"
                    ? `<button class="btn-danger"
                               onclick="cancelSession('${s.id}')"
                               style="width:auto; padding:8px 16px; font-size:13px; margin:0;">
                           Cancel
                       </button>`
                    : ""}
            </div>
        </div>
    `).join("");
}

async function cancelSession(sessionId) {
    if (!confirm("Are you sure you want to cancel this session?")) return;

    const res  = await fetch(`/cancel-session/${sessionId}`, { method: "POST" });
    const data = await res.json();

    showMsg("sessionMsg", data.message || data.error, !res.ok);
    if (res.ok) loadSessions();
}
