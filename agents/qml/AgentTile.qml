import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// A focus scope, so when the view hands focus to the current tile it lands in the input.
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

    readonly property string agentKey: key
    readonly property bool selected: key === controller.selectedKey
    readonly property color line: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                          Kirigami.Theme.textColor.b, 0.18)

    signal zoomRequested()
    signal stopRequested()

    function focusInput() {
        input.forceActiveFocus()
    }

    // A poll can move the selection while focus stays here, so every action selects its own agent first.
    function act(fn) {
        if (!selected)
            controller.select(key)
        fn()
    }

    function choose(index: int) {
        act(() => controller.answer(index))
    }

    width: GridView.view.cellWidth
    height: GridView.view.cellHeight

    Rectangle {
        id: frame
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        color: "transparent"
        border.width: 1
        border.color: tile.selected ? Ansi.blue : tile.line
        opacity: tile.group === "done" && !tile.selected ? 0.55 : 1

        MouseArea {
            anchors.fill: parent
            onClicked: {
                tile.act(() => {})
                tile.focusInput()
            }
            onDoubleClicked: tile.zoomRequested()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 1
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                spacing: Kirigami.Units.smallSpacing * 2

                QQC2.Label {
                    text: tile.group === "need" ? "!" : tile.group === "work" ? "▶" : "✓"
                    color: tile.group === "need" ? Ansi.yellow
                         : tile.group === "work" ? Ansi.blue : Kirigami.Theme.disabledTextColor
                    font.bold: tile.group === "need"
                }
                QQC2.Label {
                    text: tile.name
                    elide: Text.ElideRight
                    Layout.maximumWidth: implicitWidth
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    text: tile.project
                    color: Kirigami.Theme.disabledTextColor
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    visible: !tile.attachable
                    text: "tty"
                    color: Kirigami.Theme.disabledTextColor
                }
                QQC2.Label {
                    text: tile.age
                    color: Kirigami.Theme.disabledTextColor
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
                color: tile.line
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                // Bottom-aligned so the newest lines stay visible and older ones fall off the top.
                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Kirigami.Units.smallSpacing * 2
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
                            text: Ansi.line(modelData, Kirigami.Theme.disabledTextColor)
                        }
                    }
                    QQC2.Label {
                        width: parent.width
                        visible: tile.question.text !== undefined
                        textFormat: Text.StyledText
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        text: Ansi.paint(Ansi.yellow, "?") + " " + Ansi.esc(tile.question.text ?? "")
                    }
                    Flow {
                        width: parent.width
                        visible: tile.question.text !== undefined && tile.attachable
                        spacing: Kirigami.Units.smallSpacing

                        Repeater {
                            model: tile.question.options ?? []
                            QQC2.Button {
                                required property string modelData
                                required property int index
                                text: "[" + (index + 1) + "] " + modelData
                                flat: true
                                focusPolicy: Qt.NoFocus
                                highlighted: index === 0
                                onClicked: tile.choose(index)
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: tile.line
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                spacing: Kirigami.Units.smallSpacing

                QQC2.Label {
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: input.topPadding
                    text: ">"
                    color: tile.attachable ? Ansi.green : Kirigami.Theme.disabledTextColor
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
                    Component.onCompleted: text = tile.controller.draft(tile.key)
                    onTextChanged: tile.controller.setDraft(tile.key, text)
                    onActiveFocusChanged: {
                        if (activeFocus && !tile.selected)
                            tile.controller.select(tile.key)
                    }
                    Keys.onEscapePressed: tile.act(() => tile.controller.interrupt())
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
