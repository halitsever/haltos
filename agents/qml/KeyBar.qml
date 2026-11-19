import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: bar

    property bool canInterrupt: false
    property bool canTerminal: false
    property bool zoomed: false
    property bool typing: false

    signal triggered(string action)

    spacing: 0

    QQC2.Label {
        objectName: "modeBadge"
        Layout.leftMargin: Kirigami.Units.smallSpacing * 2
        Layout.rightMargin: Kirigami.Units.smallSpacing
        text: bar.typing ? "TYPE" : "NAV"
        color: Ansi.bg
        font.bold: true
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        leftPadding: Kirigami.Units.smallSpacing * 2
        rightPadding: Kirigami.Units.smallSpacing * 2
        background: Rectangle {
            radius: 3
            color: bar.typing ? Ansi.green : Ansi.accent
        }
    }

    Repeater {
        model: bar.typing ? [
            { key: "enter", label: "send" },
            { key: "shift+enter", label: "newline" },
            { key: "esc", label: "nav" }
        ] : bar.zoomed ? [
            { key: "a d", label: "prev/next", action: "next" },
            { key: "enter", label: "type", action: "type" },
            { key: "1-9", label: "answer" },
            { key: "esc", label: "grid", action: "zoom" },
            { key: "x", label: "interrupt", action: "interrupt" },
            { key: "t", label: "terminal", action: "terminal" }
        ] : [
            { key: "wasd", label: "move" },
            { key: "enter", label: "type", action: "type" },
            { key: "1-9", label: "answer" },
            { key: "o", label: "zoom", action: "zoom" },
            { key: "x", label: "interrupt", action: "interrupt" },
            { key: "n", label: "new", action: "new" },
            { key: "/", label: "search", action: "search" },
            { key: "?", label: "keys", action: "help" }
        ]

        QQC2.ToolButton {
            required property var modelData
            readonly property string act: modelData.action ?? ""

            // The KDE style paints `text` itself, so the hint lives in its own property and label.
            readonly property string hint: modelData.key + " " + modelData.label

            objectName: "key:" + (act || modelData.key)
            flat: true
            focusPolicy: Qt.NoFocus
            hoverEnabled: act !== ""
            enabled: act === "interrupt" ? bar.canInterrupt
                   : act === "terminal" ? bar.canTerminal : true
            onClicked: if (act) bar.triggered(act)

            implicitWidth: hintLabel.implicitWidth + Kirigami.Units.smallSpacing * 4
            contentItem: QQC2.Label {
                id: hintLabel
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                textFormat: Text.StyledText
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                opacity: parent.enabled ? 1 : 0.4
                text: Ansi.paint(Ansi.text, Ansi.esc(modelData.key)) + " " + Ansi.paint(Ansi.faint, modelData.label)
            }
        }
    }

    Item {
        Layout.fillWidth: true
    }
}
