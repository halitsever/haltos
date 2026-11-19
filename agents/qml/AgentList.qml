import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: list

    required property QtObject controller

    spacing: 0

    QQC2.ScrollView {
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
