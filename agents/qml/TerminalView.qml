import QtQuick
import org.kde.kirigami as Kirigami

// Draws one agent's Claude Code and hands it every key, so its own shortcuts and menus all work.
FocusScope {
    id: view
    objectName: "terminalView"

    required property QtObject terminal
    required property font termFont

    readonly property real cellWidth: metrics.advanceWidth("M")
    readonly property real cellHeight: Math.ceil(metrics.height)
    readonly property int cols: Math.max(10, Math.floor((width - Kirigami.Units.largeSpacing * 2) / cellWidth))
    readonly property int rows: Math.max(3, Math.floor((height - Kirigami.Units.largeSpacing * 2) / cellHeight))

    function sendSize() {
        if (terminal && width > 0 && height > 0)
            terminal.resize(cols, rows)
    }

    onColsChanged: Qt.callLater(sendSize)
    onRowsChanged: Qt.callLater(sendSize)
    Component.onCompleted: Qt.callLater(sendSize)

    FontMetrics {
        id: metrics
        font: view.termFont
    }

    Rectangle {
        anchors.fill: parent
        color: Ansi.bg
    }

    Item {
        id: screen
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        clip: true

        Column {
            Repeater {
                model: view.terminal ? view.terminal.rows : null
                Text {
                    required property string html
                    height: view.cellHeight
                    font: view.termFont
                    color: Ansi.text
                    textFormat: Text.RichText
                    text: html
                }
            }
        }

        Rectangle {
            visible: view.terminal !== null && view.terminal.cursorVisible
            x: view.terminal ? view.terminal.cursorX * view.cellWidth : 0
            y: view.terminal ? view.terminal.cursorY * view.cellHeight : 0
            width: view.cellWidth
            height: view.cellHeight
            color: Ansi.text
            opacity: view.activeFocus ? 0.6 : 0.25
        }
    }

    // Reads the clipboard: QML has no clipboard API of its own.
    TextEdit {
        id: clipboard
        visible: false
    }

    MouseArea {
        anchors.fill: parent
        onClicked: view.forceActiveFocus()
        onWheel: wheel => view.terminal.scroll(wheel.angleDelta.y > 0 ? -1 : 1)
    }

    focus: true
    Keys.onPressed: event => {
        if (!view.terminal)
            return
        event.accepted = true
        if (event.key === Qt.Key_V && (event.modifiers & Qt.ControlModifier) && (event.modifiers & Qt.ShiftModifier)) {
            clipboard.text = ""
            clipboard.paste()
            if (clipboard.text !== "")
                view.terminal.paste(clipboard.text)
            return
        }
        view.terminal.key(event.key, event.text, event.modifiers)
    }
}
