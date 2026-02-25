import os
import sys
import re

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QCheckBox,
    QComboBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QProgressBar
)

from core.i18n import load_lang
from core.env_setup import ensure_pip_packages
from core.pdf_extract import extract_folder_hits
from core.exporter import export_txt, export_word, export_excel


# ----------------------------
# Worker signals
# ----------------------------
class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)   # 0-100
    status = Signal(str)     # 状态文字


class ExtractWorker(QRunnable):
    def __init__(self, folder, keywords, use_regex, en_boundary, dedup):
        super().__init__()
        self.folder = folder
        self.keywords = keywords
        self.use_regex = use_regex
        self.en_boundary = en_boundary
        self.dedup = dedup
        self.signals = WorkerSignals()

    def _count_pdfs(self, folder: str) -> int:
        try:
            return sum(
                1 for name in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, name)) and name.lower().endswith(".pdf")
            )
        except Exception:
            return 0

    def run(self):
        try:
            # Stage 1: scan
            self.signals.status.emit("Scanning PDF files...")
            self.signals.progress.emit(0)

            total = self._count_pdfs(self.folder)
            self.signals.status.emit(f"Found {total} PDF(s). Preparing extraction...")
            self.signals.progress.emit(5)

            if total == 0:
                self.signals.result.emit([])
                self.signals.progress.emit(100)
                return

            # Stage 2: run extraction (single call, reliable)
            self.signals.status.emit("Extracting evidence... (this may take a while)")
            self.signals.progress.emit(10)

            rows = extract_folder_hits(
                self.folder,
                self.keywords,
                self.use_regex,
                self.en_boundary,
                self.dedup
            )

            # Stage 3: done
            self.signals.status.emit("Completed.")
            self.signals.progress.emit(100)
            self.signals.result.emit(rows)

        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# ----------------------------
