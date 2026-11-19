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

    QQC2.Label {
        anchors.centerIn: parent
        visible: grid.count === 0
        text: "henüz ajan yok · ctrl+n yeni"
        color: Kirigami.Theme.disabledTextColor
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
