import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: bar

    property bool canInterrupt: false
    property bool canTerminal: false
    property bool zoomed: false

    signal triggered(string action)

    spacing: 0

    Repeater {
        model: bar.zoomed ? [
            { action: "zoom", text: "ctrl+o grid" },
            { action: "next", text: "alt+←→ önceki/sonraki" },
            { action: "interrupt", text: "esc kes" },
            { action: "new", text: "ctrl+n yeni" },
            { action: "terminal", text: "ctrl+t terminal" }
        ] : [
            { action: "next", text: "alt+←↑↓→ geç" },
            { action: "zoom", text: "ctrl+o büyüt" },
            { action: "interrupt", text: "esc kes" },
            { action: "new", text: "ctrl+n yeni" },
            { action: "search", text: "ctrl+f ara" },
            { action: "terminal", text: "ctrl+t terminal" }
        ]

        QQC2.ToolButton {
            required property var modelData
            objectName: "key:" + modelData.action
            text: modelData.text
            flat: true
            focusPolicy: Qt.NoFocus
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            enabled: modelData.action === "interrupt" ? bar.canInterrupt
                   : modelData.action === "terminal" ? bar.canTerminal : true
            onClicked: bar.triggered(modelData.action)
        }
    }

    Item {
        Layout.fillWidth: true
    }
}
