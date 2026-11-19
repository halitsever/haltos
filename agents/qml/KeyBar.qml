import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: bar

    property bool canInterrupt: false
    property bool canTerminal: false
    property bool agentOpen: false

    signal triggered(string action)

    spacing: 0
    Layout.leftMargin: Kirigami.Units.smallSpacing

    Repeater {
        model: bar.agentOpen ? [
            { key: "enter", label: "send" },
            { key: "shift+enter", label: "new line" },
            { key: "1 2", label: "answer" },
            { key: "ctrl+k", label: "interrupt", action: "interrupt" },
            { key: "esc", label: "back", action: "back" }
        ] : [
            { key: "←↑↓→", label: "select" },
            { key: "enter", label: "open", action: "open" },
            { key: "1 2", label: "answer" },
            { key: "n", label: "new agent", action: "new" },
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
