import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property QtObject controller
    readonly property alias columns: grid.columns
    readonly property alias bigRows: grid.bigRows

    signal zoomRequested()
    signal escaped()

    function spotlight(): Item {
        return tiles.itemAt(root.controller.selectedIndex)
    }

    function focusSelected() {
        grid.reveal()
        const tile = spotlight()
        if (tile)
            tile.focusInput()
    }

    Flickable {
        id: grid
        objectName: "agentGrid"

        readonly property int columns: Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 16)))
        readonly property real cellWidth: Math.floor(width / columns)
        readonly property real cellHeight: Kirigami.Units.gridUnit * 6
        readonly property int bigRows: Math.max(2, Math.round(height / 2 / cellHeight))
        readonly property int count: tiles.count
        property var rects: []
        property int frame: 0

        // Packing lives in Python, so QML re-reads it whenever the rows, the selection or the size change.
        function relayout() {
            rects = root.controller.pack(columns, bigRows)
            Qt.callLater(reveal)
        }

        function reveal() {
            const r = rects[root.controller.selectedIndex]
            if (!r)
                return
            const top = r[1] * cellHeight
            const bottom = top + r[3] * cellHeight
            if (top < contentY)
                contentY = top
            else if (bottom > contentY + height)
                contentY = Math.min(bottom, contentHeight) - height
        }

        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        clip: true
        contentWidth: width
        contentHeight: rects.reduce((end, r) => Math.max(end, (r[1] + r[3]) * cellHeight), 0)
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick

        QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

        onColumnsChanged: relayout()
        onBigRowsChanged: relayout()
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
            running: grid.visible && (root.controller.counts.work ?? 0) > 0
            onTriggered: grid.frame++
        }

        Repeater {
            id: tiles
            model: root.controller.agents

            delegate: AgentTile {
                readonly property var rect: grid.rects[index] ?? [0, 0, 1, 1]

                controller: root.controller
                big: agentKey === root.controller.selectedKey
                frame: grid.frame
                x: rect[0] * grid.cellWidth
                y: rect[1] * grid.cellHeight
                width: rect[2] * grid.cellWidth
                height: rect[3] * grid.cellHeight

                Behavior on x { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
                Behavior on width { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
                Behavior on height { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }

                onZoomRequested: root.zoomRequested()
                onEscaped: root.escaped()
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
            text: "no agents yet"
        }
        QQC2.Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Ansi.paint(Ansi.accent, "n") + " new agent"
            textFormat: Text.StyledText
            color: Ansi.faint
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
