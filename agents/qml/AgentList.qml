import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: list

    required property QtObject controller

    signal newAgentRequested()
    signal searchLeft()
    signal picked()

    function focusSearch() {
        search.forceActiveFocus()
        search.selectAll()
    }

    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing * 2

        Kirigami.SearchField {
            id: search
            objectName: "searchField"
            Layout.fillWidth: true
            placeholderText: "oturumlarda ara…"
            delaySearch: true
            onAccepted: list.controller.search(text)
            Keys.onEscapePressed: {
                search.clear()
                list.controller.search("")
                list.searchLeft()
            }
        }
        QQC2.ToolButton {
            text: "+"
            focusPolicy: Qt.NoFocus
            QQC2.ToolTip.text: "Yeni ajan (ctrl+n)"
            QQC2.ToolTip.visible: hovered
            onClicked: list.newAgentRequested()
        }
    }

    QQC2.Label {
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.smallSpacing
        text: list.controller.query === "" ? "AGENTS" : "SONUÇLAR"
        color: Kirigami.Theme.disabledTextColor
        font.pointSize: Kirigami.Theme.smallFont.pointSize
    }

    SearchResults {
        controller: list.controller
        onPicked: list.picked()
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

            delegate: QQC2.ItemDelegate {
                id: row
                required property string key
                required property string name
                required property string group
                required property string cwd
                required property string age
                required property bool attachable

                width: ListView.view.width
                highlighted: key === list.controller.selectedKey
                focusPolicy: Qt.NoFocus
                onClicked: {
                    list.controller.select(key)
                    list.picked()
                }
                QQC2.ToolTip.text: cwd
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay

                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing * 2

                    QQC2.Label {
                        text: row.group === "need" ? "!" : row.group === "work" ? "▶" : "✓"
                        color: row.group === "need" ? Ansi.yellow
                             : row.group === "work" ? Ansi.blue : Kirigami.Theme.disabledTextColor
                        font.bold: row.group === "need"
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: row.name
                        elide: Text.ElideRight
                        color: row.group === "done" ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.textColor
                    }
                    QQC2.Label {
                        visible: !row.attachable
                        text: "tty"
                        color: Kirigami.Theme.disabledTextColor
                        QQC2.ToolTip.text: "Bir terminalde açık"
                    }
                    QQC2.Label {
                        text: row.age
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
            }

            QQC2.Label {
                anchors.centerIn: parent
                visible: view.count === 0
                text: "henüz ajan yok"
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
}
