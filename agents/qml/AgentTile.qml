import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A focus scope, so focus handed to the tile lands in its input.
FocusScope {
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

    property bool big: false
    property int frame: 0

    readonly property string agentKey: key
    readonly property bool selected: key === controller.selectedKey
    readonly property bool asking: question.text !== undefined
    readonly property color rail: group === "need" ? Ansi.yellow : group === "work" ? Ansi.accent : Ansi.rule

    signal zoomRequested()
    signal stopRequested()
    signal escaped()

    function focusInput() {
        input.forceActiveFocus()
    }

    // A poll can move the selection while focus stays here, so every action selects its own agent first.
    function act(fn) {
        if (!selected)
            controller.select(key)
        fn()
    }

    function choose(option: int) {
        act(() => controller.answer(option))
    }

    function loadDraft() {
        const text = controller.draft(key)
        if (input.text !== text) {
            input.text = text
            input.cursorPosition = input.length
        }
    }

    onBigChanged: {
        if (!big)
            return
        loadDraft()
        input.cursorPosition = input.length
    }
    onVisibleChanged: if (visible && big) loadDraft()

    property string lastGroup: group
    onGroupChanged: {
        if (group === "need" && lastGroup !== "need")
            pulse.restart()
        lastGroup = group
    }

    Kirigami.ShadowedRectangle {
        id: frame
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        radius: 4
        color: tile.big ? Ansi.surface : Qt.alpha(Ansi.surface, 0.55)
        border.width: 1
        border.color: tile.big ? Ansi.accent : Ansi.rule
        shadow.size: tile.big ? Kirigami.Units.gridUnit : 0
        shadow.color: Qt.alpha(Ansi.accent, 0.35)
        opacity: tile.group === "done" && !tile.big ? 0.55 : 1

        Behavior on shadow.size { NumberAnimation { duration: Kirigami.Units.longDuration } }

        MouseArea {
            anchors.fill: parent
            onClicked: tile.act(() => {})
            onDoubleClicked: tile.zoomRequested()
        }

        Rectangle {
            id: railBar
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 1
            width: 3
            radius: 1
            color: tile.rail

            SequentialAnimation {
                id: pulse
                NumberAnimation { target: railBar; property: "opacity"; to: 0.3; duration: Kirigami.Units.longDuration }
                NumberAnimation { target: railBar; property: "opacity"; to: 1; duration: Kirigami.Units.longDuration }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 4
            anchors.topMargin: 1
            anchors.rightMargin: 1
            anchors.bottomMargin: 1
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                spacing: Kirigami.Units.smallSpacing * 2

                QQC2.Label {
                    text: tile.group === "need" ? "!" : tile.group === "work" ? "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tile.frame % 10] : "✓"
                    color: tile.rail === Ansi.rule ? Ansi.faint : tile.rail
                    font.bold: tile.group === "need"
                }
                QQC2.Label {
                    text: tile.name
                    font.bold: tile.big
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
                    text: tile.age
                    color: Ansi.faint
                }
                QQC2.ToolButton {
                    text: "⋮"
                    focusPolicy: Qt.NoFocus
                    enabled: tile.attachable
                    onClicked: {
                        tile.act(() => {})
                        more.popup()
                    }

                    QQC2.Menu {
                        id: more
                        QQC2.MenuItem {
                            text: "arşivle"
                            enabled: tile.group === "done"
                            onTriggered: tile.act(() => tile.controller.archive())
                        }
                        QQC2.MenuItem {
                            text: "durdur…"
                            onTriggered: tile.act(() => tile.stopRequested())
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: Ansi.rule
            }

            Item {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true

                readonly property int step: Math.round(projectLabel.fontInfo.pixelSize * 1.45) + 2

                // Whole lines only, so a small tile never shows half a row at the top.
                Item {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: Kirigami.Units.smallSpacing
                    height: Math.floor((body.height - Kirigami.Units.smallSpacing * 2) / body.step) * body.step
                    clip: true

                    // Bottom-aligned so the newest lines stay visible and older ones fall off the top.
                    Column {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: Kirigami.Units.smallSpacing * 2
                        anchors.rightMargin: Kirigami.Units.smallSpacing * 2
                        spacing: 2

                        Repeater {
                            model: tile.tail
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
                        Flow {
                            width: parent.width
                            visible: tile.big && tile.asking && tile.attachable
                            spacing: Kirigami.Units.smallSpacing

                            Repeater {
                                model: tile.question.options ?? []
                                QQC2.Button {
                                    required property string modelData
                                    required property int index
                                    text: (index + 1) + " " + modelData
                                    flat: index !== 0
                                    focusPolicy: Qt.NoFocus
                                    highlighted: index === 0
                                    onClicked: tile.choose(index)
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                visible: tile.big
                Layout.fillWidth: true
                implicitHeight: 1
                color: Ansi.rule
            }

            RowLayout {
                visible: tile.big
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                spacing: Kirigami.Units.smallSpacing

                QQC2.Label {
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: input.topPadding
                    text: ">"
                    color: tile.attachable ? Ansi.green : Ansi.faint
                }
                QQC2.TextArea {
                    id: input
                    objectName: "tileInput"
                    focus: true
                    Layout.fillWidth: true
                    Layout.maximumHeight: Kirigami.Units.gridUnit * 3
                    leftPadding: 0
                    background: null
                    enabled: tile.attachable
                    wrapMode: TextEdit.Wrap
                    placeholderText: tile.attachable ? "" : "bu oturum bir terminalde açık"
                    Component.onCompleted: tile.loadDraft()
                    onTextChanged: tile.controller.setDraft(tile.key, text)
                    onActiveFocusChanged: {
                        if (activeFocus && !tile.selected)
                            tile.controller.select(tile.key)
                    }
                    Keys.onEscapePressed: tile.escaped()
                    Keys.onReturnPressed: event => {
                        if (event.modifiers & Qt.ShiftModifier) {
                            event.accepted = false
                            return
                        }
                        // Keep the text when it could not be delivered, so nothing typed is lost.
                        tile.act(() => {
                            if (tile.controller.send(input.text))
                                input.clear()
                        })
                    }
                }
            }
        }
    }
}
