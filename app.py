from PySide6.QtWidgets import *
import sys, os, io, time

# ===== 方法一依赖 =====
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter

# ===== 方法二三依赖 =====
import pymupdf as pm
import cv2
import numpy as np
from PIL import Image


# ================= 方法一：遮挡区域 =================
def fast_clean(input_pdf, output_pdf):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        packet = io.BytesIO()
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        c = canvas.Canvas(packet, pagesize=(width, height))
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, width, 60, fill=1, stroke=0)
        c.save()

        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)


# ================= 方法二：快速整页淡化 =================
def morph_clean(input_pdf, output_pdf):
    temp_dir = "tmp_pages"
    os.makedirs(temp_dir, exist_ok=True)

    doc = pm.open(input_pdf)
    imgs = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=180)
        p = f"{temp_dir}/p{i}.png"
        pix.save(p)
        imgs.append(p)

    doc.close()

    def remove(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bg = cv2.GaussianBlur(gray, (0,0), 60)
        norm = cv2.divide(gray, bg, scale=255)
        clahe = cv2.createCLAHE(2.5,(8,8))
        return clahe.apply(norm)

    first = Image.open(imgs[0])
    w,h = first.size
    c = canvas.Canvas(output_pdf, pagesize=(w,h))

    for p in imgs:
        img = cv2.imread(p)
        clean = remove(img)
        out = p.replace(".png","_c.png")
        cv2.imwrite(out, clean)
        c.drawImage(out,0,0,w,h)
        c.showPage()

    c.save()


# ================= 方法三：FFT终极干净 =================
def fft_clean(input_pdf, output_pdf):
    temp_dir = "tmp_pages"
    os.makedirs(temp_dir, exist_ok=True)

    dpi = 180
    cut = 22

    doc = pm.open(input_pdf)
    imgs = []

    for i,page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        p = f"{temp_dir}/p{i}.png"
        pix.save(p)
        imgs.append(p)

    doc.close()

    def remove_fft(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)

        r,c = gray.shape
        cr,cc = r//2,c//2

        mask = np.ones((r,c),np.uint8)
        mask[cr-cut:cr+cut, cc-cut:cc+cut] = 0

        fshift *= mask

        back = np.fft.ifftshift(fshift)
        imgb = np.abs(np.fft.ifft2(back))

        imgb = cv2.normalize(imgb,None,0,255,cv2.NORM_MINMAX).astype(np.uint8)
        imgb = cv2.bitwise_not(imgb)

        return cv2.adaptiveThreshold(
            imgb,255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,8
        )

    first = Image.open(imgs[0])
    w,h = first.size
    c = canvas.Canvas(output_pdf, pagesize=(w,h))

    for p in imgs:
        img = cv2.imread(p)
        clean = remove_fft(img)
        out = p.replace(".png","_c.png")
        cv2.imwrite(out, clean)
        c.drawImage(out,0,0,w,h)
        c.showPage()

    c.save()


# ================= 软件界面 =================
class PDFTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF去水印软件")

        self.btn_open = QPushButton("选择PDF")
        self.label = QLabel("未选择文件")

        self.combo = QComboBox()
        self.combo.addItems(["方法一：区域遮挡", "方法二：快速淡化", "方法三：终极干净"])

        self.btn_run = QPushButton("开始处理")
        self.progress = QProgressBar()

        layout = QVBoxLayout()
        layout.addWidget(self.btn_open)
        layout.addWidget(self.label)
        layout.addWidget(self.combo)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.progress)
        self.setLayout(layout)

        self.btn_open.clicked.connect(self.open_pdf)
        self.btn_run.clicked.connect(self.run)

        self.pdf_path = None

    def open_pdf(self):
        path,_ = QFileDialog.getOpenFileName(self,"选择PDF","","PDF Files (*.pdf)")
        if path:
            self.pdf_path = path
            self.label.setText(path)

    def run(self):
        if not self.pdf_path:
            QMessageBox.warning(self,"提示","请先选择PDF")
            return

        out = os.path.join(os.path.dirname(self.pdf_path),"output_clean.pdf")

        mode = self.combo.currentText()
        self.progress.setValue(20)

        if "方法一" in mode:
            fast_clean(self.pdf_path,out)
        elif "方法二" in mode:
            morph_clean(self.pdf_path,out)
        else:
            fft_clean(self.pdf_path,out)

        self.progress.setValue(100)
        QMessageBox.information(self,"完成",f"处理完成！\n输出文件：\n{out}")


# ================= 启动 =================
app = QApplication(sys.argv)
w = PDFTool()
w.resize(420,260)
w.show()
sys.exit(app.exec())