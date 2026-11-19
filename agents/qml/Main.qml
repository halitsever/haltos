import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    readonly property QtObject controller: agentsController
    required property bool hideOnClose
    required property bool startHidden

    title: "HaltOS Agents"
    width: Kirigami.Units.gridUnit * 62
    height: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 22
    visible: !startHidden

    onClosing: close => {
        if (hideOnClose) {
            close.accepted = false
            root.hide()
        }
    }

    Connections {
        target: root.controller
        function onShowRequested() {
            root.show()
            root.raise()
            root.requestActivate()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: root.controller.error !== ""
            type: Kirigami.MessageType.Error
            text: root.controller.error
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            AgentList {
                controller: root.controller
                Layout.preferredWidth: Kirigami.Units.gridUnit * 15
                Layout.fillHeight: true
            }

            Kirigami.Separator {
                Layout.fillHeight: true
            }

            AgentDetail {
                controller: root.controller
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }
    }
}
