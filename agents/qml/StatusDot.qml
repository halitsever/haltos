import QtQuick
import org.kde.kirigami as Kirigami

// Monochrome on purpose: shape tells the state apart, the theme has no accent colour.
Rectangle {
    property string group: "work"

    implicitWidth: 8
    implicitHeight: 8
    radius: 4
    color: group === "need" ? Kirigami.Theme.textColor : "transparent"
    border.width: group === "need" ? 0 : 1.5
    border.color: group === "work" ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor

    SequentialAnimation on opacity {
        running: group === "work"
        loops: Animation.Infinite
        onStopped: parent.opacity = 1
        NumberAnimation { to: 0.3; duration: 700 }
        NumberAnimation { to: 1; duration: 700 }
    }
}
