import QtQuick

// HaltOS login: one shadcn-style card on the wallpaper. Uses only QtQuick so it runs on any SDDM Qt6 greeter.
Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#09090b"

    readonly property color fg: "#fafafa"
    readonly property color mutedFg: "#a1a1aa"
    readonly property color border: "#27272a"
    readonly property color ring: "#d4d4d8"
    readonly property color accent: "#27272a"
    readonly property color danger: "#ef4444"
    readonly property string mono: "JetBrains Mono"
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property string error: ""

    function submit() {
        error = "";
        sddm.login(userField.text, passwordField.text, sessionIndex);
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.error = "authentication failed";
            passwordField.text = "";
            passwordField.forceActiveFocus();
        }
    }

    Image {
        anchors.fill: parent
        source: config.background
        fillMode: Image.PreserveAspectCrop
        opacity: 1
    }

    // Hidden list view reads session names, which SDDM only exposes through a model.
    ListView {
        id: sessions
        model: sessionModel
        visible: false
        currentIndex: root.sessionIndex
        delegate: Item { property string sessionName: model.name }
    }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: 380
        height: content.implicitHeight + 64
        radius: 12
        color: "#09090b"
        border.color: root.border
        border.width: 1

        Column {
            id: content
            anchors.fill: parent
            anchors.margins: 32
            spacing: 14

            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: "wordmark.png"
                width: parent.width * 0.8
                height: width * sourceSize.height / sourceSize.width
                smooth: true
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: sddm.hostName ? "sign in to " + sddm.hostName : "sign in"
                color: root.mutedFg
                font.family: root.mono
                font.pixelSize: 13
            }

            Item { width: 1; height: 4 }

            Field {
                id: userField
                label: "username"
                text: userModel.lastUser
                KeyNavigation.tab: passwordField
                onAccepted: passwordField.forceActiveFocus()
            }

            Field {
                id: passwordField
                label: "password"
                secret: true
                KeyNavigation.tab: userField
                onAccepted: root.submit()
                Component.onCompleted: if (userField.text.length) forceActiveFocus()
            }

            Rectangle {
                width: parent.width
                height: 38
                radius: 6
                color: signIn.pressed ? "#e4e4e7" : root.fg

                Text {
                    anchors.centerIn: parent
                    text: "Sign in"
                    color: "#18181b"
                    font.family: root.mono
                    font.pixelSize: 14
                    font.weight: Font.Medium
                }

                MouseArea {
                    id: signIn
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.submit()
                }
            }

            Text {
                width: parent.width
                visible: root.error.length > 0
                text: root.error
                color: root.danger
                font.family: root.mono
                font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    Text {
        anchors.top: card.bottom
        anchors.topMargin: 16
        anchors.horizontalCenter: card.horizontalCenter
        text: "session: " + (sessions.currentItem ? sessions.currentItem.sessionName : "default") + "  [click to change]"
        color: root.mutedFg
        font.family: root.mono
        font.pixelSize: 12

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.sessionIndex = (root.sessionIndex + 1) % Math.max(1, sessionModel.rowCount())
        }
    }

    Text {
        id: clock
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 28
        color: root.fg
        font.family: root.mono
        font.pixelSize: 15
        function tick() { text = Qt.formatDateTime(new Date(), "ddd dd MMM  HH:mm") }
        Component.onCompleted: tick()
        Timer { interval: 10000; running: true; repeat: true; onTriggered: clock.tick() }
    }

    Text {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 28
        text: "HaltOS 1.0 // SIGKILL"
        color: root.mutedFg
        font.family: root.mono
        font.pixelSize: 13
    }

    Row {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 28
        spacing: 8

        Repeater {
            model: [
                { label: "reboot", enabled: sddm.canReboot, act: function () { sddm.reboot() } },
                { label: "shutdown", enabled: sddm.canPowerOff, act: function () { sddm.powerOff() } }
            ]
            Rectangle {
                required property var modelData
                visible: modelData.enabled
                width: label.implicitWidth + 24
                height: 32
                radius: 6
                color: area.containsMouse ? root.accent : "transparent"
                border.color: root.border

                Text {
                    id: label
                    anchors.centerIn: parent
                    text: modelData.label
                    color: root.fg
                    font.family: root.mono
                    font.pixelSize: 12
                }

                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modelData.act()
                }
            }
        }
    }

    component Field: Rectangle {
        id: field
        property alias text: input.text
        property string label
        property bool secret: false
        signal accepted()

        function forceActiveFocus() { input.forceActiveFocus() }

        width: parent.width
        height: 38
        radius: 6
        color: "transparent"
        border.color: input.activeFocus ? root.ring : root.border
        border.width: 1

        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter
            color: root.fg
            selectionColor: root.accent
            font.family: root.mono
            font.pixelSize: 14
            echoMode: field.secret ? TextInput.Password : TextInput.Normal
            passwordCharacter: "*"
            clip: true
            onAccepted: field.accepted()
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 12
            visible: input.text.length === 0
            text: field.label
            color: "#71717a"
            font.family: root.mono
            font.pixelSize: 14
        }
    }
}
