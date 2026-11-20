import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// The one style for primary actions. The KDE style ignores `highlighted`, so it is drawn here.
QQC2.AbstractButton {
    id: button

    property bool primary: true

    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    implicitHeight: label.implicitHeight + Kirigami.Units.smallSpacing * 3
    implicitWidth: label.implicitWidth + Kirigami.Units.smallSpacing * 6

    background: Rectangle {
        radius: 6
        color: button.primary ? (button.down ? Qt.darker(Ansi.accent, 1.2) : button.hovered ? Qt.lighter(Ansi.accent, 1.12) : Ansi.accent)
                              : (button.hovered ? Ansi.surface : "transparent")
        border.width: button.primary ? 0 : 1
        border.color: Ansi.rule
    }

    contentItem: QQC2.Label {
        id: label
        text: button.text
        color: Ansi.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
