import json, os, sys, time, threading, subprocess, re
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QObject, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QPixmap, QIcon, QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFileDialog, QTextEdit, QFrame, QMessageBox,
    QComboBox, QSpinBox, QProgressBar, QScrollArea, QGridLayout, QCheckBox,
    QButtonGroup, QGraphicsOpacityEffect, QLineEdit
)

APP_NAME = 'Hn38videoAItool'
CREATOR = 'Hoainguyenstudio'
VERSION = '1.0.0'
ZALO = '0965.043.000'
ROOT = Path(__file__).resolve().parent.parent
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
DATA = ROOT / 'data'
PROFILES = ROOT / 'browser_profiles'
OUTPUT = ROOT / 'output'
LOGS = ROOT / 'logs'
ASSETS = ROOT / 'assets'
SETTINGS = DATA / 'settings.json'
for p in (DATA, PROFILES, OUTPUT, LOGS):
    p.mkdir(parents=True, exist_ok=True)
META_PROFILE = PROFILES / 'meta'
FLOW_PROFILE = PROFILES / 'flow'
META_PROFILE.mkdir(parents=True, exist_ok=True)
FLOW_PROFILE.mkdir(parents=True, exist_ok=True)
META_URL = 'https://www.meta.ai/'
FLOW_URL = 'https://labs.google/fx/tools/flow'

DEFAULT_SETTINGS = {
    'theme': 'Neon Dark',
    'animations': True,
    'animation_level': 'Vừa',
    'open_animation': True,
    'page_animation': False,
    'hover_animation': True,
    'upload_animation': True,
    'toast_animation': True,
    'neon_glow': True,
    'auto_download': True,
    'output_dir': str(OUTPUT),
}

