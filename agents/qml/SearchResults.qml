import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.ScrollView {
    id: results

    required property QtObject controller

    ListView {
        id: view
        model: results.controller.results
        clip: true

        delegate: QQC2.ItemDelegate {
            id: hit
            required property string sessionId
            required property string title
            required property string cwd
            required property string where
            required property string date
            required property string snippet

            width: ListView.view.width
            onClicked: results.controller.resume(sessionId, cwd)
            QQC2.ToolTip.text: "Bu oturumu ajan olarak sürdür"
            QQC2.ToolTip.visible: hovered
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay

            contentItem: ColumnLayout {
                spacing: 2
                QQC2.Label {
                    Layout.fillWidth: true
                    text: hit.title
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: hit.where + " · " + hit.date
                    elide: Text.ElideMiddle
                    opacity: 0.6
                    font: Kirigami.Theme.smallFont
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: hit.snippet
                    elide: Text.ElideRight
                    maximumLineCount: 2
                    wrapMode: Text.Wrap
                    opacity: 0.75
                    font: Kirigami.Theme.smallFont
                }
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 2
            visible: view.count === 0
            text: "Sonuç yok"
        }
    }
}
