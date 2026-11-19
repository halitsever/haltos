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
    color: Ansi.bg
    font: Qt.fontFamilies().indexOf("JetBrains Mono") >= 0
          ? Qt.font({ family: "JetBrains Mono", pointSize: Kirigami.Theme.fixedWidthFont.pointSize })
          : Kirigami.Theme.fixedWidthFont

    // HaltMono whatever the desktop theme is, so the app looks the same in every screenshot.
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.backgroundColor: Ansi.bg
    Kirigami.Theme.alternateBackgroundColor: Ansi.surface
    Kirigami.Theme.textColor: Ansi.text
    Kirigami.Theme.disabledTextColor: Ansi.faint
    Kirigami.Theme.highlightColor: Ansi.accent
    Kirigami.Theme.highlightedTextColor: Ansi.text

    readonly property bool searching: controller.query !== ""

    function navigate() {
        navigator.forceActiveFocus()
    }

    function trigger(action: string) {
        // With search results on screen the agents are hidden, so keys aimed at them wait.
        if (searching && !["new", "search", "help", "escape"].includes(action))
            return
        if (action.startsWith("answer:")) {
            controller.answer(Number(action.slice(7)))
            return
        }
        switch (action) {
        case "open": openSelected(); break
        case "interrupt": controller.interrupt(); break
        case "new": newAgent.open(); break
        case "search": search.forceActiveFocus(); search.selectAll(); break
        case "help": help.open = !help.open; break
        case "prev": controller.step(-1); break
        case "next": controller.step(1); break
        case "up":
        case "down": controller.go(action, agentGrid.columns); break
        case "escape":
            if (help.open)
                help.open = false
            else if (searching)
                clearSearch()
            break
        }
    }

    // A session already open in a terminal cannot be attached twice, so the user is told instead.
    function openSelected() {
        if (controller.selectedIndex < 0)
            return
        if (controller.selected.attachable !== true)
            agentGrid.hint("Already open in a terminal")
        else
            controller.openTerminal()
    }

    function clearSearch() {
        search.clear()
        controller.search("")
        navigate()
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: root.trigger("new") }
    Shortcut { sequence: "Ctrl+F"; onActivated: root.trigger("search") }
    Shortcut { sequence: "Ctrl+K"; onActivated: root.trigger("interrupt") }

    // Kirigami's page stack asks for focus too, so the grid claims it once everything is built.
    Component.onCompleted: {
        navigate()
        if (!startHidden)
            showMaximized()
    }

    // Focus that drops to nothing or the window's root item goes back to the grid.
    function focusLost(): bool {
        return !activeFocusItem || activeFocusItem.parent === null
    }
    onActiveFocusItemChanged: {
        if (active && focusLost())
            Qt.callLater(() => {
                if (root.focusLost())
                    root.navigate()
            })
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
        // A new window would take the keyboard from whatever the user is typing into here.
        function onLaunchReady(key) {
            if (!newAgent.visible && !search.activeFocus)
                root.controller.openTerminal()
        }
        function onShowRequested() {
            if (!root.visible)
                root.showMaximized()
            root.raise()
            root.requestActivate()
            root.navigate()
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
                text: "Close"
                onTriggered: root.controller.dismissError()
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: root.controller.untrustedDir !== ""
            type: Kirigami.MessageType.Warning
            text: root.controller.untrustedDir + " is not trusted yet. Accept Claude Code's trust prompt in Konsole, then start again."
            actions: [
                Kirigami.Action {
                    text: "Open in Konsole"
                    icon.name: "utilities-terminal"
                    onTriggered: root.controller.trustInKonsole()
                },
                Kirigami.Action {
                    text: "Start again"
                    icon.name: "media-playback-start"
                    onTriggered: root.controller.retryLaunch()
                },
                Kirigami.Action {
                    text: "Dismiss"
                    onTriggered: root.controller.dismissUntrusted()
                }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing * 2
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                objectName: "brand"
                spacing: Kirigami.Units.smallSpacing * 2

                Image {
                    source: "haltos-mark.svg"
                    sourceSize.height: Kirigami.Units.gridUnit
                    Layout.preferredHeight: Kirigami.Units.gridUnit
                    Layout.preferredWidth: Kirigami.Units.gridUnit
                }
                QQC2.Label {
                    text: "agents"
                    font.bold: true
                }
            }

            Item {
                Layout.fillWidth: true
            }

            Kirigami.SearchField {
                id: search
                objectName: "searchField"
                Layout.preferredWidth: Kirigami.Units.gridUnit * 16
                placeholderText: "search sessions…"
                delaySearch: true
                onAccepted: root.controller.search(text)
                Keys.onEscapePressed: {
                    root.clearSearch()
                }
            }
            QQC2.Button {
                objectName: "newButton"
                text: "+ New agent"
                highlighted: true
                focusPolicy: Qt.NoFocus
                QQC2.ToolTip.text: "ctrl+n"
                QQC2.ToolTip.visible: hovered
                onClicked: newAgent.open()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: Ansi.rule
        }

        SearchResults {
            controller: root.controller
            onPicked: root.navigate()
            visible: root.controller.query !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        AgentGrid {
            id: agentGrid
            controller: root.controller
            visible: root.controller.query === ""
            onOpened: root.trigger("open")
            onNewRequested: newAgent.open()
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: Ansi.rule
        }

        KeyBar {
            objectName: "keyBar"
            Layout.fillWidth: true
            canInterrupt: root.controller.selected.group === "work" && root.controller.selected.attachable === true
            onTriggered: action => root.trigger(action)
        }
    }

    NewAgentDialog {
        id: newAgent
        objectName: "newAgentDialog"
        controller: root.controller
        onClosed: root.navigate()
    }

    // Holds focus on the grid. Text fields never pass letters on, so here they are always commands.
    Item {
        id: navigator
        objectName: "navigator"
        focus: true

        Keys.onPressed: event => {
            if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
                return
            const k = event.key
            const t = event.text.toLowerCase()
            const action = k === Qt.Key_Escape ? "escape"
                : t === "?" ? "help"
                : help.open ? ""
                : k === Qt.Key_Left || t === "a" || t === "h" ? "prev"
                : k === Qt.Key_Right || t === "d" || t === "l" ? "next"
                : k === Qt.Key_Up || t === "w" || t === "k" ? "up"
                : k === Qt.Key_Down || t === "s" || t === "j" ? "down"
                : k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Space ? "open"
                : t.length === 1 && t >= "1" && t <= "9" ? "answer:" + (Number(t) - 1)
                : t === "x" ? "interrupt"
                : t === "n" ? "new"
                : t === "/" ? "search"
                : t === "t" ? "open"
                : ""
            if (!action)
                return
            event.accepted = true
            root.trigger(action)
        }
    }

    HelpOverlay {
        id: help
        objectName: "helpOverlay"
        anchors.fill: parent
    }
}