THEMES = {
    'Neon Dark': {
        'bg': '#050b16', 'panel': '#091526', 'card': '#0c1b2e', 'card2': '#0a1728',
        'border': '#1d3858', 'text': '#edf5ff', 'muted': '#8ca4c1', 'primary': '#5d7cff',
        'primary2': '#9b5cff', 'accent': '#25d8ff', 'pink': '#ff4fc8', 'success': '#52e3a3',
        'danger': '#ff5c7a', 'warning': '#ffc857'
    },
    'Midnight Purple': {
        'bg': '#090611', 'panel': '#120b1e', 'card': '#1a1029', 'card2': '#160c24',
        'border': '#3a2356', 'text': '#f4edff', 'muted': '#b0a0c9', 'primary': '#9b5cff',
        'primary2': '#d35cff', 'accent': '#6f8cff', 'pink': '#ff5ccf', 'success': '#58e2a8',
        'danger': '#ff6387', 'warning': '#ffd166'
    },
    'Cyber Blue': {
        'bg': '#031019', 'panel': '#061924', 'card': '#092333', 'card2': '#071d2a',
        'border': '#12435e', 'text': '#e9fbff', 'muted': '#8fb4c7', 'primary': '#00a9ff',
        'primary2': '#3b6cff', 'accent': '#00e5ff', 'pink': '#00b7ff', 'success': '#48e5a2',
        'danger': '#ff5f76', 'warning': '#ffd166'
    },
    'Black & Red': {
        'bg': '#090909', 'panel': '#111111', 'card': '#181818', 'card2': '#141414',
        'border': '#3b2528', 'text': '#f5f5f5', 'muted': '#a7a7a7', 'primary': '#ff3b57',
        'primary2': '#ff6b35', 'accent': '#ff8a3d', 'pink': '#ff3b72', 'success': '#55df9a',
        'danger': '#ff3b57', 'warning': '#ffc857'
    },
    'Light': {
        'bg': '#f3f6fb', 'panel': '#ffffff', 'card': '#ffffff', 'card2': '#eef3f9',
        'border': '#d7e0ec', 'text': '#172033', 'muted': '#607089', 'primary': '#4f63e8',
        'primary2': '#7957d6', 'accent': '#078ecf', 'pink': '#d53a9d', 'success': '#13965f',
        'danger': '#d83a55', 'warning': '#b97800'
    },
}


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log_event(message, level='INFO'):
    line = f'[{now()}] [{level}] {message}'
    print(line, flush=True)
    try:
        with open(LOGS / 'app.log', 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def load_settings():
    data = DEFAULT_SETTINGS.copy()
    try:
        if SETTINGS.exists():
            data.update(json.loads(SETTINGS.read_text(encoding='utf-8')))
    except Exception as e:
        log_event(f'Không đọc được settings: {e}', 'WARN')
    return data


def save_settings(data):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def browser_path():
    bundled = ROOT / '_browsers'
    if bundled.exists():
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(bundled)


browser_path()


class WorkerSignals(QObject):
    status = Signal(str)
    error = Signal(str)
    done = Signal(str)
    login_state = Signal(str, bool)


class BrowserAutomation:
    """Real browser automation. Each provider has its own persistent profile."""
    def __init__(self, provider='meta', signals=None):
        self.provider = provider
        self.signals = signals or WorkerSignals()
        self._thread = None
        self._stop = threading.Event()
        self._pw = None
        self._context = None
        self._page = None

    def _import_pw(self):
        from playwright.sync_api import sync_playwright
        return sync_playwright

    def _profile_url(self):
        if self.provider == 'meta':
            return META_PROFILE, META_URL
        return FLOW_PROFILE, FLOW_URL

    def login(self):
        if self._thread and self._thread.is_alive():
            self.signals.status.emit(f'{self.provider.upper()} browser đang chạy.')
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._login_loop, daemon=True, name=f'{self.provider}-browser')
        self._thread.start()

    def _login_loop(self):
        profile, url = self._profile_url()
        try:
            sync_playwright = self._import_pw()
            with sync_playwright() as pw:
                self._pw = pw
                self.signals.status.emit(f'Đang mở trình duyệt {self.provider.upper()}...')
                self._context = self._launch_browser(pw, profile)
                self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
                self._page.set_default_timeout(7000)
                self.signals.status.emit(f'Đã mở browser {self.provider.upper()}, đang tải trang...')
                try:
                    self._page.goto(url, wait_until='commit', timeout=15000)
                    try:
                        self._page.wait_for_load_state('domcontentloaded', timeout=10000)
                    except Exception:
                        pass
                except Exception as e:
                    self.signals.status.emit(f'Browser đã mở nhưng trang chưa tải xong: {e}')
                self.signals.status.emit('🟡 Chờ bạn đăng nhập trong cửa sổ trình duyệt...')
                last_state = None
                started = time.time()
                while not self._stop.is_set() and self._context.pages:
                    state = self._detect_login_state(self._page)
                    if state != last_state:
                        last_state = state
                        if state == 'logged_in':
                            self.signals.login_state.emit(self.provider, True)
                            self.signals.status.emit(f'🟢 {self.provider.upper()} đã đăng nhập.')
                        elif state == 'login_required':
                            self.signals.login_state.emit(self.provider, False)
                            self.signals.status.emit('🟡 Chờ đăng nhập...')
                    if time.time() - started > 45 and state == 'load_error':
                        self.signals.status.emit('🔴 Trang chưa tải được sau 45 giây. Browser vẫn mở để bạn thử lại.')
                        started = time.time()
                    time.sleep(2)
                self.signals.status.emit('Browser đã đóng.')
        except Exception as e:
            log_event(f'{self.provider} login error: {e}', 'ERROR')
            self.signals.error.emit(str(e))
        finally:
            self._context = None
            self._page = None
            self._pw = None

    def _clear_stale_profile_locks(self, profile):
        # These profiles belong exclusively to Hn38videoAItool. Remove only stale
        # Chromium lock files before starting a new session; never touch the user's
        # normal Chrome profile.
        for name in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
            try:
                f = profile / name
                if f.exists() or f.is_symlink():
                    f.unlink()
            except Exception:
                pass

    def _launch_browser(self, pw, profile):
        # Prefer the user's installed Chrome/Edge. This keeps the EXE much smaller and
        # also gives the login page the same browser engine users already have installed.
        common = {
            'user_data_dir': str(profile),
            'headless': False,
            'viewport': {'width': 1400, 'height': 900},
            'accept_downloads': True,
            'timeout': 15000,
            'args': ['--disable-background-networking', '--disable-features=Translate,MediaRouter'],
        }
        errors = []
        self._clear_stale_profile_locks(profile)
        for channel in ('chrome', 'msedge'):
            try:
                return pw.chromium.launch_persistent_context(channel=channel, **common)
            except Exception as e:
                errors.append(f'{channel}: {e}')
        # Last resort: Playwright-managed Chromium if the portable build contains it.
        try:
            return pw.chromium.launch_persistent_context(**common)
        except Exception as e:
            errors.append(f'chromium: {e}')
            raise RuntimeError('Không mở được browser. Hãy cài Google Chrome hoặc Microsoft Edge rồi thử lại.\n' + '\n'.join(errors[-2:]))

    def _detect_login_state(self, page):
        try:
            url = (page.url or '').lower()
            if any(x in url for x in ('accounts.google.com', '/login', '/signin', '/auth')):
                return 'login_required'

            # Only inspect VISIBLE login controls. Searching the whole body is unreliable
            # because Meta/Google can mention "Log in" in footer/help text even after login.
            selectors = [
                'button:visible', 'a:visible',
                '[role="button"]:visible',
            ]
            for sel in selectors:
                loc = page.locator(sel)
                for i in range(min(loc.count(), 80)):
                    try:
                        txt = (loc.nth(i).inner_text(timeout=300) or '').strip().lower()
                        if re.fullmatch(r'(log in|login|sign in|đăng nhập)', txt):
                            return 'login_required'
                    except Exception:
                        pass

            body = page.locator('body').inner_text(timeout=1200).strip()
            if len(body) >= 80:
                return 'logged_in'
            return 'load_error'
        except Exception:
            return 'load_error'

    def stop(self):
        self._stop.set()
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass

    def _visible_prompt(self, page):
        for sel in ['textarea', 'textarea[placeholder]', '[contenteditable="true"]', 'input[type="text"]']:
            try:
                loc = page.locator(sel)
                for i in range(min(loc.count(), 10)):
                    el = loc.nth(i)
                    if el.is_visible() and el.is_editable():
                        return el
            except Exception:
                pass
        return None

    def _click_text(self, page, texts):
        for text in texts:
            for loc in [page.get_by_role('button', name=text, exact=False), page.get_by_text(text, exact=False)]:
                try:
                    if loc.count() and loc.first.is_visible():
                        loc.first.click(timeout=2500)
                        return True
                except Exception:
                    pass
        return False

    def _upload_images(self, page, images):
        if not images:
            return 0
        inputs = page.locator('input[type=file]')
        try:
            if inputs.count():
                inputs.last.set_input_files(images)
                return len(images)
        except Exception:
            pass
        return 0

    def generate_meta_video(self, prompt, images, output_dir):
        threading.Thread(target=self._generate_meta_video, args=(prompt, images, output_dir), daemon=True).start()

    def _generate_meta_video(self, prompt, images, output_dir):
        try:
            sync_playwright = self._import_pw()
            self.signals.status.emit('Đang mở phiên Meta AI...')
            with sync_playwright() as pw:
                context = self._launch_browser(pw, META_PROFILE)
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(8000)
                try:
                    page.goto(META_URL, wait_until='commit', timeout=15000)
                    try:
                        page.wait_for_load_state('domcontentloaded', timeout=10000)
                    except Exception:
                        pass
                except Exception as e:
                    raise RuntimeError(f'Meta AI không tải được: {e}')
                self.signals.status.emit('Đang kiểm tra phiên Meta AI...')
                state = self._detect_login_state(page)
                if state != 'logged_in':
                    raise RuntimeError('Phiên Meta AI chưa được xác nhận đăng nhập. Hãy đăng nhập trước.')
                self.signals.status.emit('Đang tìm giao diện tạo video...')
                self._click_text(page, ['Video', 'Create video', 'Tạo video', 'AI video', 'Vibes'])
                page.wait_for_timeout(1000)
                prompt_el = self._visible_prompt(page)
                if not prompt_el:
                    raise RuntimeError('Không tìm thấy ô prompt video. Tài khoản/khu vực có thể chưa có chức năng này hoặc giao diện đã thay đổi.')
                prompt_el.fill(prompt)
                if images and self._upload_images(page, images) != len(images):
                    raise RuntimeError('Không tìm thấy bộ phận upload ảnh của Meta AI.')
                self.signals.status.emit('Đang gửi yêu cầu tạo video...')
                if not self._click_text(page, ['Generate video', 'Create video', 'Generate', 'Create', 'Tạo', 'Send']):
                    prompt_el.press('Enter')
                self.signals.status.emit('Meta AI đang xử lý — chờ kết quả thật...')
                deadline = time.time() + 15 * 60
                video = None
                while time.time() < deadline:
                    page.wait_for_timeout(2500)
                    for sel in ['video', 'a[download]', 'a[href*=".mp4"]']:
                        try:
                            loc = page.locator(sel)
                            for i in range(loc.count()):
                                el = loc.nth(i)
                                if el.is_visible():
                                    video = el
                                    break
                            if video:
                                break
                        except Exception:
                            pass
                    if video:
                        break
                if not video:
                    raise RuntimeError('Meta AI chưa trả về video thật trong thời gian chờ. Không đánh dấu thành công.')
                output_dir.mkdir(parents=True, exist_ok=True)
                out = output_dir / f'meta_video_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
                saved = False
                try:
                    with page.expect_download(timeout=10000) as dl_info:
                        if not self._click_text(page, ['Download', 'Tải xuống']):
                            raise RuntimeError('Không tìm thấy nút tải xuống')
                    dl_info.value.save_as(str(out))
                    saved = True
                except Exception:
                    src = video.get_attribute('src')
                    if src:
                        resp = context.request.get(src, timeout=30000)
                        if resp.ok:
                            out.write_bytes(resp.body())
                            saved = True
                if not saved or not out.exists() or out.stat().st_size < 1024:
                    raise RuntimeError('Video được phát hiện nhưng không tải được file kết quả.')
                context.close()
                self.signals.done.emit(str(out))
                self.signals.status.emit(f'🟢 Đã tải video thật: {out.name}')
        except Exception as e:
            log_event(f'Meta video error: {e}', 'ERROR')
            self.signals.error.emit(str(e))


