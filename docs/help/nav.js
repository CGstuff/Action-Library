// Central top navigation for the Action Library docs.
//
// Every page has a hardcoded <nav class="top"> as a no-JS fallback; this script
// replaces it with the list below, so the nav is defined in ONE place. Adding a
// page = add one line here (plus a link on index.html's directory) - no need to
// touch every page. The current section auto-highlights. These docs open from a
// real browser (Docs button / F1), so JS is always available.
(function buildNav() {
  // Only list pages that EXIST - a nav link to a missing page is a 404 in the
  // user's browser, which is worse than the page simply not being offered yet.
  var sections = [
    { href: "index.html",           label: "Home" },
    { href: "getting-started.html", label: "Getting Started" },
    { href: "installation.html",    label: "Install & Update" },
    { href: "library.html",         label: "The Library" },
    { href: "capturing.html",       label: "Capturing" },
    { href: "applying.html",        label: "Applying" },
    { href: "versions.html",        label: "Versions" },
    { href: "organizing.html",      label: "Organizing" },
    { href: "review.html",          label: "Review" },
    { href: "removing.html",        label: "Archive & Delete" },
    { href: "storage.html",         label: "Storage" },
    { href: "settings.html",        label: "Settings" },
    { href: "reference.html",       label: "Reference" }
  ];

  var here = location.pathname.split("/").pop() || "index.html";
  var html = '<span class="brand">Action Library</span>';

  sections.forEach(function (s) {
    var active = s.href === here;
    html += '<a class="' + (active ? "active" : "") + '" href="' + s.href + '">' +
            s.label + '</a>';
  });

  var nav = document.querySelector("nav.top");
  if (nav) nav.innerHTML = html;
})();

// In-page table of contents. Each section is one long page; this builds a sticky
// sidebar from that page's h2/h3 headings so the reader can move around without
// going back to the hub. Pages with fewer than two headings get no sidebar -
// there'd be nothing worth navigating.
(function buildToc() {
  var main = document.querySelector("main");
  if (!main || main.hasAttribute("data-no-toc")) return;

  var items = [];
  main.querySelectorAll("h2, h3").forEach(function (h) {
    if (!h.id) {
      h.id = h.textContent.trim().toLowerCase()
              .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    }
    if (h.id) items.push(h);
  });
  if (items.length < 2) return;

  var aside = document.createElement("aside");
  aside.className = "toc";
  var inner = '<div class="toc-title">On this page</div>';
  items.forEach(function (h) {
    inner += '<a class="' + (h.tagName === "H3" ? "lvl3" : "lvl2") +
             '" href="#' + h.id + '">' + h.textContent + '</a>';
  });
  aside.innerHTML = inner;

  var layout = document.createElement("div");
  layout.className = "layout";
  main.parentNode.insertBefore(layout, main);
  layout.appendChild(aside);
  layout.appendChild(main);

  // Scrollspy - highlight whichever heading is at the top of the viewport.
  var links = aside.querySelectorAll("a");
  function spy() {
    var cur = items[0];
    for (var i = 0; i < items.length; i++) {
      if (items[i].getBoundingClientRect().top <= 80) cur = items[i];
      else break;
    }
    links.forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("href") === "#" + cur.id);
    });
  }
  window.addEventListener("scroll", spy, { passive: true });
  spy();
})();
