import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialog

    required property QtObject controller
    readonly property bool ready: dir.editText.trim() !== "" && prompt.text.trim() !== ""

    title: "Yeni ajan"
    padding: Kirigami.Units.largeSpacing
    preferredWidth: Kirigami.Units.gridUnit * 32
    standardButtons: Kirigami.Dialog.NoButton

    customFooterActions: [
        Kirigami.Action {
            text: "Başlat"
            icon.name: "media-playback-start"
            enabled: dialog.ready
            onTriggered: dialog.launch()
        },
        Kirigami.Action {
            text: "İptal"
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

    Kirigami.FormLayout {
        RowLayout {
            Kirigami.FormData.label: "Klasör:"
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
                QQC2.ToolTip.text: "Klasör seç"
                QQC2.ToolTip.visible: hovered
                onClicked: dialog.folderPicker.createObject(dialog).open()
            }
        }
        QQC2.TextField {
            id: name
            Kirigami.FormData.label: "Ad:"
            Layout.fillWidth: true
            placeholderText: "otomatik"
        }
        QQC2.ComboBox {
            id: model
            Kirigami.FormData.label: "Model:"
            model: ["varsayılan", "opus", "sonnet", "haiku"]
        }
        QQC2.Switch {
            id: worktree
            Kirigami.FormData.label: "Worktree:"
            text: "Ayrı bir git worktree'de çalışsın"
        }
        QQC2.TextArea {
            id: prompt
            Kirigami.FormData.label: "Görev:"
            Layout.fillWidth: true
            implicitHeight: Kirigami.Units.gridUnit * 6
            wrapMode: TextEdit.Wrap
            placeholderText: "Ne yapsın? Ctrl+Enter başlatır."
            Keys.onReturnPressed: event => {
                if (event.modifiers & Qt.ControlModifier)
                    dialog.launch()
                else
                    event.accepted = false
            }
        }
    }

    // Created on demand: a second child would stop the dialog's ScrollView from sizing to the form.
    readonly property Component folderPicker: Component {
        FolderDialog {
            onAccepted: dir.editText = decodeURIComponent(selectedFolder.toString().replace("file://", ""))
        }
    }
}
