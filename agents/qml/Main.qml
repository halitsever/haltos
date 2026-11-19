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
    font: Kirigami.Theme.fixedWidthFont

    function trigger(action: string) {
        switch (action) {
        case "interrupt": controller.interrupt(); break
        case "new": newAgent.open(); break
        case "search": agentList.focusSearch(); break
        case "terminal": controller.openTerminal(); break
        case "prev": controller.step(-1); break
        case "next": controller.step(1); break
        }
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: root.trigger("new") }
    Shortcut { sequence: "Ctrl+F"; onActivated: root.trigger("search") }
    Shortcut { sequence: "Ctrl+T"; onActivated: root.trigger("terminal") }
    Shortcut { sequence: "Alt+Up"; onActivated: root.trigger("prev") }
    Shortcut { sequence: "Alt+Down"; onActivated: root.trigger("next") }

    onActiveChanged: controller.setWindowActive(active)

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
            objectName: "errorMessage"
            Layout.fillWidth: true
            visible: root.controller.error !== ""
            type: Kirigami.MessageType.Error
            text: root.controller.error
            // The built-in close button overwrites the visible binding, so later errors would stay hidden.
            showCloseButton: false
            actions: Kirigami.Action {
                text: "Kapat"
                onTriggered: root.controller.dismissError()
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: root.controller.untrustedDir !== ""
            type: Kirigami.MessageType.Warning
            text: root.controller.untrustedDir + " klasörüne henüz güvenilmedi. Konsole'da Claude Code'un güven sorusunu onayla, sonra yeniden başlat."
            actions: [
                Kirigami.Action {
                    text: "Konsole'da aç"
                    icon.name: "utilities-terminal"
                    onTriggered: root.controller.trustInKonsole()
                },
                Kirigami.Action {
                    text: "Yeniden başlat"
                    icon.name: "media-playback-start"
                    onTriggered: root.controller.retryLaunch()
                },
                Kirigami.Action {
                    text: "Vazgeç"
                    onTriggered: root.controller.dismissUntrusted()
                }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            AgentList {
                id: agentList
                controller: root.controller
                onNewAgentRequested: newAgent.open()
                onSearchLeft: agentDetail.focusInput()
                Layout.preferredWidth: Kirigami.Units.gridUnit * 15
                Layout.maximumWidth: Kirigami.Units.gridUnit * 15
                Layout.fillHeight: true
            }

            Kirigami.Separator {
                Layout.fillHeight: true
            }

            AgentDetail {
                id: agentDetail
                controller: root.controller
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        KeyBar {
            objectName: "keyBar"
            Layout.fillWidth: true
            canInterrupt: root.controller.selected.group === "work" && root.controller.selected.attachable === true
            canTerminal: root.controller.selected.attachable === true
            onTriggered: action => root.trigger(action)
        }
    }

    NewAgentDialog {
        id: newAgent
        objectName: "newAgentDialog"
        controller: root.controller
    }
}
