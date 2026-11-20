import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: overlay

    property bool open: false

    visible: open
    color: Qt.alpha(Ansi.bg, 0.75)

    MouseArea {
        anchors.fill: parent
        onClicked: overlay.open = false
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - Kirigami.Units.gridUnit * 2, sheet.implicitWidth + Kirigami.Units.gridUnit * 2)
        height: sheet.implicitHeight + Kirigami.Units.gridUnit * 2
        radius: 6
        color: Ansi.surface
        border.width: 1
        border.color: Ansi.rule

        // Swallows clicks so only a click outside the card closes it.
        MouseArea {
            anchors.fill: parent
        }

        ColumnLayout {
            id: sheet
            anchors.centerIn: parent
            spacing: Kirigami.Units.largeSpacing

            // Rows alternate key and meaning, filling the two grid columns.
            Repeater {
                model: [
                    { title: "KEYS", rows: [
                        "←↑↓→ · w a s d · h j k l", "select an agent",
                        "enter · click · t", "open it in Claude Code",
                        "1 2 …", "answer its question",
                        "x · ctrl+k", "interrupt it",
                        "delete", "delete it (asks first)",
                        "n · ctrl+n", "new agent in the last folder",
                        "ctrl+g", "switch between the grid and Tasks",
                        "ctrl+tab · alt+0..9", "next tab or pane, jump to a tab",
                        "/ · ctrl+f", "search old sessions",
                        "?", "these keys"
                    ] }
                ]

                ColumnLayout {
                    required property var modelData
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Label {
                        text: modelData.title
                        color: Ansi.accent
                        font.bold: true
                    }
                    GridLayout {
                        columns: 2
                        columnSpacing: Kirigami.Units.gridUnit
                        rowSpacing: 2

                        Repeater {
                            model: modelData.rows
                            QQC2.Label {
                                required property string modelData
                                required property int index
                                text: modelData
                                color: index % 2 === 0 ? Ansi.text : Ansi.faint
                            }
                        }
                    }
                }
            }
        }
    }
}
