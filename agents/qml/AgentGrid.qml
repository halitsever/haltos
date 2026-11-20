import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property QtObject controller
    readonly property alias columns: grid.columns

    signal opened()
    signal newRequested()
    signal deleteRequested(string key, string name)
    signal clearDoneRequested()

    function hint(text: string) {
        tip.show(text, 2000)
    }

    QQC2.ToolTip {
        id: tip
        objectName: "gridHint"
        x: (root.width - width) / 2
        y: root.height - height - Kirigami.Units.gridUnit
    }

    component SectionHeader: QQC2.Label {
        required property string group
        required property string title
        readonly property int at: grid.order.indexOf(group)
        readonly property var info: at < 0 ? null : grid.sections[at]

        objectName: "section:" + group
        visible: at >= 0
        x: Kirigami.Units.smallSpacing
        y: info ? info[2] * grid.cellHeight + at * grid.headerHeight : 0
        height: grid.headerHeight
        verticalAlignment: Text.AlignBottom
        bottomPadding: Kirigami.Units.smallSpacing
        font.bold: true
        text: title + "  " + (info ? info[1] : 0)

        Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
    }

    Flickable {
        id: grid
        objectName: "agentGrid"

        readonly property int columns: Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 16)))
        readonly property real cellWidth: Math.floor(width / columns)
        readonly property real cellHeight: Kirigami.Units.gridUnit * 7
        readonly property real headerHeight: Kirigami.Units.gridUnit * 2
        readonly property int count: tiles.count
        property var cells: []
        property var sections: []
        readonly property var order: sections.map(s => s[0])
        property int frame: 0
        property string revealed: ""

        // Layout lives in Python, so QML re-reads it whenever the rows or the width change.
        // It scrolls only when the selected tile moved, so a poll never undoes the user's scrolling.
        function relayout() {
            cells = root.controller.tiles(columns)
            sections = root.controller.sections(columns)
            const spot = JSON.stringify([root.controller.selectedKey, cells[root.controller.selectedIndex]])
            // Hidden behind a tab the grid has no real height, so scrolling waits until it shows again.
            if (spot !== revealed && visible) {
                revealed = spot
                Qt.callLater(reveal)
            }
        }

        // Sections run in row order, so a tile belongs to the last section starting at or above its row.
        function sectionOf(index: int): int {
            const row = cells[index] ? cells[index][1] : 0
            let at = 0
            for (let i = 0; i < sections.length; i++)
                if (sections[i][2] <= row)
                    at = i
            return at
        }

        function tileTop(index: int): real {
            const cell = cells[index]
            return cell ? cell[1] * cellHeight + (sectionOf(index) + 1) * headerHeight : 0
        }

        function reveal() {
            const i = root.controller.selectedIndex
            if (!cells[i])
                return
            const y0 = tileTop(i)
            const y1 = y0 + cellHeight
            if (y0 - headerHeight < contentY)
                contentY = Math.max(0, y0 - headerHeight)
            else if (y1 > contentY + height)
                contentY = Math.min(y1, contentHeight) - height
        }

        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        clip: true
        contentWidth: width
        contentHeight: cells.length ? tileTop(cells.length - 1) + cellHeight : 0
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick

        QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

        onColumnsChanged: relayout()
        onVisibleChanged: if (visible) relayout()
        Component.onCompleted: relayout()

        Connections {
            target: root.controller
            function onChanged() {
                grid.relayout()
            }
        }

        Timer {
            objectName: "spinner"
            interval: 90
            repeat: true
            running: grid.visible && root.Window.window !== null && root.Window.window.visible && (root.controller.counts.work ?? 0) > 0
            onTriggered: grid.frame++
        }

        SectionHeader {
            group: "need"
            title: "● Waiting for you"
            color: Ansi.yellow
        }
        SectionHeader {
            group: "work"
            title: "◐ Working"
            color: Ansi.accent
        }
        SectionHeader {
            id: doneHeader
            group: "done"
            title: "✓ Done"
            color: Ansi.faint
        }
        AccentButton {
            objectName: "clearDone"
            visible: doneHeader.visible
            primary: false
            compact: true
            text: "Clear"
            x: doneHeader.x + doneHeader.implicitWidth + Kirigami.Units.largeSpacing
            // Centred on the header's text line, which sits at the bottom of the header.
            y: doneHeader.y + doneHeader.height - doneHeader.bottomPadding - doneHeader.contentHeight / 2 - height / 2
            onClicked: root.clearDoneRequested()
        }

        Repeater {
            id: tiles
            model: root.controller.agents

            delegate: AgentTile {
                readonly property var cell: grid.cells[index] ?? [0, 0]

                controller: root.controller
                frame: grid.frame
                x: cell[0] * grid.cellWidth
                y: grid.tileTop(index)
                width: grid.cellWidth
                height: grid.cellHeight

                Behavior on x { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }

                onOpened: root.opened()
                onDeleteRequested: root.deleteRequested(agentKey, name)
                onStopRequested: {
                    confirmStop.target = agentKey
                    confirmStop.targetName = name
                    confirmStop.open()
                }
            }
        }
    }

    Column {
        objectName: "emptyState"
        anchors.centerIn: parent
        visible: grid.count === 0
        spacing: Kirigami.Units.largeSpacing

        Image {
            anchors.horizontalCenter: parent.horizontalCenter
            source: "haltos-mark.svg"
            sourceSize.height: 64
            opacity: 0.85
        }
        QQC2.Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "No agents yet"
        }
        AccentButton {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "+ New agent"
            onClicked: root.newRequested()
        }
    }

    Kirigami.PromptDialog {
        id: confirmStop
        objectName: "stopDialog"

        // The selection can change while the dialog is open, so it stops the agent it asked about.
        property string target
        property string targetName

        title: "Stop agent"
        subtitle: "Stop " + targetName + "? The conversation is kept."
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            root.controller.select(target)
            root.controller.kill()
        }
    }
}
