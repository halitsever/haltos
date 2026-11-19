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

    property bool zoomed: false

    component Counter: QQC2.Label {
        required property string group
        required property string label
        readonly property int count: root.controller.counts[group] ?? 0
        objectName: "counter:" + group
        visible: count > 0
        text: count + " " + label
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        leftPadding: Kirigami.Units.smallSpacing * 2
        rightPadding: Kirigami.Units.smallSpacing * 2
        topPadding: 1
        bottomPadding: 1
        background: Rectangle {
            radius: height / 2
            color: Qt.alpha(parent.color, 0.14)
        }
    }

    // NAV and TYPE are not stored: the app is typing exactly when a text field has focus.
    readonly property bool typing: activeFocusItem !== null && activeFocusItem.cursorPosition !== undefined
    onTypingChanged: controller.setTyping(typing)

    function inputFocused(): bool {
        const name = activeFocusItem ? activeFocusItem.objectName : ""
        return name === "tileInput" || name === "agentInput"
    }

    function navigate() {
        navigator.forceActiveFocus()
    }

    function focusInput() {
        if (zoomed)
            agentDetail.focusInput()
        else
            agentGrid.focusSelected()
    }

    function type() {
        if (controller.selected.attachable !== true) {
            ttyHint.show("this session is open in a terminal", 2000)
            return
        }
        focusInput()
    }

    // Moves keep the mode: typing stays in the new spotlight's input, navigating stays on the navigator.
    function move(fn) {
        const typingHere = inputFocused()
        fn()
        if (typingHere)
            focusInput()
    }

    function trigger(action: string) {
        if (action.startsWith("answer:")) {
            controller.answer(Number(action.slice(7)))
            return
        }
        switch (action) {
        case "interrupt": controller.interrupt(); break
        case "new": newAgent.open(); break
        case "search": search.forceActiveFocus(); search.selectAll(); break
        case "terminal": controller.openTerminal(); break
        case "type": type(); break
        case "help": help.open = !help.open; break
        case "prev": move(() => controller.step(-1)); break
        case "next": move(() => controller.step(1)); break
        case "up":
        case "down":
            move(() => zoomed ? controller.step(action === "up" ? -1 : 1)
                              : controller.go(action, agentGrid.columns, agentGrid.bigRows))
            break
        case "zoom": {
            const typingHere = inputFocused()
            zoomed = !zoomed
            typingHere ? focusInput() : navigate()
            break
        }
        case "escape":
            if (help.open)
                help.open = false
            else if (zoomed)
                trigger("zoom")
            break
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

    // Kirigami's page stack asks for focus too, so NAV claims it once everything is built.
    Component.onCompleted: navigate()

    // A spotlight that disappears takes its focused input with it and focus drops to the window's root item.
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
        function onShowRequested() {
            root.show()
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

            Counter {
                group: "need"
                label: "seni bekliyor"
                color: Ansi.yellow
            }
            Counter {
                group: "work"
                label: "çalışıyor"
                color: Ansi.accent
            }
            Counter {
                group: "done"
                label: "bitti"
                color: Ansi.faint
            }

            Item {
                Layout.fillWidth: true
            }

            Kirigami.SearchField {
                id: search
                objectName: "searchField"
                Layout.preferredWidth: Kirigami.Units.gridUnit * 16
                placeholderText: "oturumlarda ara…"
                delaySearch: true
                onAccepted: root.controller.search(text)
                Keys.onEscapePressed: {
                    search.clear()
                    root.controller.search("")
                    root.navigate()
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
            visible: root.controller.query === "" && !root.zoomed
            onZoomRequested: root.trigger("zoom")
            onEscaped: root.navigate()
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        AgentDetail {
            id: agentDetail
            objectName: "agentDetail"
            controller: root.controller
            visible: root.controller.query === "" && root.zoomed
            onBack: root.trigger("zoom")
            onEscaped: root.navigate()
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
            zoomed: root.zoomed
            typing: root.typing
            canInterrupt: root.controller.selected.group === "work" && root.controller.selected.attachable === true
            canTerminal: root.controller.selected.attachable === true
            onTriggered: action => root.trigger(action)
        }
    }

    NewAgentDialog {
        id: newAgent
        objectName: "newAgentDialog"
        controller: root.controller
        onClosed: root.navigate()
    }

    // Letter keys are commands only here; text fields never pass them on.
    Item {
        id: navigator
        objectName: "navigator"
        focus: true

        Keys.onPressed: event => {
            if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
                return
            const k = event.key
            const t = event.text.toLowerCase()
            const action = k === Qt.Key_Left || t === "a" || t === "h" ? "prev"
                : k === Qt.Key_Right || t === "d" || t === "l" ? "next"
                : k === Qt.Key_Up || t === "w" || t === "k" ? "up"
                : k === Qt.Key_Down || t === "s" || t === "j" ? "down"
                : k === Qt.Key_Return || k === Qt.Key_Enter || t === "i" ? "type"
                : t.length === 1 && t >= "1" && t <= "9" ? "answer:" + (Number(t) - 1)
                : t === "o" || k === Qt.Key_Space ? "zoom"
                : t === "x" ? "interrupt"
                : t === "n" ? "new"
                : t === "/" ? "search"
                : t === "t" ? "terminal"
                : t === "?" ? "help"
                : k === Qt.Key_Escape ? "escape"
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

    QQC2.ToolTip {
        id: ttyHint
        objectName: "ttyHint"
        x: (root.width - width) / 2
        y: root.height - height - Kirigami.Units.gridUnit * 3
    }
}
