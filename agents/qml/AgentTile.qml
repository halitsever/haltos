import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: tile
    objectName: "agentTile"

    required property QtObject controller
    required property string key
    required property string name
    required property string group
    required property string project
    required property string age
    required property bool attachable
    required property var tail
    required property var question
    required property int index

    property int frame: 0

    readonly property string agentKey: key
    readonly property bool selected: key === controller.selectedKey
    readonly property bool asking: question.text !== undefined
    readonly property color tone: group === "need" ? Ansi.yellow : group === "work" ? Ansi.accent : Ansi.faint

    signal opened()
    signal stopRequested()

    // A poll can move the selection, so every action selects its own agent first.
    function act(fn) {
        if (!selected)
            controller.select(key)
        fn()
    }

    function choose(option: int) {
        act(() => controller.answer(option))
    }

    function open() {
        act(() => {})
        opened()
    }

    property string lastGroup: group
    onGroupChanged: {
        if (group === "need" && lastGroup !== "need")
            pulse.restart()
        lastGroup = group
    }

    Rectangle {
        id: frame
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        radius: 6
        color: Qt.alpha(Ansi.surface, 0.55)
        border.width: tile.selected ? 2 : 1
        border.color: tile.selected ? Ansi.accent : Ansi.rule
        opacity: tile.group === "done" && !tile.selected ? 0.55 : 1

        SequentialAnimation {
            id: pulse
            ColorAnimation { target: frame; property: "border.color"; to: Ansi.yellow; duration: Kirigami.Units.longDuration }
            ColorAnimation { target: frame; property: "border.color"; to: tile.selected ? Ansi.accent : Ansi.rule; duration: Kirigami.Units.longDuration }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: tile.open()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing * 2
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing * 2

                QQC2.Label {
                    visible: tile.group === "work"
                    text: "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tile.frame % 10]
                    color: Ansi.accent
                }
                QQC2.Label {
                    text: tile.name
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.maximumWidth: implicitWidth
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    id: projectLabel
                    text: tile.project
                    color: Ansi.faint
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    visible: !tile.attachable
                    text: "tty"
                    color: Ansi.faint
                }
                QQC2.Label {
                    // The section header already names the status, so only working agents show their age.
                    visible: tile.group === "work"
                    text: tile.age
                    color: Ansi.faint
                }
                QQC2.ToolButton {
                    text: "⋮"
                    focusPolicy: Qt.NoFocus
                    enabled: tile.attachable
                    implicitHeight: projectLabel.implicitHeight
                    onClicked: {
                        tile.act(() => {})
                        more.popup()
                    }

                    QQC2.Menu {
                        id: more
                        QQC2.MenuItem {
                            text: "archive"
                            enabled: tile.group === "done"
                            onTriggered: tile.act(() => tile.controller.archive())
                        }
                        QQC2.MenuItem {
                            text: "stop…"
                            onTriggered: tile.act(() => tile.stopRequested())
                        }
                    }
                }
            }

            Item {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true

                readonly property int step: Math.round(projectLabel.fontInfo.pixelSize * 1.45) + 2

                // Whole lines only, so a tile never shows half a row at the top.
                Item {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: Math.floor(body.height / body.step) * body.step
                    clip: true

                    // Bottom-aligned so the newest lines stay visible and older ones fall off the top.
                    Column {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        spacing: 2

                        Repeater {
                            model: tile.tail.slice(-4)
                            QQC2.Label {
                                required property var modelData
                                width: parent.width
                                textFormat: Text.StyledText
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                // Glyphs like ⎿ come from a fallback font with a taller line; keep rows even.
                                height: Math.round(fontInfo.pixelSize * 1.45)
                                verticalAlignment: Text.AlignVCenter
                                text: Ansi.line(modelData, Ansi.faint)
                            }
                        }
                        QQC2.Label {
                            width: parent.width
                            visible: tile.asking
                            textFormat: Text.StyledText
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            text: Ansi.paint(Ansi.yellow, "?") + " " + Ansi.esc(tile.question.text ?? "")
                        }
                    }
                }
            }

            Flow {
                objectName: "answerButtons"
                Layout.fillWidth: true
                visible: tile.asking && tile.attachable
                spacing: Kirigami.Units.smallSpacing

                Repeater {
                    model: tile.question.options ?? []
                    QQC2.Button {
                        required property string modelData
                        required property int index
                        text: (index + 1) + " " + modelData
                        highlighted: index === 0
                        focusPolicy: Qt.NoFocus
                        onClicked: tile.choose(index)
                    }
                }
            }
        }
    }
}