class FadePage(QWidget):
    def __init__(self, animations=True, level='Vừa'):
        super().__init__()
        self.animations = animations
        self.level = level

    def fade_in(self):
        # Full-page QGraphicsOpacityEffect forces Qt to render the entire page to
        # an off-screen surface on every frame. That makes navigation noticeably
        # laggy on Windows, especially on pages containing scroll areas/thumbnails.
        # Keep page transitions lightweight: briefly lift the page into view without
        # applying an expensive graphics effect. The global window-open animation is
        # still available separately.
        if not self.animations:
            return
        QTimer.singleShot(0, self.update)


class ImageThumb(QFrame):
    removed = Signal(object)
    def __init__(self, path, number, animations=True):
        super().__init__()
        self.path = path; self.animations = animations
        self.setObjectName('thumbCard')
        lay = QVBoxLayout(self); lay.setContentsMargins(7,7,7,7); lay.setSpacing(5)
        head = QHBoxLayout(); head.addWidget(QLabel(f'Ảnh {number}')); head.addStretch()
        rm = QPushButton('×'); rm.setFixedSize(26,26); rm.setObjectName('miniDanger'); rm.clicked.connect(lambda: self.removed.emit(self)); head.addWidget(rm); lay.addLayout(head)
        pic = QLabel(); pic.setFixedSize(150,100); pic.setAlignment(Qt.AlignCenter); pic.setObjectName('thumbImage')
        pix = QPixmap(path)
        if not pix.isNull(): pix = pix.scaled(pic.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pic.setPixmap(pix); lay.addWidget(pic)
        if animations:
            effect = QGraphicsOpacityEffect(self); self.setGraphicsEffect(effect)
            a = QPropertyAnimation(effect, b'opacity', self); a.setDuration(220); a.setStartValue(0); a.setEndValue(1); a.start(QPropertyAnimation.DeleteWhenStopped); self._a = a


class Toast(QLabel):
    def __init__(self, parent, text, kind='info'):
        super().__init__(parent)
        self.setText(text); self.setObjectName('toast'); self.adjustSize(); self.raise_()
        self.move(parent.width() - self.width() - 30, 25)
        QTimer.singleShot(2800, self.deleteLater)


class LoginPage(FadePage):
    def __init__(self, app):
        super().__init__(app.animations, app.settings['animation_level']); self.app = app
        lay = QVBoxLayout(self); lay.setSpacing(16)
        title = QLabel('🔐  ĐĂNG NHẬP'); title.setObjectName('pageTitle'); lay.addWidget(title)
        sub = QLabel('Mỗi dịch vụ dùng một browser profile riêng. Bạn tự đăng nhập trong cửa sổ browser.')
        sub.setObjectName('muted'); lay.addWidget(sub)
        self.cards = {}
        for provider, name, desc in [('meta','Meta AI','Session riêng cho Meta AI.'), ('flow','Google Flow','Session riêng cho Google Flow.')]:
            card = QFrame(); card.setObjectName('card'); c = QVBoxLayout(card)
            top = QHBoxLayout(); icon = QLabel('🤖' if provider=='meta' else '🎬'); icon.setStyleSheet('font-size:30px'); top.addWidget(icon)
            info = QVBoxLayout(); l=QLabel(name); l.setObjectName('cardTitle'); info.addWidget(l); d=QLabel(desc); d.setObjectName('muted'); info.addWidget(d); top.addLayout(info,1)
            status = QLabel('🔴 Chưa đăng nhập'); status.setObjectName('loginStatus'); top.addWidget(status); c.addLayout(top)
            buttons = QHBoxLayout(); b=QPushButton('🌐 Mở trình duyệt đăng nhập'); b.setObjectName('primary'); b.clicked.connect(lambda _,p=provider:self.app.start_login(p)); buttons.addWidget(b)
            check=QPushButton('🔄 Kiểm tra'); check.clicked.connect(lambda _,p=provider:self.app.check_login(p)); buttons.addWidget(check); c.addLayout(buttons)
            self.cards[provider] = status; lay.addWidget(card)
        lay.addStretch()

    def set_status(self, provider, ok, text=None):
        self.cards[provider].setText(('🟢 Đã đăng nhập' if ok else '🔴 Chưa đăng nhập') if not text else text)


class MetaVideoPage(FadePage):
    def __init__(self, app):
        super().__init__(app.animations, app.settings['animation_level']); self.app=app; self.images=[]
        outer=QVBoxLayout(self); outer.setContentsMargins(24,20,24,24); outer.setSpacing(14)
        title=QLabel('🤖  META AI  /  TẠO VIDEO'); title.setObjectName('pageTitle'); outer.addWidget(title)
        sub=QLabel('Tạo video bằng phiên Meta AI đã đăng nhập. Kết quả chỉ báo thành công khi nhận được file thật.'); sub.setObjectName('muted'); outer.addWidget(sub)
        row=QHBoxLayout(); left=QVBoxLayout(); right=QVBoxLayout(); row.addLayout(left,3); row.addLayout(right,2); outer.addLayout(row,1)
        card=QFrame(); card.setObjectName('card'); cl=QVBoxLayout(card)
        h=QHBoxLayout(); h.addWidget(QLabel('01  •  ẢNH ĐẦU VÀO')); h.addStretch(); add=QPushButton('+ Thêm ảnh'); add.clicked.connect(self.add_images); h.addWidget(add); cl.addLayout(h)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.thumbhost=QWidget(); self.thumbs=QGridLayout(self.thumbhost); self.thumbs.setAlignment(Qt.AlignLeft|Qt.AlignTop); self.scroll.setWidget(self.thumbhost); self.scroll.setMinimumHeight(175); cl.addWidget(self.scroll)
        hint=QLabel('Ảnh 1 • Ảnh 2 • Ảnh 3…  Thumbnail xuất hiện ngay sau khi chọn.'); hint.setObjectName('muted'); cl.addWidget(hint); left.addWidget(card)
        pc=QFrame(); pc.setObjectName('card'); pl=QVBoxLayout(pc); pl.addWidget(QLabel('02  •  PROMPT')); self.prompt=QTextEdit(); self.prompt.setPlaceholderText('Mô tả chuyển động, nhân vật, bối cảnh, camera...'); self.prompt.setMinimumHeight(170); pl.addWidget(self.prompt); left.addWidget(pc)
        opt=QFrame(); opt.setObjectName('card'); ol=QGridLayout(opt)
        for i,(label,widget) in enumerate([('Số lượng',QSpinBox()),('Tỷ lệ',QComboBox()),('Chất lượng',QComboBox())]):
            ol.addWidget(QLabel(label),0,i); ol.addWidget(widget,1,i)
        self.count=opt.findChildren(QSpinBox)[0]; self.count.setRange(1,10); self.ratio=opt.findChildren(QComboBox)[0]; self.ratio.addItems(['16:9 (Ngang)','9:16 (Dọc)','1:1']); self.quality=opt.findChildren(QComboBox)[1]; self.quality.addItems(['Tự động','HD']); left.addWidget(opt)
        state=QFrame(); state.setObjectName('card'); sl=QVBoxLayout(state); sl.addWidget(QLabel('03  •  TRẠNG THÁI')); self.status=QLabel('🟡 Chưa bắt đầu'); self.status.setObjectName('bigStatus'); sl.addWidget(self.status); self.progress=QProgressBar(); self.progress.setRange(0,0); self.progress.hide(); sl.addWidget(self.progress); right.addWidget(state)
        pv=QFrame(); pv.setObjectName('previewCard'); pvl=QVBoxLayout(pv); pvl.addWidget(QLabel('04  •  KẾT QUẢ')); self.preview=QLabel('Video kết quả sẽ xuất hiện ở đây'); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumHeight(300); self.preview.setObjectName('preview'); pvl.addWidget(self.preview,1); right.addWidget(pv,1)
        self.generate=QPushButton('✨  TẠO VIDEO'); self.generate.setObjectName('primaryBig'); self.generate.clicked.connect(self.generate_video); right.addWidget(self.generate)
        self.open_btn=QPushButton('📂 Mở thư mục output'); self.open_btn.clicked.connect(self.open_output); right.addWidget(self.open_btn)

    def add_images(self):
        files,_=QFileDialog.getOpenFileNames(self,'Chọn ảnh','',['Images (*.png *.jpg *.jpeg *.webp *.bmp)'])
        for f in files: self.add_one(f)

    def add_one(self,path):
        if path in self.images: return
        self.images.append(path); self.rebuild_thumbs()

    def rebuild_thumbs(self):
        while self.thumbs.count():
            item=self.thumbs.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        for i,p in enumerate(self.images,1):
            w=ImageThumb(p,i,self.app.animations); w.removed.connect(self.remove_thumb); self.thumbs.addWidget(w,(i-1)//3,(i-1)%3)

    def remove_thumb(self,w):
        if w.path in self.images: self.images.remove(w.path); self.rebuild_thumbs()

    def open_output(self):
        path=Path(self.app.settings.get('output_dir',str(OUTPUT))); path.mkdir(parents=True,exist_ok=True)
        if sys.platform=='win32': os.startfile(str(path))
        elif sys.platform=='darwin': subprocess.Popen(['open',str(path)])
        else: subprocess.Popen(['xdg-open',str(path)])

    def generate_video(self):
        prompt=self.prompt.toPlainText().strip()
        if not prompt: QMessageBox.warning(self,'Thiếu prompt','Hãy nhập prompt video.'); return
        if not self.app.meta_logged: QMessageBox.warning(self,'Chưa đăng nhập','Hãy vào Đăng nhập → Meta AI trước.'); return
        self.generate.setEnabled(False); self.progress.show(); self.status.setText('🟡 Đang xử lý trên Meta AI...')
        worker=BrowserAutomation('meta'); worker.signals.status.connect(self.status.setText); worker.signals.error.connect(self.on_error); worker.signals.done.connect(self.on_done); worker.generate_meta_video(prompt,self.images,Path(self.app.settings.get('output_dir',str(OUTPUT)))); self._worker=worker

    def on_error(self,e):
        self.progress.hide(); self.status.setText('🔴 '+e); self.generate.setEnabled(True); Toast(self,'Meta AI: '+e,'error')

    def on_done(self,path):
        self.progress.hide(); self.status.setText('🟢 Đã nhận video thật: '+Path(path).name); self.generate.setEnabled(True); self.preview.setText('🎬  '+Path(path).name+'\n\nFile đã lưu trong output.'); Toast(self,'Tạo video thành công')


class DashboardPage(FadePage):
    def __init__(self, app):
        super().__init__(app.animations, app.settings['animation_level'])
        lay=QVBoxLayout(self); lay.setContentsMargins(24,20,24,24); lay.setSpacing(16)
        t=QLabel('🏠  DASHBOARD'); t.setObjectName('pageTitle'); lay.addWidget(t)
        grid=QGridLayout(); lay.addLayout(grid)
        self.cards=[]
        for i,(title,value,desc) in enumerate([('Meta AI','🔴 Chưa đăng nhập','Browser profile riêng'),('Google Flow','🔴 Chưa đăng nhập','Browser profile riêng'),('Output','0','Video đã lưu'),('Animation','ON','Có thể đổi trong Cài đặt')]):
            c=QFrame(); c.setObjectName('statCard'); v=QVBoxLayout(c); a=QLabel(title); a.setObjectName('muted'); v.addWidget(a); b=QLabel(value); b.setObjectName('statValue'); v.addWidget(b); d=QLabel(desc); d.setObjectName('muted'); v.addWidget(d); grid.addWidget(c,i//2,i%2); self.cards.append(b)
        info=QFrame(); info.setObjectName('card'); il=QVBoxLayout(info); il.addWidget(QLabel('Hn38videoAItool')); il.addWidget(QLabel('Meta AI và Google Flow dùng profile riêng. Không tự lấy cookie từ Chrome chính.')); il.addWidget(QLabel(f'Version {VERSION} • {CREATOR} • Zalo {ZALO}')); lay.addWidget(info); lay.addStretch()

    def refresh(self, meta, flow, animations):
        self.cards[0].setText('🟢 Đã đăng nhập' if meta else '🔴 Chưa đăng nhập'); self.cards[1].setText('🟢 Đã đăng nhập' if flow else '🔴 Chưa đăng nhập'); self.cards[3].setText('ON' if animations else 'OFF')


class SettingsPage(FadePage):
    changed = Signal()
    def __init__(self, app):
        super().__init__(app.animations, app.settings['animation_level']); self.app=app
        lay=QVBoxLayout(self); lay.setContentsMargins(24,20,24,24); lay.setSpacing(14)
        t=QLabel('⚙️  CÀI ĐẶT'); t.setObjectName('pageTitle'); lay.addWidget(t)
        c=QFrame(); c.setObjectName('card'); g=QGridLayout(c)
        g.addWidget(QLabel('Theme'),0,0); self.theme=QComboBox(); self.theme.addItems(THEMES.keys()); self.theme.setCurrentText(app.settings['theme']); g.addWidget(self.theme,0,1)
        self.anim=QCheckBox('Bật animation giao diện'); self.anim.setChecked(app.settings['animations']); g.addWidget(self.anim,1,0,1,2)
        g.addWidget(QLabel('Mức animation'),2,0); self.level=QComboBox(); self.level.addItems(['Nhẹ','Vừa','Mạnh']); self.level.setCurrentText(app.settings['animation_level']); g.addWidget(self.level,2,1)
        self.neon=QCheckBox('Glow / Neon effects'); self.neon.setChecked(app.settings['neon_glow']); g.addWidget(self.neon,3,0,1,2)
        self.open_anim=QCheckBox('Animation khi mở ứng dụng'); self.open_anim.setChecked(app.settings['open_animation']); g.addWidget(self.open_anim,4,0,1,2)
        self.page_anim=QCheckBox('Animation chuyển trang'); self.page_anim.setChecked(app.settings['page_animation']); g.addWidget(self.page_anim,5,0,1,2)
        self.upload_anim=QCheckBox('Animation upload ảnh'); self.upload_anim.setChecked(app.settings['upload_animation']); g.addWidget(self.upload_anim,6,0,1,2)
        lay.addWidget(c)
        out=QFrame(); out.setObjectName('card'); og=QGridLayout(out); og.addWidget(QLabel('Thư mục output'),0,0); self.out=QLineEdit(app.settings.get('output_dir',str(OUTPUT))); og.addWidget(self.out,0,1); b=QPushButton('Chọn'); b.clicked.connect(self.choose_output); og.addWidget(b,0,2); lay.addWidget(out)
        save=QPushButton('💾  LƯU & ÁP DỤNG'); save.setObjectName('primary'); save.clicked.connect(self.apply); lay.addWidget(save); lay.addStretch()

    def choose_output(self):
        d=QFileDialog.getExistingDirectory(self,'Chọn thư mục output',self.out.text());
        if d: self.out.setText(d)

    def apply(self):
        s=self.app.settings; s.update({'theme':self.theme.currentText(),'animations':self.anim.isChecked(),'animation_level':self.level.currentText(),'neon_glow':self.neon.isChecked(),'open_animation':self.open_anim.isChecked(),'page_animation':self.page_anim.isChecked(),'upload_animation':self.upload_anim.isChecked(),'output_dir':self.out.text()})
        save_settings(s); self.app.apply_theme(); self.app.rebuild_pages(); Toast(self.app,'Đã lưu cài đặt')


class PlaceholderPage(FadePage):
    def __init__(self, app, title, desc):
        super().__init__(app.animations, app.settings['animation_level']); lay=QVBoxLayout(self); lay.setContentsMargins(24,20,24,24); t=QLabel(title); t.setObjectName('pageTitle'); lay.addWidget(t); d=QLabel(desc); d.setObjectName('muted'); lay.addWidget(d); lay.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.settings=load_settings(); self.animations=self.settings['animations']; self.meta_logged=False; self.flow_logged=False; self.login_workers={}
        self.setWindowTitle(APP_NAME); self.resize(1500,930)
        ico=ASSETS/'hn38.ico'; self.setWindowIcon(QIcon(str(ico)) if ico.exists() else QIcon())
        self.stack=QStackedWidget(); self.buttons=[]
        root=QWidget(); self.setCentralWidget(root); main=QHBoxLayout(root); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        side=QFrame(); side.setObjectName('sidebar'); side.setFixedWidth(245); sl=QVBoxLayout(side); sl.setContentsMargins(18,20,18,18)
        logo=QLabel('Hn38'); logo.setObjectName('logo'); logo.setAlignment(Qt.AlignCenter); sl.addWidget(logo); brand=QLabel(APP_NAME); brand.setAlignment(Qt.AlignCenter); brand.setObjectName('brand'); sl.addWidget(brand); sl.addSpacing(18)
        self.nav=QVBoxLayout(); sl.addLayout(self.nav); sl.addStretch(); foot=QLabel(f'Version {VERSION}\n{CREATOR}\nZalo: {ZALO}'); foot.setObjectName('muted'); sl.addWidget(foot); main.addWidget(side); main.addWidget(self.stack,1)
        self.build_nav(); self.apply_theme(); self.show_page(0)
        if self.settings['open_animation'] and self.animations: QTimer.singleShot(80,self.animate_window)

    def build_nav(self):
        while self.nav.count():
            item=self.nav.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        self.buttons=[]
        groups=[('WORKSPACE',[('🏠','Dashboard'),('🔐','Đăng nhập')]),('GOOGLE FLOW',[('🎬','FLOW'),('📋','Queue / Kết quả')]),('META AI',[('🖼️','Tạo Ảnh'),('🎬','Tạo Video')]),('SYSTEM',[('📋','Log chi tiết'),('⚙️','Cài đặt')])]
        self.page_defs=[]
        for group,items in groups:
            h=QLabel(group); h.setObjectName('navGroup'); self.nav.addWidget(h)
            for icon,name in items:
                b=QPushButton(f'{icon}  {name}'); b.setCheckable(True); b.clicked.connect(lambda _,idx=len(self.page_defs):self.show_page(idx)); self.nav.addWidget(b); self.buttons.append(b); self.page_defs.append((name,b))
        # stack pages correspond exactly to page_defs
        while self.stack.count():
            w=self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.pages=[]
        for name,_ in self.page_defs:
            if name=='Dashboard': p=DashboardPage(self)
            elif name=='Đăng nhập': p=LoginPage(self)
            elif name=='Tạo Video': p=MetaVideoPage(self)
            elif name=='Cài đặt': p=SettingsPage(self)
            else: p=PlaceholderPage(self,name,'Khu vực này đã được chuẩn bị để tích hợp tác vụ thật, queue và log chi tiết.')
            self.stack.addWidget(p); self.pages.append(p)
        self.login_page=self.pages[1]; self.video_page=self.pages[5]; self.dashboard=self.pages[0]

    def rebuild_pages(self):
        current=self.stack.currentIndex(); self.build_nav(); self.show_page(min(current,self.stack.count()-1))

    def show_page(self,index):
        if index<0 or index>=self.stack.count(): return
        # Navigation must stay synchronous and cheap. Pages are created once in
        # build_nav(), then simply switched here; no page reconstruction and no
        # full-page opacity animation on every click.
        if self.stack.currentIndex() != index:
            self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.buttons):
            b.setChecked(i == index)
        if hasattr(self.dashboard,'refresh'):
            self.dashboard.refresh(self.meta_logged,self.flow_logged,self.animations)

    def start_login(self,provider):
        worker=self.login_workers.get(provider)
        if worker and worker._thread and worker._thread.is_alive():
            Toast(self,'Browser đang mở'); return
        worker=BrowserAutomation(provider); self.login_workers[provider]=worker
        worker.signals.status.connect(self.on_browser_status); worker.signals.error.connect(lambda e:self.browser_error(e)); worker.signals.login_state.connect(self.on_login_state); worker.login()

    def check_login(self,provider):
        # Reuse persistent profile by opening a short-lived browser only when needed.
        self.start_login(provider)

    def on_browser_status(self,s): self.statusBar().showMessage(s,12000)

    def on_login_state(self,provider,ok):
        if provider=='meta': self.meta_logged=ok
        else: self.flow_logged=ok
        self.login_page.set_status(provider,ok)
        if hasattr(self.dashboard,'refresh'): self.dashboard.refresh(self.meta_logged,self.flow_logged,self.animations)
        Toast(self, f'{provider.upper()}: '+('Đã đăng nhập' if ok else 'Chưa đăng nhập'))

    def browser_error(self,e): QMessageBox.critical(self,'Browser / Đăng nhập',e)

    def meta_ready(self): return self.meta_logged

    def animate_window(self):
        effect=QGraphicsOpacityEffect(self); self.setGraphicsEffect(effect); a=QPropertyAnimation(effect,b'opacity',self); a.setDuration(420); a.setStartValue(0); a.setEndValue(1); a.setEasingCurve(QEasingCurve.OutCubic); self._window_anim=a; a.start(QPropertyAnimation.DeleteWhenStopped)

    def apply_theme(self):
        t=THEMES.get(self.settings['theme'],THEMES['Neon Dark']); glow=t['primary'] if self.settings.get('neon_glow',True) else t['border']
        self.setStyleSheet(f'''
        QWidget{{background:{t['bg']};color:{t['text']};font-family:'Segoe UI';font-size:13px}}
        QMainWindow{{background:{t['bg']}}}
        #sidebar{{background:{t['panel']};border-right:1px solid {t['border']}}}
        #logo{{font-size:48px;font-weight:900;font-style:italic;color:{t['primary']}}}
        #brand{{font-size:12px;font-weight:800;color:{t['muted']}}}
        #navGroup{{color:{t['muted']};font-size:10px;font-weight:800;letter-spacing:1.5px;padding:12px 7px 6px}}
        QPushButton{{background:{t['card2']};border:1px solid {t['border']};border-radius:10px;padding:10px 12px;color:{t['text']};text-align:left}}
        QPushButton:hover{{background:{t['card']};border-color:{glow}}}
        QPushButton:checked{{background:{t['card']};border-color:{t['primary']};color:{t['text']}}}
        #primary,#primaryBig{{background:{t['primary']};border:0;color:white;font-weight:800}}
        #primaryBig{{font-size:15px;padding:15px;border-radius:12px}}
        #card,#statCard,#previewCard{{background:{t['card']};border:1px solid {t['border']};border-radius:14px}}
        #statCard{{padding:10px}}
        #cardTitle{{font-size:18px;font-weight:800}}
        #pageTitle{{font-size:26px;font-weight:900;padding:4px}}
        #muted{{color:{t['muted']}}}
        #status,#loginStatus,#bigStatus{{color:{t['success']};font-weight:800}}
        #bigStatus{{font-size:15px}}
        #statValue{{font-size:25px;font-weight:900;color:{t['accent']}}}
        #preview,#thumbImage{{background:{t['card2']};border:1px dashed {t['border']};border-radius:10px;color:{t['muted']}}}
        #thumbCard{{background:{t['card2']};border:1px solid {t['border']};border-radius:12px}}
        #miniDanger{{padding:0;border-radius:7px;color:{t['danger']}}}
        QTextEdit,QComboBox,QSpinBox,QLineEdit{{background:{t['card2']};border:1px solid {t['border']};border-radius:9px;padding:9px;color:{t['text']}}}
        QScrollArea{{border:0;background:transparent}}
        QProgressBar{{background:{t['card2']};border:0;border-radius:7px;height:10px}} QProgressBar::chunk{{background:{t['primary']};border-radius:7px}}
        QCheckBox{{spacing:8px}}
        #toast{{background:{t['card']};border:1px solid {t['primary']};border-radius:10px;padding:10px 14px;font-weight:700}}
        ''')


def main():
    app=QApplication(sys.argv); app.setStyle('Fusion'); win=MainWindow(); win.show(); sys.exit(app.exec())

if __name__=='__main__': main()
