from PyQt5.QtCore import QThread, pyqtSignal

class DownloadThread(QThread):
    """
    UI 线程封装：调用后端 Updater.download，向前端发射进度与完成信号。
    """
    progress = pyqtSignal(int)               # 0-100
    finished = pyqtSignal(bool, str)         # success, error_msg

    def __init__(self, updater, save_path, parent=None):
        super().__init__(parent)
        self.updater = updater
        self.save_path = save_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _canceled(self):
        return self._cancel

    def run(self):
        try:
            ok, msg = self.updater.download(
                save_path=self.save_path,
                progress_cb=self.progress.emit,
                cancel_flag=self._canceled
            )
            self.finished.emit(ok, msg)
        except Exception as e:
            self.finished.emit(False, str(e))
            
