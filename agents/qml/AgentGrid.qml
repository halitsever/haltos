import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property QtObject controller
    readonly property alias columns: grid.columns

    signal zoomRequested()

    // currentIndex follows the user, never the controller: the view hands focus to a new current item,
    // so binding it to the selection would let a poll pull focus.
    function focusSelected() {
        const i = root.controller.selectedIndex
        if (i < 0)
            return
        grid.currentIndex = i
        grid.positionViewAtIndex(i, GridView.Contain)
        if (grid.currentItem)
            grid.currentItem.focusInput()
    }

    GridView {
        id: grid
        objectName: "agentGrid"

        readonly property int columns: Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 22)))

        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        model: root.controller.agents
        clip: true
        cellWidth: Math.floor(width / columns)
        cellHeight: Kirigami.Units.gridUnit * 10
        keyNavigationEnabled: false
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick

        QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

        delegate: AgentTile {
            controller: root.controller
            onZoomRequested: root.zoomRequested()
            onStopRequested: {
                confirmStop.target = agentKey
                confirmStop.targetName = name
                confirmStop.open()
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
            text: "henüz ajan yok"
        }
        QQC2.Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Ansi.paint(Ansi.accent, "n") + " yeni ajan"
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

        title: "Ajanı durdur"
        subtitle: targetName + " durdurulsun mu? Konuşma silinmez."
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            root.controller.select(target)
            root.controller.kill()
        }
    }
}
