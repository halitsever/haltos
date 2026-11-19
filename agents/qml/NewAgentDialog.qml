import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialog

    required property QtObject controller
    readonly property bool ready: dir.editText.trim() !== "" && prompt.text.trim() !== ""

    title: "New agent"
    padding: Kirigami.Units.largeSpacing
    preferredWidth: Kirigami.Units.gridUnit * 32
    standardButtons: Kirigami.Dialog.NoButton

    customFooterActions: [
        Kirigami.Action {
            text: "Start"
            icon.name: "media-playback-start"
            enabled: dialog.ready
            onTriggered: dialog.launch()
        },
        Kirigami.Action {
            text: "Cancel"
            icon.name: "dialog-cancel"
            onTriggered: dialog.close()
        }
    ]

    function launch() {
        if (!ready)
            return
        controller.newAgent(dir.editText, name.text, model.currentIndex === 0 ? "" : model.currentText,
                            worktree.checked, prompt.text)
        close()
    }

    onOpened: {
        controller.loadRecentDirs()
        // The combo only fills its text after the new model lands.
        Qt.callLater(() => worktree.checked = controller.isGitRepo(dir.editText))
        name.clear()
        prompt.clear()
        prompt.forceActiveFocus()
    }

    // The task and the folder are all most people need; the rest waits behind "More options".
    Kirigami.FormLayout {
        QQC2.TextArea {
            id: prompt
            Kirigami.FormData.label: "Task:"
            Layout.fillWidth: true
            implicitHeight: Kirigami.Units.gridUnit * 6
            wrapMode: TextEdit.Wrap
            placeholderText: "What should it do? Ctrl+Enter starts it."
            Keys.onReturnPressed: event => {
                if (event.modifiers & Qt.ControlModifier)
                    dialog.launch()
                else
                    event.accepted = false
            }
        }
        RowLayout {
            Kirigami.FormData.label: "Folder:"
            Layout.fillWidth: true
            QQC2.ComboBox {
                id: dir
                Layout.fillWidth: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 18
                editable: true
                model: dialog.controller.recentDirs
                onEditTextChanged: worktree.checked = dialog.controller.isGitRepo(editText)
            }
            QQC2.Button {
                icon.name: "document-open-folder"
                QQC2.ToolTip.text: "Pick a folder"
                QQC2.ToolTip.visible: hovered
                onClicked: dialog.folderPicker.createObject(dialog).open()
            }
        }
        QQC2.CheckBox {
            id: more
            text: "More options"
        }
        QQC2.TextField {
            id: name
            visible: more.checked
            Kirigami.FormData.label: "Name:"
            Layout.fillWidth: true
            placeholderText: "automatic"
        }
        QQC2.ComboBox {
            id: model
            visible: more.checked
            Kirigami.FormData.label: "Model:"
            model: ["default", "opus", "sonnet", "haiku"]
        }
        QQC2.Switch {
            id: worktree
            visible: more.checked
            Kirigami.FormData.label: "Worktree:"
            text: "Run in its own git worktree"
        }
    }

    // Created on demand: a second child would stop the dialog's ScrollView from sizing to the form.
    readonly property Component folderPicker: Component {
        FolderDialog {
            onAccepted: dir.editText = decodeURIComponent(selectedFolder.toString().replace("file://", ""))
        }
    }
}
