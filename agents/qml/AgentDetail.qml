import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: detail

    required property QtObject controller
    readonly property var agent: controller.selected
    readonly property var question: controller.question
    readonly property bool hasAgent: agent.key !== undefined
    readonly property bool canAct: hasAgent && agent.attachable
    readonly property bool asking: question.text !== undefined
    readonly property string draftText: input.text
    readonly property color tone: agent.group === "need" ? Ansi.yellow : agent.group === "work" ? Ansi.accent : Ansi.faint

    signal back()
    signal escaped()
    signal answered(int index)

    function focusInput() {
        input.forceActiveFocus()
    }

    // The draft belongs to the agent, so it is reloaded whenever this screen shows another one.
    readonly property string key: controller.selectedKey
    onKeyChanged: loadDraft()
    onVisibleChanged: {
        if (visible)
            loadDraft()
    }

    function loadDraft() {
        const text = controller.draft(key)
        if (input.text !== text) {
            input.text = text
            input.cursorPosition = input.length
        }
    }

    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        visible: detail.hasAgent
        spacing: Kirigami.Units.smallSpacing * 2

        QQC2.Button {
            objectName: "backButton"
            text: "← Back"
            focusPolicy: Qt.NoFocus
            onClicked: detail.back()
        }
        QQC2.Label {
            text: "●"
            color: detail.tone
        }
        QQC2.Label {
            text: detail.agent.name ?? ""
            font.bold: true
            elide: Text.ElideRight
            Layout.maximumWidth: implicitWidth
            Layout.fillWidth: true
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: (detail.agent.project ?? "") + (detail.agent.branch ? ":" + detail.agent.branch : "")
                  + (detail.agent.model ? " · " + detail.agent.model : "")
            color: Ansi.faint
            elide: Text.ElideMiddle
        }
        QQC2.Button {
            objectName: "interruptButton"
            visible: detail.canAct && detail.agent.group === "work"
            text: "■ Interrupt"
            focusPolicy: Qt.NoFocus
            onClicked: detail.controller.interrupt()
        }
        QQC2.ToolButton {
            text: "⋮"
            focusPolicy: Qt.NoFocus
            enabled: detail.canAct
            onClicked: more.popup()

            QQC2.Menu {
                id: more
                QQC2.MenuItem {
                    text: "open in terminal"
                    onTriggered: detail.controller.openTerminal()
                }
                QQC2.MenuItem {
                    text: "archive"
                    enabled: detail.agent.group === "done"
                    onTriggered: detail.controller.archive()
                }
                QQC2.MenuItem {
                    text: "stop…"
                    onTriggered: {
                        confirmStop.target = detail.agent.key
                        confirmStop.open()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmStop

        // The selection can change while the dialog is open, so it stops the agent it asked about.
        property string target

        title: "Stop agent"
        subtitle: "Stop " + (detail.agent.name ?? "") + "? The conversation is kept."
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            detail.controller.select(target)
            detail.controller.kill()
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: Ansi.rule
        visible: detail.hasAgent
    }

    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        visible: detail.hasAgent
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

        ListView {
            id: feed
            model: detail.controller.feed
            clip: true
            spacing: Kirigami.Units.smallSpacing
            topMargin: Kirigami.Units.largeSpacing
            bottomMargin: Kirigami.Units.largeSpacing
            leftMargin: Kirigami.Units.gridUnit
            rightMargin: Kirigami.Units.gridUnit
            // Wrapped rows settle their height late, so the view stays pinned to the end until the user scrolls up.
            property bool stick: true
            onMovementEnded: stick = atYEnd
            onContentHeightChanged: if (stick) Qt.callLater(feed.positionViewAtEnd)
            onCountChanged: if (stick) Qt.callLater(feed.positionViewAtEnd)

            delegate: QQC2.Label {
                required property string kind
                required property string body
                required property string name
                required property int added
                required property int removed
                required property bool error

                readonly property bool styled: kind === "prompt" || kind === "tool"

                width: ListView.view.width - ListView.view.leftMargin - ListView.view.rightMargin
                topPadding: kind === "prompt" ? Kirigami.Units.smallSpacing * 2 : 0
                leftPadding: kind === "text" || kind === "result" ? Kirigami.Units.gridUnit : 0
                wrapMode: Text.Wrap
                textFormat: styled ? Text.StyledText : Text.PlainText
                color: kind === "result" ? (error ? Ansi.red : Ansi.faint)
                     : kind === "text" ? Ansi.faint : Ansi.text
                text: kind === "prompt" ? Ansi.paint(Ansi.green, "&gt;") + " " + Ansi.esc(body)
                    : kind === "tool" ? Ansi.paint(Ansi.cyan, "⏺ " + Ansi.esc(name)) + "(" + Ansi.esc(body) + ")"
                                        + (added ? " " + Ansi.paint(Ansi.green, "+" + added) : "")
                                        + (removed ? " " + Ansi.paint(Ansi.red, "-" + removed) : "")
                    : kind === "result" ? "⎿ " + body
                    : body
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.smallSpacing
        visible: detail.hasAgent && detail.asking
        implicitHeight: questionBox.implicitHeight + Kirigami.Units.largeSpacing * 2
        radius: 8
        color: "transparent"
        border.width: 1
        border.color: Qt.alpha(Ansi.yellow, 0.35)

        ColumnLayout {
            id: questionBox
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label {
                Layout.fillWidth: true
                textFormat: Text.StyledText
                text: Ansi.paint(Ansi.yellow, "?") + " " + Ansi.esc(detail.question.text ?? "")
                wrapMode: Text.Wrap
            }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                visible: detail.canAct

                Repeater {
                    model: detail.question.options ?? []
                    QQC2.Button {
                        required property string modelData
                        required property int index
                        text: (index + 1) + " " + modelData
                        highlighted: index === 0
                        focusPolicy: Qt.NoFocus
                        onClicked: detail.answered(index)
                    }
                }
            }
        }
    }

    // Bordered like Claude Code's prompt box.
    Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.largeSpacing
        visible: detail.hasAgent
        implicitHeight: promptRow.implicitHeight + Kirigami.Units.smallSpacing * 2
        Layout.topMargin: Kirigami.Units.smallSpacing
        radius: 8
        color: "transparent"
        border.width: 1
        border.color: input.activeFocus ? Ansi.faint : Ansi.rule

        RowLayout {
            id: promptRow
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            anchors.leftMargin: Kirigami.Units.largeSpacing
            anchors.rightMargin: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label {
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: input.topPadding
                topPadding: 0
                text: ">"
                color: detail.canAct ? Ansi.text : Ansi.faint
            }
            QQC2.TextArea {
                id: input
                objectName: "agentInput"
                Layout.fillWidth: true
                Layout.maximumHeight: Kirigami.Units.gridUnit * 8
                leftPadding: 0
                background: null
                enabled: detail.canAct
                wrapMode: TextEdit.Wrap
                placeholderText: detail.canAct ? "Message " + (detail.agent.name ?? "") + "…"
                                               : "This session is open in a terminal"
                onTextChanged: detail.controller.setDraft(detail.key, text)
                Keys.onEscapePressed: detail.escaped()
                Keys.onPressed: event => {
                    // Like Claude Code: a digit answers the question, unless a reply is being typed.
                    const t = event.text
                    if (text === "" && detail.asking && t.length === 1 && t >= "1" && t <= "9"
                            && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                        event.accepted = true
                        detail.answered(Number(t) - 1)
                    }
                }
                Keys.onReturnPressed: event => {
                    if (event.modifiers & Qt.ShiftModifier) {
                        event.accepted = false
                        return
                    }
                    // Keep the text when it could not be delivered, so nothing typed is lost.
                    if (detail.controller.send(input.text))
                        input.clear()
                }
            }
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !detail.hasAgent
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: "No agent selected"
        color: Ansi.faint
    }
}
