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
                    { title: "NAV", rows: [
                        "w a s d · arrows · h j k l", "move between agents",
                        "enter · i", "type to the spotlight agent",
                        "1-9", "answer its question",
                        "o · space", "zoom in and out",
                        "x", "interrupt it",
                        "n", "new agent",
                        "/", "search sessions",
                        "t", "open it in a terminal",
                        "esc", "close this, leave zoom"
                    ] },
                    { title: "TYPE", rows: [
                        "enter", "send",
                        "shift+enter", "new line",
                        "esc", "back to NAV, the draft stays",
                        "alt+arrows", "move and keep typing"
                    ] },
                    { title: "ANYWHERE", rows: [
                        "ctrl+n · ctrl+f · ctrl+t · ctrl+o", "new, search, terminal, zoom"
                    ] }
                ]

                ColumnLayout {
                    required property var modelData
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Label {
                        text: modelData.title
                        color: modelData.title === "TYPE" ? Ansi.green : Ansi.accent
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
