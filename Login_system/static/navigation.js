(() => {
    const PUBLIC_PATHS = new Set([
        "/",
        "/login",
        "/register",
        "/verify-otp",
        "/forgot-password",
        "/reset-password",
        "/auth/google/login",
        "/auth/google/callback",
    ]);

    const HOME_BY_ROLE = {
        superadmin: "/superadmin",
        master_admin: "/master_admin",
        admin: "/admin",
        employee: "/employee",
        customer: "/main",
    };

    const TOP_LINKS_BY_ROLE = {
        superadmin: [
            { href: "/superadmin", label: "Superadmin" },
            { href: "/profile", label: "Profile" },
            { href: "/notifications", label: "Notifications" },
            { href: "/logout", label: "Logout" },
        ],
        master_admin: [
            { href: "/master_admin", label: "Dashboard" },
            { href: "/master_admin/admins", label: "Manage Admins" },
            { href: "/master_admin/users", label: "Users" },
            { href: "/master_admin/knowledge", label: "Knowledge" },
            { href: "/master_admin/analytics", label: "Analytics" },
            { href: "/master_admin/audit-logs", label: "Audit Logs" },
            { href: "/master_admin/access-requests", label: "Access Requests" },
            { href: "/master_admin/tickets", label: "Tickets" },
            { href: "/profile", label: "Profile" },
            { href: "/notifications", label: "Notifications" },
            { href: "/logout", label: "Logout" },
        ],
        admin: [
            { href: "/admin", label: "Dashboard" },
            { href: "/admin/users", label: "Users" },
            { href: "/admin/knowledge", label: "Knowledge" },
            { href: "/admin/analytics", label: "Analytics" },
            { href: "/admin/audit-logs", label: "Audit Logs" },
            { href: "/admin/access-requests", label: "Access Requests" },
            { href: "/admin/tickets", label: "Tickets" },
            { href: "/profile", label: "Profile" },
            { href: "/notifications", label: "Notifications" },
            { href: "/logout", label: "Logout" },
        ],
        employee: [
            { href: "/employee", label: "Dashboard" },
            { href: "/employee/customers", label: "Customers" },
            { href: "/employee/tickets", label: "Tickets" },
            { href: "/profile", label: "Profile" },
            { href: "/notifications", label: "Notifications" },
            { href: "/logout", label: "Logout" },
        ],
        customer: [
            { href: "/main", label: "Chat" },
            { href: "/my-tickets", label: "My Tickets" },
            { href: "/select-business", label: "Businesses" },
            { href: "/profile", label: "Profile" },
            { href: "/notifications", label: "Notifications" },
            { href: "/logout", label: "Logout" },
        ],
    };

    const SIDE_LINKS_BY_ROLE = {
        master_admin: [
            { href: "/master_admin", label: "Overview" },
            { href: "/master_admin/admins", label: "Manage Admins" },
            { href: "/master_admin/users", label: "Users" },
            { href: "/master_admin/knowledge", label: "Knowledge Base" },
            { href: "/master_admin/analytics", label: "Analytics" },
            { href: "/master_admin/audit-logs", label: "Audit Logs" },
            { href: "/master_admin/access-requests", label: "Access Requests" },
            { href: "/master_admin/tickets", label: "Support Tickets" },
        ],
        admin: [
            { href: "/admin", label: "Overview" },
            { href: "/admin/users", label: "Users" },
            { href: "/admin/knowledge", label: "Knowledge Base" },
            { href: "/admin/analytics", label: "Analytics" },
            { href: "/admin/audit-logs", label: "Audit Logs" },
            { href: "/admin/access-requests", label: "Access Requests" },
            { href: "/admin/tickets", label: "Support Tickets" },
        ],
        employee: [
            { href: "/employee", label: "Overview" },
            { href: "/employee/customers", label: "Customers" },
            { href: "/employee/tickets", label: "Support Tickets" },
        ],
    };

    function getCookie(name) {
        const v = `; ${document.cookie}`;
        const parts = v.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
    }

    function isActive(path, target) {
        if (path === target) return true;
        if (target !== "/" && path.startsWith(target + "/")) return true;
        return false;
    }

    function removeLegacyNav() {
        document.querySelectorAll(".nav-overlay").forEach((el) => el.remove());
        document.querySelectorAll(".nav-menu").forEach((el) => el.remove());
        document.querySelectorAll("header").forEach((el) => {
            if (el.querySelector(".menu-btn")) el.remove();
        });
    }

    async function resolveRole() {
        const meta = document.querySelector('meta[name="assistify-role"]');
        if (meta && meta.content) return meta.content.trim();

        try {
            const csrf = getCookie("csrf_token");
            const headers = csrf ? { "x-csrf-token": csrf } : {};
            const res = await fetch("/api/my-profile", {
                credentials: "same-origin",
                headers,
            });
            if (!res.ok) return "customer";
            const data = await res.json();
            return (data.role || "customer").trim();
        } catch {
            return "customer";
        }
    }

    function renderTopNav(role, path) {
        const home = HOME_BY_ROLE[role] || "/main";
        const links = TOP_LINKS_BY_ROLE[role] || TOP_LINKS_BY_ROLE.customer;
        const showSideToggle = ["admin", "master_admin", "employee"].includes(role);

        let topNav = document.querySelector(".app-top-nav");
        if (!topNav) {
            topNav = document.createElement("nav");
            topNav.className = "app-top-nav";
            document.body.prepend(topNav);
        }

        topNav.innerHTML = `
            ${showSideToggle ? '<button type="button" class="side-toggle-btn" aria-label="Toggle section menu">Sections</button>' : ""}
            <a class="brand" href="${home}">Assistify</a>
            <div class="links">
                ${links
                    .map(
                        (l) =>
                            `<a class="${isActive(path, l.href) ? "active" : ""}" href="${l.href}">${l.label}</a>`
                    )
                    .join("")}
            </div>
        `;

        return topNav;
    }

    function renderSideNav(role, path) {
        const links = SIDE_LINKS_BY_ROLE[role];
        if (!links || !links.length) return null;

        let side = document.querySelector(".app-side-nav");
        if (!side) {
            side = document.createElement("aside");
            side.className = "app-side-nav";
            document.body.appendChild(side);
        }

        side.innerHTML = links
            .map(
                (l) =>
                    `<a class="${isActive(path, l.href) ? "active" : ""}" href="${l.href}">${l.label}</a>`
            )
            .join("");

        let overlay = document.querySelector(".app-side-overlay");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "app-side-overlay";
            overlay.addEventListener("click", closeSideDrawer);
            document.body.appendChild(overlay);
        }

        return side;
    }

    function closeSideDrawer() {
        document.body.classList.remove("side-drawer-open");
    }

    function wireSideToggle(topNav) {
        const btn = topNav.querySelector(".side-toggle-btn");
        if (!btn) return;
        btn.addEventListener("click", () => {
            document.body.classList.toggle("side-drawer-open");
        });
    }

    async function init() {
        const path = window.location.pathname || "/";
        if (PUBLIC_PATHS.has(path)) return;

        removeLegacyNav();

        const role = await resolveRole();
        const topNav = renderTopNav(role, path);
        const sideNav = renderSideNav(role, path);

        document.body.classList.add("has-app-nav");
        if (sideNav) {
            document.body.classList.add("has-side-nav");
            wireSideToggle(topNav);
        } else {
            document.body.classList.remove("has-side-nav", "side-drawer-open");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
