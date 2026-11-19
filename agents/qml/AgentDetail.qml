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

    signal back()

    function focusInput() {
        input.forceActiveFocus()
    }

    // The tile and this view edit the same per-agent draft, so reload it whenever either side may have changed it.
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

        QQC2.ToolButton {
            objectName: "backButton"
            text: "← grid"
            flat: true
            focusPolicy: Qt.NoFocus
            onClicked: detail.back()
        }
        QQC2.Label {
            text: detail.agent.name ?? ""
            color: Ansi.green
            font.bold: true
            elide: Text.ElideRight
            Layout.maximumWidth: implicitWidth
            Layout.fillWidth: true
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: (detail.agent.project ?? "") + (detail.agent.branch ? ":" + detail.agent.branch : "")
                  + (detail.agent.model ? " · " + detail.agent.model : "")
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideMiddle
            QQC2.ToolTip.text: detail.agent.cwd ?? ""
            QQC2.ToolTip.visible: tipArea.containsMouse
            MouseArea {
                id: tipArea
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
            }
        }
        QQC2.ToolButton {
            text: "⋮"
            focusPolicy: Qt.NoFocus
            enabled: detail.canAct
            onClicked: more.popup()

            QQC2.Menu {
                id: more
                QQC2.MenuItem {
                    text: "arşivle"
                    enabled: detail.agent.group === "done"
                    onTriggered: detail.controller.archive()
                }
                QQC2.MenuItem {
                    text: "durdur…"
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

        title: "Ajanı durdur"
        subtitle: (detail.agent.name ?? "") + " durdurulsun mu? Konuşma silinmez."
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            detail.controller.select(target)
            detail.controller.kill()
        }
    }

    Kirigami.Separator {
        Layout.fillWidth: true
        visible: detail.hasAgent
    }

    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: detail.hasAgent
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

        ListView {
            id: feed
            model: detail.controller.feed
            clip: true
            spacing: Kirigami.Units.smallSpacing
            topMargin: Kirigami.Units.largeSpacing
            bottomMargin: Kirigami.Units.largeSpacing
            leftMargin: Kirigami.Units.largeSpacing
            rightMargin: Kirigami.Units.largeSpacing
            onCountChanged: Qt.callLater(feed.positionViewAtEnd)

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
                color: kind === "result" ? (error ? Ansi.red : Kirigami.Theme.disabledTextColor)
                     : kind === "text" ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.textColor
                text: kind === "prompt" ? Ansi.paint(Ansi.green, "$") + " " + Ansi.esc(body)
                    : kind === "tool" ? Ansi.paint(Ansi.cyan, "⏺ " + Ansi.esc(name)) + "(" + Ansi.esc(body) + ")"
                                        + (added ? " " + Ansi.paint(Ansi.green, "+" + added) : "")
                                        + (removed ? " " + Ansi.paint(Ansi.red, "-" + removed) : "")
                    : kind === "result" ? "⎿ " + body
                    : body
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        visible: detail.hasAgent && detail.question.text !== undefined
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
                    text: "[" + (index + 1) + "] " + modelData
                    flat: true
                    focusPolicy: Qt.NoFocus
                    highlighted: index === 0
                    onClicked: detail.controller.answer(index)
                }
            }
        }
    }

    Kirigami.Separator {
        Layout.fillWidth: true
        visible: detail.hasAgent
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        visible: detail.hasAgent
        spacing: Kirigami.Units.smallSpacing

        QQC2.Label {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: input.topPadding
            text: ">"
            color: detail.canAct ? Ansi.green : Kirigami.Theme.disabledTextColor
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
            placeholderText: detail.canAct ? "ajana yaz… enter gönderir, shift+enter yeni satır"
                                           : "bu oturum bir terminalde açık, buradan yönetilemez"
            onTextChanged: detail.controller.setDraft(detail.key, text)
            Keys.onEscapePressed: detail.controller.interrupt()
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

    QQC2.Label {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !detail.hasAgent
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: "ajan seçilmedi"
        color: Kirigami.Theme.disabledTextColor
    }
}