# App
# ----------------------------
class App(QWidget):
    def __init__(self):
        super().__init__()

        self.threadpool = QThreadPool.globalInstance()
        self.lang_code = "zh"
        self.t = load_lang(self.lang_code)

        self.rows = []
        self.out_dir = ""

        self._bootstrap_environment()
        self._build_ui()
        self._apply_i18n()

    def _bootstrap_environment(self):
        missing = ensure_pip_packages()
        if missing:
            QMessageBox.warning(
                self, "Warning",
                f"Some Python packages may be missing: {missing}\n"
                f"Please run pip install -r requirements.txt"
            )

    def _build_ui(self):
        layout = QVBoxLayout()

        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        layout.addWidget(self.progressBar)

        # language switch
        top = QHBoxLayout()
        self.lbl_lang = QLabel()
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem("中文", "zh")
        self.cmb_lang.addItem("English", "en")
        self.cmb_lang.addItem("한국어", "ko")
        self.cmb_lang.currentIndexChanged.connect(self.on_lang_change)
        top.addWidget(self.lbl_lang)
        top.addWidget(self.cmb_lang)
        top.addStretch(1)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---- Tab: Extract ----
        self.tab_extract = QWidget()
        ex_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.lbl_pdf_folder = QLabel()
        self.ed_pdf_folder = QLineEdit()
        self.btn_pdf_folder = QPushButton()
        self.btn_pdf_folder.clicked.connect(self.choose_pdf_folder)
        row1.addWidget(self.lbl_pdf_folder)
        row1.addWidget(self.ed_pdf_folder)
        row1.addWidget(self.btn_pdf_folder)
        ex_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.lbl_out_folder = QLabel()
        self.ed_out_folder = QLineEdit()
        self.btn_out_folder = QPushButton()
        self.btn_out_folder.clicked.connect(self.choose_out_folder)
        row2.addWidget(self.lbl_out_folder)
        row2.addWidget(self.ed_out_folder)
        row2.addWidget(self.btn_out_folder)
        ex_layout.addLayout(row2)

        self.lbl_keywords = QLabel()
        self.ed_keywords = QLineEdit()
        ex_layout.addWidget(self.lbl_keywords)
        ex_layout.addWidget(self.ed_keywords)

        self.cb_regex = QCheckBox()
        self.cb_boundary = QCheckBox()
        self.cb_dedup = QCheckBox()
        self.cb_dedup.setChecked(True)

        ex_layout.addWidget(self.cb_regex)
        ex_layout.addWidget(self.cb_boundary)
        ex_layout.addWidget(self.cb_dedup)

        self.btn_run_extract = QPushButton()
        self.btn_run_extract.clicked.connect(self.run_extract)
        ex_layout.addWidget(self.btn_run_extract)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["file", "page", "keyword", "sentence"])
        self.table.horizontalHeader().setStretchLastSection(True)
        ex_layout.addWidget(self.table)

        ex_btns = QHBoxLayout()
        self.btn_export_txt = QPushButton()
        self.btn_export_word = QPushButton()
        self.btn_export_excel = QPushButton()

        self.btn_export_txt.clicked.connect(self.do_export_txt)
        self.btn_export_word.clicked.connect(self.do_export_word)
        self.btn_export_excel.clicked.connect(self.do_export_excel)

        ex_btns.addWidget(self.btn_export_txt)
        ex_btns.addWidget(self.btn_export_word)
        ex_btns.addWidget(self.btn_export_excel)
        ex_btns.addStretch(1)
        ex_layout.addLayout(ex_btns)

        self.lbl_status = QLabel()
        ex_layout.addWidget(self.lbl_status)

        self.tab_extract.setLayout(ex_layout)
        self.tabs.addTab(self.tab_extract, "Extract")

        self.setLayout(layout)

    def _apply_i18n(self):
        self.t = load_lang(self.lang_code)
        self.setWindowTitle(self.t["title"])

        self.lbl_lang.setText(self.t["lang"])
        self.tabs.setTabText(0, self.t["tab_extract"])

        self.lbl_pdf_folder.setText(self.t["pdf_folder"])
        self.lbl_out_folder.setText(self.t["out_folder"])
        self.btn_pdf_folder.setText(self.t["choose"])
        self.btn_out_folder.setText(self.t["choose"])

        self.lbl_keywords.setText(self.t["keywords"])
        self.cb_regex.setText(self.t["use_regex"])
        self.cb_boundary.setText(self.t["en_boundary"])
        self.cb_dedup.setText(self.t["dedup"])

        self.btn_run_extract.setText(self.t["run_extract"])
        self.btn_export_txt.setText(self.t["export_txt"])
        self.btn_export_word.setText(self.t["export_word"])
        self.btn_export_excel.setText(self.t["export_excel"])

        self.lbl_status.setText(self.t["status_ready"])

    def on_lang_change(self):
        self.lang_code = self.cmb_lang.currentData()
        self._apply_i18n()

    # ---------- File pickers ----------
    def choose_pdf_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.t["pdf_folder"])
        if path:
            self.ed_pdf_folder.setText(path)

    def choose_out_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.t["out_folder"])
        if path:
            self.ed_out_folder.setText(path)
            self.out_dir = path

    # ---------- Extraction ----------
    def run_extract(self):
        folder = self.ed_pdf_folder.text().strip()
        out = self.ed_out_folder.text().strip()

        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Error", "Invalid PDF folder.")
            return
        if not out or not os.path.isdir(out):
            QMessageBox.warning(self, "Error", "Invalid output folder.")
            return

        self.out_dir = out

        keywords = [k.strip() for k in re.split(r"[，,]", self.ed_keywords.text()) if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "Error", "Please input keywords.")
            return

        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)

        self.lbl_status.setText(self.t["status_running"])
        self.btn_run_extract.setEnabled(False)

        worker = ExtractWorker(
            folder=folder,
            keywords=keywords,
            use_regex=self.cb_regex.isChecked(),
            en_boundary=self.cb_boundary.isChecked(),
            dedup=self.cb_dedup.isChecked()
        )

        worker.signals.progress.connect(self.on_extract_progress)
        worker.signals.status.connect(self.on_extract_status)
        worker.signals.result.connect(self.on_extract_result)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_extract_finished)

        self.threadpool.start(worker)

    def on_extract_progress(self, val: int):
        if val is None:
            return
        self.progressBar.setValue(int(val))

    def on_extract_status(self, msg: str):
        if msg:
            self.lbl_status.setText(msg)

    def on_extract_result(self, rows):
        self.rows = rows

        # 显示全部（注意：非常多时会卡UI）
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get("file", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get("page", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get("keyword", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(r.get("sentence", ""))))

    def on_extract_finished(self):
        self.btn_run_extract.setEnabled(True)
        if self.progressBar.value() != 100:
            self.progressBar.setValue(100)
        self.lbl_status.setText(f"{self.t['status_done']}: {len(self.rows)} hits")

    # ---------- Export ----------
    def do_export_txt(self):
        if self.rows:
            export_txt(self.rows, os.path.join(self.out_dir, "results.txt"))

    def do_export_word(self):
        if self.rows:
            export_word(self.rows, os.path.join(self.out_dir, "results.docx"))

    def do_export_excel(self):
        if self.rows:
            export_excel(self.rows, os.path.join(self.out_dir, "results.xlsx"))

    def on_worker_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        self.btn_run_extract.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.resize(980, 720)
    w.show()
    sys.exit(app.exec())