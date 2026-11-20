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

    property bool marked: false

    signal opened()
    signal stopRequested()
    signal deleteRequested()
    signal menuRequested()
    signal markToggled()

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
        border.color: tile.selected || tile.marked ? Ansi.accent : Ansi.rule
        opacity: tile.group === "done" && !tile.selected ? 0.55 : 1

        SequentialAnimation {
            id: pulse
            ColorAnimation { target: frame; property: "border.color"; to: Ansi.yellow; duration: Kirigami.Units.longDuration }
            ColorAnimation { target: frame; property: "border.color"; to: tile.selected ? Ansi.accent : Ansi.rule; duration: Kirigami.Units.longDuration }
        }

        MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: Qt.PointingHandCursor
            onClicked: mouse => {
                if (mouse.button === Qt.RightButton) {
                    tile.act(() => {})
                    tile.menuRequested()
                } else if (mouse.modifiers & Qt.ControlModifier) {
                    tile.markToggled()
                } else {
                    tile.open()
                }
            }
        }

        // Ctrl+click marks tiles for a bulk action; the tick says which ones.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Qt.alpha(Ansi.accent, 0.12)
            visible: tile.marked
        }
        Rectangle {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Kirigami.Units.smallSpacing * 2
            width: Kirigami.Units.gridUnit * 1.2
            height: width
            radius: width / 2
            color: Ansi.accent
            visible: tile.marked
            QQC2.Label {
                anchors.centerIn: parent
                text: "✓"
                color: Ansi.text
                font.bold: true
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing * 2
            spacing: 2

            // The name gets the whole first row; where it runs and how long sits below it, small.
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing * 2

                QQC2.Label {
                    visible: tile.group === "work"
                    text: "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tile.frame % 10]
                    color: Ansi.accent
                }
                QQC2.Label {
                    id: nameLabel
                    text: tile.name
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                QQC2.ToolButton {
                    text: "⋮"
                    focusPolicy: Qt.NoFocus
                    opacity: hover.containsMouse || hovered ? 1 : 0
                    implicitHeight: metaLabel.implicitHeight + Kirigami.Units.smallSpacing
                    onClicked: {
                        tile.act(() => {})
                        tile.menuRequested()
                    }
                }
            }
            QQC2.Label {
                id: metaLabel
                Layout.fillWidth: true
                elide: Text.ElideRight
                color: Ansi.faint
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                text: [tile.project, tile.group === "work" ? tile.age : "", tile.attachable ? "" : "open in a terminal"]
                      .filter(part => part !== "").join(" · ")
            }

            Item {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Body rows use the normal font, so the row height comes from the name, not the small meta line.
                readonly property int step: Math.round(nameLabel.fontInfo.pixelSize * 1.45) + 2

                // Whole lines only, so a tile never shows half a row at the top.
                Item {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: Math.max(0, Math.floor(body.height / body.step)) * body.step
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
                            visible: tile.tail.length === 0 && !tile.asking
                            text: tile.group === "need" ? "Waiting for your first message" : "No output yet"
                            color: Ansi.faint
                            font.italic: true
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
                    AccentButton {
                        required property string modelData
                        required property int index
                        text: (index + 1) + " " + modelData
                        primary: index === 0
                        onClicked: tile.choose(index)
                    }
                }
            }
        }
    }
}
