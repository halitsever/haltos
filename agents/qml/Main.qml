import QtQuick
import QtQuick.Controls as QQC2
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

    property bool zoomed: false

    function focusInput() {
        if (zoomed)
            agentDetail.focusInput()
        else
            agentGrid.focusSelected()
    }

    function trigger(action: string) {
        switch (action) {
        case "interrupt": controller.interrupt(); break
        case "new": newAgent.open(); break
        case "search": search.forceActiveFocus(); search.selectAll(); break
        case "terminal": controller.openTerminal(); break
        case "prev": controller.step(-1); focusInput(); break
        case "next": controller.step(1); focusInput(); break
        case "up": zoomed ? controller.step(-1) : controller.go("up", agentGrid.columns, 2); focusInput(); break
        case "down": zoomed ? controller.step(1) : controller.go("down", agentGrid.columns, 2); focusInput(); break
        case "zoom": zoomed = !zoomed; focusInput(); break
        }
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: root.trigger("new") }
    Shortcut { sequence: "Ctrl+F"; onActivated: root.trigger("search") }
    Shortcut { sequence: "Ctrl+T"; onActivated: root.trigger("terminal") }
    Shortcut { sequence: "Ctrl+O"; onActivated: root.trigger("zoom") }
    Shortcut { sequence: "Alt+Left"; onActivated: root.trigger("prev") }
    Shortcut { sequence: "Alt+Right"; onActivated: root.trigger("next") }
    Shortcut { sequence: "Alt+Up"; onActivated: root.trigger("up") }
    Shortcut { sequence: "Alt+Down"; onActivated: root.trigger("down") }

    // Focus moves only on what the user does. The one exception is the first agent showing up
    // while nothing else holds focus, so typing works right after the window opens.
    property bool placedFocus: false
    Connections {
        target: root.controller
        function onChanged() {
            if (root.placedFocus || root.controller.selectedIndex < 0)
                return
            root.placedFocus = true
            if (!newAgent.visible && !search.activeFocus)
                Qt.callLater(root.focusInput)
        }
    }

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
            root.focusInput()
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
            Layout.margins: Kirigami.Units.smallSpacing * 2

            Kirigami.SearchField {
                id: search
                objectName: "searchField"
                Layout.fillWidth: true
                placeholderText: "oturumlarda ara…"
                delaySearch: true
                onAccepted: root.controller.search(text)
                Keys.onEscapePressed: {
                    search.clear()
                    root.controller.search("")
                    root.focusInput()
                }
            }
            QQC2.ToolButton {
                text: "+"
                focusPolicy: Qt.NoFocus
                QQC2.ToolTip.text: "Yeni ajan (ctrl+n)"
                QQC2.ToolTip.visible: hovered
                onClicked: newAgent.open()
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        SearchResults {
            controller: root.controller
            onPicked: root.focusInput()
            visible: root.controller.query !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        AgentGrid {
            id: agentGrid
            controller: root.controller
            visible: root.controller.query === "" && !root.zoomed
            onZoomRequested: root.trigger("zoom")
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        AgentDetail {
            id: agentDetail
            objectName: "agentDetail"
            controller: root.controller
            visible: root.controller.query === "" && root.zoomed
            onBack: root.trigger("zoom")
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        KeyBar {
            objectName: "keyBar"
            Layout.fillWidth: true
            zoomed: root.zoomed
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
