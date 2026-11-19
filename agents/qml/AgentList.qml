import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: list

    required property QtObject controller

    signal newAgentRequested()

    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing * 2

        Kirigami.SearchField {
            Layout.fillWidth: true
            placeholderText: "Oturumlarda ara…"
            delaySearch: true
            onAccepted: list.controller.search(text)
        }
        QQC2.ToolButton {
            icon.name: "list-add"
            QQC2.ToolTip.text: "Yeni ajan"
            QQC2.ToolTip.visible: hovered
            onClicked: list.newAgentRequested()
        }
    }

    SearchResults {
        controller: list.controller
        visible: list.controller.query !== ""
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    QQC2.ScrollView {
        visible: list.controller.query === ""
        Layout.fillWidth: true
        Layout.fillHeight: true

        ListView {
            id: view
            model: list.controller.agents
            clip: true
            section.property: "groupLabel"
            section.delegate: Kirigami.ListSectionHeader {
                required property string section
                width: ListView.view.width
                text: section
            }

            delegate: QQC2.ItemDelegate {
                id: row
                required property string key
                required property string name
                required property string group
                required property string cwd
                required property bool attachable

                width: ListView.view.width
                highlighted: key === list.controller.selectedKey
                onClicked: list.controller.select(key)
                QQC2.ToolTip.text: cwd
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay

                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing * 2

                    StatusDot {
                        group: row.group
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: row.name
                        elide: Text.ElideRight
                    }
                    Kirigami.Icon {
                        visible: !row.attachable
                        source: "utilities-terminal"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: implicitWidth
                        opacity: 0.5
                    }
                }
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 2
                visible: view.count === 0
                text: "Henüz ajan yok"
            }
        }
    }
}
