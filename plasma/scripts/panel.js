// Floating top panel with the HaltOS start dot. Run through PlasmaShell.evaluateScript.
panels().forEach(function (p) {
    p.location = "top";
    p.floating = true;
    p.height = 32;
    // The virtual desktop pager is two grey boxes on a monochrome bar and of little use over RDP.
    p.widgets("org.kde.plasma.pager").forEach(function (w) {
        w.remove();
    });
    // A slim bar has no room for the date under the time, so it goes beside it.
    p.widgets("org.kde.plasma.digitalclock").forEach(function (w) {
        w.currentConfigGroup = ["Appearance"];
        w.writeConfig("dateDisplayFormat", 1);
        // Auto size grows the clock to the panel height, which looks huge on a thicker bar.
        w.writeConfig("autoFontAndSize", false);
        w.writeConfig("fontFamily", "JetBrains Mono");
        w.writeConfig("fontSize", 10);
        w.writeConfig("fontWeight", 400);
    });
    p.widgets("org.kde.plasma.kickoff").forEach(function (w) {
        w.currentConfigGroup = ["General"];
        w.writeConfig("icon", "haltos-start");
    });
});
