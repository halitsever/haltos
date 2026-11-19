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

    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        visible: detail.hasAgent
        spacing: Kirigami.Units.smallSpacing * 2

        Kirigami.Heading {
            level: 3
            text: detail.agent.name ?? ""
            elide: Text.ElideRight
            Layout.maximumWidth: implicitWidth
            Layout.fillWidth: true
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: (detail.agent.cwd ?? "") + (detail.agent.branch ? " · " + detail.agent.branch : "")
            elide: Text.ElideMiddle
            opacity: 0.6
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

        ListView {
            id: feed
            model: detail.controller.feed
            clip: true
            spacing: Kirigami.Units.smallSpacing * 2
            topMargin: Kirigami.Units.largeSpacing
            bottomMargin: Kirigami.Units.largeSpacing
            onCountChanged: Qt.callLater(feed.positionViewAtEnd)

            delegate: QQC2.Label {
                required property string kind
                required property string body

                x: Kirigami.Units.largeSpacing
                width: ListView.view.width - Kirigami.Units.largeSpacing * 2
                wrapMode: Text.Wrap
                textFormat: kind === "text" ? Text.MarkdownText : Text.PlainText
                text: kind === "prompt" ? "› " + body : body
                font.weight: kind === "prompt" ? Font.DemiBold : Font.Normal
                opacity: kind === "tool" ? 0.55 : 1
                leftPadding: kind === "tool" ? Kirigami.Units.largeSpacing : 0
                onLinkActivated: link => Qt.openUrlExternally(link)
            }
        }
    }

    Kirigami.AbstractCard {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        visible: detail.hasAgent && detail.question.text !== undefined

        contentItem: ColumnLayout {
            QQC2.Label {
                Layout.fillWidth: true
                text: detail.question.text ?? ""
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
                        text: modelData
                        highlighted: index === 0
                        onClicked: detail.controller.answer(index)
                    }
                }
            }
        }
    }

    Kirigami.PlaceholderMessage {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !detail.hasAgent
        text: "Bir ajan seç"
    }
}
