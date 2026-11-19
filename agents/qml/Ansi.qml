pragma Singleton
import QtQuick

/** HaltMono colours from the Konsole and Plasma schemes, so the app reads like the terminal on any desktop. */
QtObject {
    readonly property color red: "#ef4444"
    readonly property color green: "#22c55e"
    readonly property color yellow: "#eab308"
    readonly property color blue: "#3b82f6"
    readonly property color cyan: "#06b6d4"

    readonly property color bg: "#09090b"
    readonly property color surface: "#18181b"
    readonly property color text: "#fafafa"
    readonly property color faint: "#a1a1aa"
    readonly property color rule: Qt.rgba(0.98, 0.98, 0.98, 0.12)
    readonly property color accent: blue

    function esc(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>")
    }

    function paint(c, s) {
        return "<font color=\"" + c + "\">" + s + "</font>"
    }

    /** One feed item as a single StyledText line, the way Claude Code prints it. */
    function line(item, dim) {
        const body = esc(String(item.body).split("\n")[0])
        switch (item.kind) {
        case "prompt":
            return paint(green, "$") + " " + body
        case "tool":
            return paint(cyan, "⏺ " + esc(item.name)) + "(" + body + ")"
                + (item.added ? " " + paint(green, "+" + item.added) : "")
                + (item.removed ? " " + paint(red, "-" + item.removed) : "")
        case "result":
            return paint(item.error ? red : dim, "&nbsp;&nbsp;⎿ " + body)
        default:
            return paint(dim, "&nbsp;&nbsp;" + body)
        }
    }
}
