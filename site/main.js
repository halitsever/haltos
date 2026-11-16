/* HaltOS site: boot log, wordmark decode, copy buttons and the screens tabs. The page works without it. */
(() => {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const HEX = "0123456789abcdef";
  const rand = (n) => Math.floor(Math.random() * n);

  // Faint hex dump down both edges of the hero, like the wallpaper.
  const hex = document.querySelector(".hex");
  if (hex) {
    const rows = Math.ceil(hex.clientHeight / 20) + 1;
    const cols = Math.ceil(hex.clientWidth / 26);
    let out = "";
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) out += Math.random() < 0.5 ? HEX[rand(16)] + HEX[rand(16)] + " " : "   ";
      out += "\n";
    }
    hex.textContent = out;
  }

  const bootLines = [
    ["ok", "Reached target HaltOS base system."],
    ["ok", "Started claude-code-vps workstation."],
    ["ok", "Started xrdp remote desktop on :53389."],
    ["ok", "Started KWin window manager."],
    ["ok", "Loaded HaltOS mono palette."],
    ["info", "uid0 privileges: granted. shutdown: never."],
  ];
  const boot = document.getElementById("boot");
  const mark = document.querySelector(".wm");

  const renderBoot = (n) => {
    boot.innerHTML = bootLines
      .slice(0, n)
      .map(([kind, text]) => `<span class="${kind}">[${kind === "ok" ? "  OK  " : " INFO "}]</span> ${text}`)
      .join("\n");
  };

  // Each glyph cell starts as a hex digit and settles, sweeping left to right.
  const decode = () => {
    const cells = [...mark.querySelectorAll(".c")].map((g) => ({
      g,
      x: g.nextElementSibling,
      at: Number(g.dataset.col) * 16 + rand(260),
    }));
    mark.classList.add("decoding");
    const start = performance.now();
    const frame = (now) => {
      const t = now - start;
      let left = 0;
      for (const cell of cells) {
        if (cell.done) continue;
        if (t >= cell.at) {
          cell.done = true;
          cell.g.classList.add("on");
          cell.x.classList.add("off");
        } else {
          left++;
          cell.x.textContent = HEX[rand(16)];
        }
      }
      if (left) requestAnimationFrame(frame);
      else mark.classList.remove("decoding");
    };
    requestAnimationFrame(frame);
  };

  if (boot && mark) {
    if (still) {
      renderBoot(bootLines.length);
    } else {
      let n = 0;
      const tick = setInterval(() => {
        renderBoot(++n);
        if (n === bootLines.length) clearInterval(tick);
      }, 110);
      decode();
    }
  }

  document.querySelectorAll(".copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        btn.textContent = "Copied";
        btn.dataset.state = "done";
      } catch {
        btn.textContent = "Select and copy";
      }
      setTimeout(() => {
        btn.textContent = "Copy";
        delete btn.dataset.state;
      }, 1800);
    });
  });

  // Tabs follow the WAI-ARIA pattern: arrow keys move between them, Home and End jump to the ends.
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const select = (tab) => {
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    tab.focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (e) => {
      const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      select(tabs[(next + tabs.length) % tabs.length]);
    });
  });
})();
