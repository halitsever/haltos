// Floating panel with the HaltOS start dot. Run through PlasmaShell.evaluateScript.
panels().forEach(function (p) {
    p.floating = true;
    p.height = 44;
    p.widgets("org.kde.plasma.kickoff").forEach(function (w) {
        w.currentConfigGroup = ["General"];
        w.writeConfig("icon", "haltos-start");
    });
});
