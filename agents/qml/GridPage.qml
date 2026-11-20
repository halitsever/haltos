import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The open agents side by side, like claudegrid's panes. Empty cells offer a new agent.
Item {
    id: page
    objectName: "gridPage"

    required property QtObject controller
    required property font termFont

    readonly property var size: controller.gridLayout.split("x").map(Number)
    readonly property int cols: size[0]
    readonly property int rows: size[1]
    onColsChanged: if (visible) Qt.callLater(() => controller.fillGrid(cols * rows))
    onRowsChanged: if (visible) Qt.callLater(() => controller.fillGrid(cols * rows))
    readonly property var keys: controller.tabKeys
    property int focusedCell: 0

    signal maximize(int tab)
    signal newAgent()
    signal deleteRequested(string key, string name)

    function focusCell(index: int) {
        const cell = cells.itemAt(index)
        if (cell && cell.view) {
            focusedCell = index
            cell.view.forceActiveFocus()
        }
    }

    function cycle(step: int) {
        const used = Math.min(keys.length, cols * rows)
        if (used > 0)
            focusCell((focusedCell + step + used) % used)
    }

    GridLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        columns: page.cols
        rowSpacing: Kirigami.Units.smallSpacing
        columnSpacing: Kirigami.Units.smallSpacing

        Repeater {
            id: cells
            model: page.cols * page.rows

            Rectangle {
                id: cell

                required property int index
                readonly property string key: index < page.keys.length ? page.keys[index] : ""
                readonly property var agent: key ? page.controller.agentInfo(key) : ({})
                readonly property Item view: loader.item && loader.item.terminal !== undefined ? loader.item : null
                readonly property bool focused: view !== null && view.activeFocus

                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.preferredHeight: 1
                radius: 6
                color: "transparent"
                border.width: focused ? 2 : 1
                border.color: focused ? Ansi.accent : Ansi.rule

                // Under the header's own buttons: a double click on the bar opens the agent in its own tab.
                MouseArea {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: paneHeader.height + cell.border.width
                    enabled: cell.key !== ""
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: mouse => {
                        if (mouse.button === Qt.RightButton)
                            paneMenu.popup()
                        else if (cell.view)
                            cell.view.forceActiveFocus()
                    }
                    onDoubleClicked: page.maximize(cell.index + 1)
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: cell.border.width
                    spacing: 0
                    visible: cell.key !== ""

                    RowLayout {
                        id: paneHeader
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.largeSpacing
                        Layout.rightMargin: Kirigami.Units.smallSpacing
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 1.6
                        spacing: Kirigami.Units.smallSpacing * 2

                        QQC2.Label {
                            text: "●"
                            color: cell.agent.group === "need" ? Ansi.yellow : cell.agent.group === "work" ? Ansi.accent : Ansi.faint
                        }
                        QQC2.Label {
                            text: cell.agent.name ?? ""
                            color: cell.focused ? Ansi.text : Ansi.faint
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        QQC2.Label {
                            text: "⋮"
                            color: paneMenuArea.containsMouse ? Ansi.text : Ansi.faint
                            MouseArea {
                                id: paneMenuArea
                                anchors.fill: parent
                                anchors.margins: -Kirigami.Units.smallSpacing
                                hoverEnabled: true
                                onClicked: paneMenu.popup()
                            }
                            QQC2.Menu {
                                id: paneMenu
                                QQC2.MenuItem {
                                    text: "Open in its own tab"
                                    onTriggered: page.maximize(cell.index + 1)
                                }
                                QQC2.MenuItem {
                                    text: "Open folder"
                                    onTriggered: page.controller.openFolder(cell.key)
                                }
                                QQC2.MenuItem {
                                    text: "Open in VS Code"
                                    onTriggered: page.controller.openInCode(cell.key)
                                }
                                QQC2.MenuSeparator {}
                                QQC2.MenuItem {
                                    text: "Delete…"
                                    onTriggered: page.deleteRequested(cell.key, cell.agent.name ?? cell.key)
                                }
                            }
                        }
                        QQC2.Label {
                            objectName: "maximize"
                            text: "⤢"
                            color: maxArea.containsMouse ? Ansi.text : Ansi.faint
                            QQC2.ToolTip.text: "Open in its own tab"
                            QQC2.ToolTip.visible: maxArea.containsMouse
                            MouseArea {
                                id: maxArea
                                anchors.fill: parent
                                anchors.margins: -Kirigami.Units.smallSpacing
                                hoverEnabled: true
                                onClicked: page.maximize(cell.index + 1)
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 1
                        color: Ansi.rule
                    }
                    Loader {
                        id: loader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: cell.key !== ""
                        sourceComponent: TerminalView {
                            terminal: page.controller.terminal(cell.key)
                            termFont: page.termFont
                            onActiveFocusChanged: if (activeFocus) page.focusedCell = cell.index
                        }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    visible: cell.key === ""
                    spacing: Kirigami.Units.largeSpacing

                    QQC2.Label {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Empty"
                        color: Ansi.faint
                    }
                    AccentButton {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "+ New agent"
                        onClicked: page.newAgent()
                    }
                }
            }
        }
    }
}
