// Floating top panel with the HaltOS start dot. Run through PlasmaShell.evaluateScript.
panels().forEach(function (p) {
    p.location = "top";
    p.floating = true;
    p.height = 44;
    // The virtual desktop pager is two grey boxes on a monochrome bar and of little use over RDP.
    p.widgets("org.kde.plasma.pager").forEach(function (w) {
        w.remove();
    });
    p.widgets("org.kde.plasma.kickoff").forEach(function (w) {
        w.currentConfigGroup = ["General"];
        w.writeConfig("icon", "haltos-start");
    });
});
