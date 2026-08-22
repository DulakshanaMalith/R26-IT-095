
// ACADEMIC EVENT AUTO-SCHEDULER — Frontend Logic

document.addEventListener("DOMContentLoaded", function () {

    var modal    = document.getElementById("academicSchedulerModal");
    var openBtn  = document.getElementById("btnOpenAcademicScheduler");
    var closeBtn = document.getElementById("closeAcademicModal");
    if (!modal || !openBtn) return;

    openBtn.addEventListener("click", async function () {
        modal.classList.remove("hidden");
        loadExistingEvents();
        await autoFillProjectInfo();
    });
    closeBtn.addEventListener("click", function () { modal.classList.add("hidden"); });
    modal.addEventListener("click", function (e) { if (e.target === modal) modal.classList.add("hidden"); });

    openBtn.addEventListener("mouseenter", function () { openBtn.style.transform = "translateY(-3px)"; openBtn.style.boxShadow = "0 12px 40px rgba(99,102,241,0.7)"; });
    openBtn.addEventListener("mouseleave", function () { openBtn.style.transform = ""; openBtn.style.boxShadow = "0 8px 32px rgba(99,102,241,0.5)"; });

    async function autoFillProjectInfo() {
        try {
            var res  = await fetch("/api/academic/current-project");
            var data = await res.json();
            if (!data.found) return;
            var ta = document.getElementById("groupsInput");
            if (ta && !ta.value.trim()) ta.value = data.group_id + " | " + data.research_topic;
            var banner = document.getElementById("projectAutofillBanner");
            if (banner) { banner.innerHTML = "Auto-filled from uploaded proposal: <strong style='color:#a5b4fc;'>" + data.group_id + "</strong>"; banner.style.display = "block"; }
        } catch (e) {}
    }

    document.getElementById("btnUploadSupervisors").addEventListener("click", async function () {
        var file = document.getElementById("supervisorFile").files[0];
        var st = document.getElementById("supervisorUploadStatus");
        var pv = document.getElementById("supervisorPreview");
        if (!file) { st.innerHTML = "<span style='color:#f87171;'>Select a file first.</span>"; return; }
        st.innerHTML = "<span style='color:#fbbf24;'>Uploading...</span>";
        var fd = new FormData(); fd.append("file", file);
        try {
            var res = await fetch("/api/academic/upload-supervisors", { method: "POST", body: fd });
            var d = await res.json();
            if (d.status === "ok") { st.innerHTML = "<span style='color:#34d399;'>Loaded " + d.supervisors_loaded + " supervisors.</span>"; renderSupervisorPreview(pv); }
            else { st.innerHTML = "<span style='color:#f87171;'>" + d.message + "</span>"; }
        } catch (err) { st.innerHTML = "<span style='color:#f87171;'>" + err.message + "</span>"; }
    });

    async function renderSupervisorPreview(container) {
        try {
            var res = await fetch("/api/academic/supervisors"); var data = await res.json();
            if (!data.length) { container.innerHTML = ""; return; }
            var rows = data.map(function(s) {
                var rc = (s.role||"").toLowerCase().indexOf("prof") >= 0 || (s.role||"").toLowerCase().indexOf("dr") >= 0 ? "#818cf8" : (s.role||"").toLowerCase().indexOf("lect") >= 0 ? "#34d399" : "#fbbf24";
                return "<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'><td style='padding:0.25rem 0.4rem;color:#e2e8f0;'>" + s.name + "</td><td style='padding:0.2rem 0.4rem;'><span style='font-size:0.65rem;background:" + rc + "22;color:" + rc + ";border:1px solid " + rc + "44;padding:0.1rem 0.35rem;border-radius:8px;'>" + (s.role||"Prof") + "</span></td><td style='padding:0.25rem 0.4rem;color:var(--text-muted);'>" + (s.expertise||"").slice(0,40) + "...</td></tr>";
            }).join("");
            container.innerHTML = "<table style='width:100%;border-collapse:collapse;font-size:0.72rem;'><thead><tr style='color:#818cf8;border-bottom:1px solid rgba(255,255,255,0.1);'><th style='text-align:left;padding:0.25rem 0.4rem;'>Name</th><th style='text-align:left;padding:0.25rem 0.4rem;'>Role</th><th style='text-align:left;padding:0.25rem 0.4rem;'>Expertise</th></tr></thead><tbody>" + rows + "</tbody></table>";
        } catch(e) {}
    }

    document.getElementById("btnUploadHalls").addEventListener("click", async function () {
        var file = document.getElementById("hallFile").files[0];
        var st = document.getElementById("hallUploadStatus");
        var pv = document.getElementById("hallPreview");
        if (!file) { st.innerHTML = "<span style='color:#f87171;'>Select a file first.</span>"; return; }
        st.innerHTML = "<span style='color:#fbbf24;'>Uploading...</span>";
        var fd = new FormData(); fd.append("file", file);
        try {
            var res = await fetch("/api/academic/upload-halls", { method: "POST", body: fd });
            var d = await res.json();
            if (d.status === "ok") { st.innerHTML = "<span style='color:#34d399;'>Loaded " + d.halls_loaded + " halls.</span>"; renderHallPreview(pv); }
            else { st.innerHTML = "<span style='color:#f87171;'>" + d.message + "</span>"; }
        } catch(err) { st.innerHTML = "<span style='color:#f87171;'>" + err.message + "</span>"; }
    });

    async function renderHallPreview(container) {
        try {
            var res = await fetch("/api/academic/halls"); var data = await res.json();
            if (!data.length) { container.innerHTML = ""; return; }
            var rows = data.map(function(h) {
                return "<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'><td style='padding:0.25rem 0.4rem;color:#e2e8f0;'>" + h.hall_name + "</td><td style='padding:0.25rem 0.4rem;color:var(--text-muted);'>" + h.capacity + "</td><td style='padding:0.25rem 0.4rem;color:var(--text-muted);'>" + h.available_times + "</td></tr>";
            }).join("");
            container.innerHTML = "<table style='width:100%;border-collapse:collapse;font-size:0.72rem;'><thead><tr style='color:#34d399;border-bottom:1px solid rgba(255,255,255,0.1);'><th style='text-align:left;padding:0.25rem 0.4rem;'>Hall</th><th style='text-align:left;padding:0.25rem 0.4rem;'>Cap.</th><th style='text-align:left;padding:0.25rem 0.4rem;'>Times</th></tr></thead><tbody>" + rows + "</tbody></table>";
        } catch(e) {}
    }

    document.getElementById("btnAutoSchedule").addEventListener("click", async function () {
        var statusEl  = document.getElementById("autoScheduleStatus");
        var rawGroups = document.getElementById("groupsInput").value.trim();
        var startDate = document.getElementById("projectStartDate").value;
        var propWeek  = parseInt(document.getElementById("proposalWeek").value) || 2;
        var pp1Week   = parseInt(document.getElementById("pp1Week").value) || 8;
        var pp2Week   = parseInt(document.getElementById("pp2Week").value) || 14;
        var duration  = parseInt(document.getElementById("eventDuration").value) || 60;

        if (!rawGroups) { statusEl.innerHTML = "<span style='color:#f87171;'>Enter at least one group.</span>"; return; }
        if (!startDate) { statusEl.innerHTML = "<span style='color:#f87171;'>Select a project start date.</span>"; return; }

        var groups = rawGroups.split("\n").map(function(line) {
            var p = line.split("|");
            return { group_id: (p[0]||"").trim(), topic: (p[1]||"software engineering").trim() };
        }).filter(function(g) { return g.group_id; });

        if (!groups.length) { statusEl.innerHTML = "<span style='color:#f87171;'>Format: GroupID | Research Topic</span>"; return; }

        statusEl.innerHTML = "<span style='color:#fbbf24;'>Running AI Matching...</span>";
        document.getElementById("btnAutoSchedule").disabled = true;
        try {
            var res = await fetch("/api/academic/auto-schedule", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ groups: groups, start_date: startDate, proposal_week: propWeek, pp1_week: pp1Week, pp2_week: pp2Week, duration_minutes: duration })
            });
            var data = await res.json();
            if (data.status === "ok") {
                statusEl.innerHTML = "<span style='color:#34d399;'>Scheduled " + data.events_created + " events for " + groups.length + " group(s)!</span>";
                document.getElementById("vivaDashboard").style.display = "block";
                loadExistingEvents();
            } else { statusEl.innerHTML = "<span style='color:#f87171;'>" + data.message + "</span>"; }
        } catch(err) { statusEl.innerHTML = "<span style='color:#f87171;'>" + err.message + "</span>"; }
        document.getElementById("btnAutoSchedule").disabled = false;
    });

    var exportBtn = document.getElementById("btnExportExcel");
    if (exportBtn) { exportBtn.addEventListener("click", function() { window.open("/api/academic/events/export-excel", "_blank"); }); }

    var allEvents = [];
    async function loadExistingEvents() {
        try {
            var res = await fetch("/api/academic/events"); allEvents = await res.json();
            if (allEvents.length > 0) { document.getElementById("vivaDashboard").style.display = "block"; renderEventCards("all"); }
        } catch(e) {}
    }

    var TYPE_META = {
        "Proposal Presentation": { bg:"rgba(99,102,241,0.15)", border:"rgba(99,102,241,0.4)", accent:"#818cf8", label:"Proposal Presentation" },
        "PP1":  { bg:"rgba(245,158,11,0.12)", border:"rgba(245,158,11,0.35)", accent:"#fbbf24", label:"Progress Presentation 1 (PP1)" },
        "PP2":  { bg:"rgba(16,185,129,0.12)", border:"rgba(16,185,129,0.35)", accent:"#34d399", label:"Progress Presentation 2 (PP2)" }
    };
    var STATUS_COLOR = { Scheduled:"#3b82f6", Completed:"#10b981", Postponed:"#f59e0b" };
    var ROLE_COLOR   = { "Professor / Doctor":"#818cf8", "Lecturer":"#34d399", "Instructor":"#fbbf24" };

    function formatDate(dstr) {
        if (!dstr) return "TBD";
        try { return new Date(dstr).toLocaleDateString("en-GB", { weekday:"short", day:"2-digit", month:"short", year:"numeric" }); }
        catch(e) { return dstr; }
    }

    function renderEventCards(filterType) {
        var container = document.getElementById("vivaEventsList");
        var filtered  = filterType === "all" ? allEvents : allEvents.filter(function(e) { return e.event_type === filterType; });
        if (!filtered.length) { container.innerHTML = "<div style='color:var(--text-muted);font-size:0.85rem;padding:1rem;text-align:center;'>No events scheduled yet.</div>"; return; }
        var grouped = {};
        filtered.forEach(function(ev) { if (!grouped[ev.group_id]) grouped[ev.group_id] = []; grouped[ev.group_id].push(ev); });
        var html = "";
        Object.keys(grouped).forEach(function(gid) {
            var events = grouped[gid];
            var cards = "";
            events.forEach(function(ev) {
                var c  = TYPE_META[ev.event_type] || TYPE_META["PP1"];
                var mp = Math.round((ev.match_score||0)*100);
                var mc = mp>=70?"#34d399":mp>=40?"#fbbf24":"#f87171";
                var sc = STATUS_COLOR[ev.status]||"#94a3b8";
                var panelHtml = "";
                if (ev.panel && ev.panel.length) {
                    panelHtml = "<div style='margin-top:0.6rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.07);'><div style='font-size:0.68rem;color:var(--text-muted);font-weight:700;margin-bottom:0.35rem;letter-spacing:0.04em;'>PANEL MEMBERS</div><div style='display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;'>";
                    ev.panel.forEach(function(pm) {
                        var rc = ROLE_COLOR[pm.role]||"#94a3b8";
                        panelHtml += "<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:0.3rem 0.5rem;'><div style='font-size:0.6rem;color:" + rc + ";font-weight:700;margin-bottom:0.1rem;'>" + pm.role + "</div><div style='font-size:0.73rem;color:#e2e8f0;font-weight:600;'>" + pm.name + "</div></div>";
                    });
                    panelHtml += "</div></div>";
                }
                cards += "<div style='background:" + c.bg + ";border:1px solid " + c.border + ";border-radius:12px;padding:1rem;margin-bottom:0.75rem;'>"
                    + "<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:0.65rem;'>"
                    + "<span style='font-size:0.88rem;font-weight:700;color:" + c.accent + ";'>" + c.label + "</span>"
                    + "<span style='font-size:0.7rem;font-weight:700;background:" + sc + "22;color:" + sc + ";border:1px solid " + sc + "44;padding:0.15rem 0.55rem;border-radius:12px;'>" + ev.status + "</span>"
                    + "</div>"
                    + "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.4rem;font-size:0.75rem;margin-bottom:0.5rem;'>"
                    + "<div style='background:rgba(0,0,0,0.15);border-radius:8px;padding:0.4rem 0.5rem;'><div style='color:var(--text-muted);font-size:0.6rem;font-weight:700;margin-bottom:0.15rem;'>DATE</div><div style='color:#f8fafc;font-weight:700;font-size:0.72rem;'>" + formatDate(ev.scheduled_date) + "</div></div>"
                    + "<div style='background:rgba(0,0,0,0.15);border-radius:8px;padding:0.4rem 0.5rem;'><div style='color:var(--text-muted);font-size:0.6rem;font-weight:700;margin-bottom:0.15rem;'>TIME</div><div style='color:#f8fafc;font-weight:700;font-size:0.72rem;'>" + (ev.scheduled_time||"TBD") + "</div></div>"
                    + "<div style='background:rgba(0,0,0,0.15);border-radius:8px;padding:0.4rem 0.5rem;'><div style='color:var(--text-muted);font-size:0.6rem;font-weight:700;margin-bottom:0.15rem;'>HALL</div><div style='color:#f8fafc;font-weight:700;font-size:0.72rem;'>" + (ev.hall_name||"TBD") + "</div></div>"
                    + "</div>"
                    + "<div style='display:flex;align-items:center;justify-content:space-between;font-size:0.75rem;'>"
                    + "<div>Supervisor: <strong style='color:#c4b5fd;'>" + ev.supervisor_name + "</strong></div>"
                    + "<div style='background:" + mc + "22;color:" + mc + ";border:1px solid " + mc + "44;padding:0.12rem 0.5rem;border-radius:8px;font-weight:700;font-size:0.7rem;'>AI " + mp + "% Match</div>"
                    + "</div>" + panelHtml + "</div>";
            });
            var topic = events[0].group_topic ? " — " + events[0].group_topic.slice(0,60) : "";
            html += "<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:1.1rem;margin-bottom:1.25rem;'><div style='font-size:0.85rem;font-weight:700;color:#f8fafc;margin-bottom:0.9rem;'><i class='fa-solid fa-users' style='color:#818cf8;'></i> " + gid + "<span style='font-size:0.72rem;color:var(--text-muted);font-weight:400;'>" + topic + "</span></div>" + cards + "</div>";
        });
        container.innerHTML = html;
    }

    var filterBar = document.getElementById("eventTypeFilter");
    if (filterBar) {
        filterBar.addEventListener("click", function(e) {
            var btn = e.target.closest(".evt-filter-btn");
            if (!btn) return;
            filterBar.querySelectorAll(".evt-filter-btn").forEach(function(b) { b.classList.remove("active"); });
            btn.classList.add("active");
            renderEventCards(btn.dataset.type);
        });
    }

}); // end DOMContentLoaded
