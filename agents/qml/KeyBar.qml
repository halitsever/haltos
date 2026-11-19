import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: bar

    property bool canInterrupt: false
    property bool canTerminal: false

    signal triggered(string action)

    spacing: 0

    Repeater {
        model: [
            { action: "interrupt", text: "esc kes" },
            { action: "new", text: "ctrl+n yeni" },
            { action: "search", text: "ctrl+f ara" },
            { action: "terminal", text: "ctrl+t terminal" },
            { action: "next", text: "alt+↑↓ geç" }
        ]

        QQC2.ToolButton {
            required property var modelData
            objectName: "key:" + modelData.action
            text: modelData.text
            flat: true
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
