import QtQuick

Rectangle {
    id: root
    color: "#09090b"

    property int stage
    property var bootLines: [
        "[  OK  ] Reached target HaltOS base system.",
        "[  OK  ] Mounted /home.",
        "[  OK  ] Started KWin window manager.",
        "[  OK  ] Started D-Bus session bus.",
        "[  OK  ] Loaded HaltOS mono palette.",
        "[  OK  ] Started Plasma shell.",
        "[  OK  ] Reached target graphical session.",
        "[ INFO ] uid0 privileges: granted. shutdown: never."
    ]
    property int shown: 0

    Timer {
        interval: 160
        repeat: true
        running: root.shown < root.bootLines.length
        onTriggered: root.shown++
    }

    // ksplash advances stage as Plasma starts; the log catches up so it never trails the real boot.
    onStageChanged: shown = Math.max(shown, Math.min(bootLines.length, stage + 2))

    Row {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -parent.height * 0.08
        spacing: 14

        Image {
            id: wordmark
            source: "images/wordmark.png"
            width: Math.min(root.width * 0.55, sourceSize.width)
            height: width * sourceSize.height / sourceSize.width
            smooth: true

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { from: 1; to: 0.8; duration: 1400; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.8; to: 1; duration: 1400; easing.type: Easing.InOutSine }
            }
        }

        // Block cursor on the baseline, one glyph row tall, like an ANSI '▄▄▄'.
        Rectangle {
            width: wordmark.height / 6 * 1.4
            height: wordmark.height / 12
            y: wordmark.height * 5 / 6 - height
            color: "#fafafa"

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                PropertyAnimation { to: 0; duration: 0 }
                PauseAnimation { duration: 530 }
                PropertyAnimation { to: 1; duration: 0 }
                PauseAnimation { duration: 530 }
            }
        }
    }

    Column {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 40
        spacing: 4

        Repeater {
            model: root.shown
            Text {
                required property int index
                text: root.bootLines[index]
                color: text.indexOf("INFO") >= 0 ? "#a1a1aa" : "#71717a"
                font.family: "JetBrains Mono"
                font.pixelSize: 14
            }
        }
    }

    Text {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 40
        text: "HaltOS 1.2 (SIGKILL)"
        color: "#71717a"
        font.family: "JetBrains Mono"
        font.pixelSize: 14
    }

    // Faint CRT scanlines.
    Column {
        anchors.fill: parent
        Repeater {
            model: Math.ceil(root.height / 3)
            Rectangle { width: root.width; height: 1; color: "#000000"; opacity: 0.25 }
        }
        spacing: 2
    }
}
