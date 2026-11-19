import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property QtObject controller
    readonly property alias columns: grid.columns

    signal zoomRequested()

    function focusSelected() {
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
        currentIndex: root.controller.selectedIndex
        keyNavigationEnabled: false
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        onCurrentIndexChanged: {
            if (currentIndex >= 0)
                positionViewAtIndex(currentIndex, GridView.Contain)
        }

        QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

        delegate: AgentTile {
            controller: root.controller
            onZoomRequested: root.zoomRequested()
            onStopRequested: confirmStop.open()
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
        title: "Ajanı durdur"
        subtitle: (root.controller.selected.name ?? "") + " durdurulsun mu? Konuşma silinmez."
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: root.controller.kill()
    }
}
