import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: bar

    property bool canInterrupt: false
    property bool agentTab: false

    signal triggered(string action)

    spacing: 0
    Layout.leftMargin: Kirigami.Units.smallSpacing

    Repeater {
        model: bar.agentTab ? [
            { key: "ctrl+tab", label: "next tab" },
            { key: "alt+0", label: "agents" },
            { key: "ctrl+shift+v", label: "paste" },
            { key: "ctrl+shift+w", label: "close tab" }
        ] : [
            { key: "←↑↓→", label: "select" },
            { key: "enter", label: "open in Claude Code", action: "open" },
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
            enabled: act === "interrupt" ? bar.canInterrupt : true
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
