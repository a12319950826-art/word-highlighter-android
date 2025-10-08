"""
单词高亮工具 - Android 版本 (Kivy)
使用 Buildozer 打包成 APK
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.properties import BooleanProperty, StringProperty, NumericProperty, ObjectProperty
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.uix.filechooser import FileChooserListView

import spacy
import threading
import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup

# 文件选择器 - Android 兼容
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    from jnius import autoclass
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.INTERNET
    ])
else:
    from kivy.uix.filechooser import FileChooserListView

# 翻译功能
try:
    from googletrans import Translator as GoogleTranslator
    translator = GoogleTranslator()
    _TRANSLATOR_AVAILABLE = True
except Exception:
    translator = None
    _TRANSLATOR_AVAILABLE = False


class WordBank:
    """词库管理类"""
    def __init__(self, show_error_callback=None):
        """初始化词库和 spaCy 词形还原器"""
        self.show_error_callback = show_error_callback
        try:
            # 获取应用数据路径
            if platform == 'android':
                from android.storage import app_storage_path
                base_path = app_storage_path()
            elif getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            model_path = os.path.join(base_path, "en_core_web_sm")
            
            # 如果模型不存在，使用简化的词形还原
            if not os.path.exists(model_path):
                print(f"警告: 模型文件夹不存在: {model_path}，使用简化模式")
                self.nlp = None
                if self.show_error_callback:
                    self.show_error_callback("提示", "未找到 spaCy 模型，将使用简化的词形还原功能")
            else:
                self.nlp = spacy.load(model_path)
        except Exception as e:
            print(f"加载模型出错: {e}")
            self.nlp = None
            if self.show_error_callback:
                self.show_error_callback("错误", f"加载模型出错: {e}\n将使用简化模式")
        
        self.words = set()

    def add_word(self, word):
        """添加单词到词库"""
        word = word.lower().strip()
        if not word:
            return None
        self.words.add(word)
        return word

    def remove_word(self, word):
        """从词库移除单词"""
        word = word.lower().strip()
        if word in self.words:
            self.words.remove(word)
            return True
        return False

    def normalize_word(self, word):
        """词形还原"""
        word = word.lower()
        if self.nlp:
            doc = self.nlp(word)
            return doc[0].lemma_ if doc else word
        else:
            # 改进的词形还原（回退模式）
            return self._fallback_lemmatize(word)
    
    def _fallback_lemmatize(self, word):
        """改进的回退词形还原（无spaCy时使用）"""
        # 常见不规则动词
        irregular_verbs = {
            'was': 'be', 'were': 'be', 'been': 'be', 'being': 'be',
            'had': 'have', 'has': 'have', 'having': 'have',
            'did': 'do', 'does': 'do', 'done': 'do', 'doing': 'do',
            'went': 'go', 'goes': 'go', 'gone': 'go', 'going': 'go',
            'came': 'come', 'comes': 'come', 'coming': 'come',
            'saw': 'see', 'sees': 'see', 'seen': 'see', 'seeing': 'see',
            'got': 'get', 'gets': 'get', 'gotten': 'get', 'getting': 'get',
            'took': 'take', 'takes': 'take', 'taken': 'take', 'taking': 'take',
            'made': 'make', 'makes': 'make', 'making': 'make',
            'said': 'say', 'says': 'say', 'saying': 'say',
            'told': 'tell', 'tells': 'tell', 'telling': 'tell',
            'knew': 'know', 'knows': 'know', 'known': 'know', 'knowing': 'know',
            'thought': 'think', 'thinks': 'think', 'thinking': 'think',
            'felt': 'feel', 'feels': 'feel', 'feeling': 'feel',
            'found': 'find', 'finds': 'find', 'finding': 'find',
            'gave': 'give', 'gives': 'give', 'given': 'give', 'giving': 'give',
            'ran': 'run', 'runs': 'run', 'running': 'run',
            'wrote': 'write', 'writes': 'write', 'written': 'write', 'writing': 'write',
        }
        
        if word in irregular_verbs:
            return irregular_verbs[word]
        
        # -ing 结尾
        if word.endswith('ing') and len(word) > 5:
            # running -> run (双写辅音)
            if len(word) > 6 and word[-4] == word[-5] and word[-4] not in 'aeiou':
                return word[:-4]
            # making -> make
            base = word[:-3]
            if len(base) >= 3:
                # 尝试加e
                if base[-1] not in 'aeiou' and len(base) >= 2 and base[-2] in 'aeiou':
                    return base + 'e'
                return base
        
        # -ed 结尾
        elif word.endswith('ed') and len(word) > 4:
            # succeeded -> succeed (eed结尾)
            if word.endswith('eed') and len(word) > 5:
                return word[:-2]  # 去掉 'ed' 而不是 'd'
            # stopped -> stop (双写辅音)
            if len(word) > 5 and word[-3] == word[-4] and word[-3] not in 'aeiou':
                return word[:-3]
            # fired -> fire, loved -> love
            base = word[:-2]
            if len(base) >= 2 and base[-1] not in 'aeiou' and base[-2] in 'aeiou':
                return base + 'e'
            return base
        
        # -s 结尾（复数/第三人称单数）
        elif word.endswith('s') and len(word) > 3 and not word.endswith('ss'):
            # cities -> city
            if word.endswith('ies') and len(word) > 4:
                return word[:-3] + 'y'
            # boxes -> box, classes -> class
            elif word.endswith('es'):
                base = word[:-2]
                if base.endswith(('s', 'sh', 'ch', 'x', 'z')):
                    return base
                return word[:-1]
            # cats -> cat
            return word[:-1]
        
        return word

    def highlight_words(self, text):
        """高亮文本中的词库单词"""
        if self.nlp:
            doc = self.nlp(text)
            result = []
            last_end = 0
            for token in doc:
                if token.is_alpha:
                    start, end = token.idx, token.idx + len(token.text)
                    result.append((text[last_end:start], "normal", None))
                    lemma = token.lemma_.lower()
                    if lemma in self.words:
                        result.append((token.text, "highlight", lemma))
                    else:
                        result.append((token.text, "normal", None))
                    last_end = end
            result.append((text[last_end:], "normal", None))
            return result
        else:
            # 简化模式：按空格分词
            result = []
            words = re.findall(r'\b\w+\b|\W+', text)
            for word in words:
                if word.strip() and word.isalpha():
                    lemma = self.normalize_word(word)
                    if lemma in self.words:
                        result.append((word, "highlight", lemma))
                    else:
                        result.append((word, "normal", None))
                else:
                    result.append((word, "normal", None))
            return result

    def save_word_bank(self, filepath):
        """保存词库到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write('\n'.join(sorted(self.words)))
            return True
        except Exception as e:
            print(f"保存词库出错: {e}")
            return False

    def load_word_bank(self, filepath):
        """从文件加载词库"""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                self.words = {line.strip().lower() for line in file if line.strip()}
            return True
        except Exception as e:
            print(f"加载词库出错: {e}")
            return False


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout):
    """可选择的列表布局"""
    pass


class WordListItem(BoxLayout):
    """词库列表项 - 简化版本"""
    def __init__(self, word, remove_callback, **kwargs):
        super(WordListItem, self).__init__(**kwargs)
        self.word = word
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 45
        self.padding = [5, 2, 5, 2]
        self.spacing = 5
        
        # 添加背景
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)  # 浅灰背景
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # 单词标签
        self.word_label = Label(
            text=word, 
            size_hint_x=0.75, 
            font_name='Chinese',
            color=(0.1, 0.1, 0.1, 1),  # 深灰色文字
            font_size='18sp',
            halign='left',
            valign='middle',
            text_size=(None, None)
        )
        self.add_widget(self.word_label)
        
        # 删除按钮
        remove_btn = Button(
            text='删除', 
            size_hint_x=0.25, 
            font_name='Chinese', 
            background_color=(0.9, 0.3, 0.3, 1),
            font_size='16sp'
        )
        remove_btn.bind(on_press=lambda x: remove_callback(word))
        self.add_widget(remove_btn)
    
    def _update_bg(self, *args):
        """更新背景"""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class WordHighlighterApp(App):
    """单词高亮工具主应用"""
    
    def __init__(self, **kwargs):
        super(WordHighlighterApp, self).__init__(**kwargs)
        self.word_bank = None
        self.progress_value = NumericProperty(0)
        self.file_chooser_callback = None  # 文件选择回调
        self._register_fonts()
    
    def _register_fonts(self):
        """注册中文字体"""
        try:
            # Windows 系统字体路径
            if platform == 'win':
                font_paths = [
                    'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
                    'C:/Windows/Fonts/simsun.ttc',  # 宋体
                    'C:/Windows/Fonts/simhei.ttf',  # 黑体
                ]
            # Android 系统字体路径
            elif platform == 'android':
                font_paths = [
                    '/system/fonts/DroidSansFallback.ttf',
                    '/system/fonts/NotoSansCJK-Regular.ttc',
                    '/system/fonts/NotoSansHans-Regular.otf',
                ]
            # Linux 系统字体路径
            elif platform == 'linux':
                font_paths = [
                    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
                    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                ]
            # Mac 系统字体路径
            elif platform == 'macosx':
                font_paths = [
                    '/System/Library/Fonts/PingFang.ttc',
                    '/Library/Fonts/Arial Unicode.ttf',
                ]
            else:
                font_paths = []
            
            # 尝试注册第一个可用的字体
            for font_path in font_paths:
                if os.path.exists(font_path):
                    LabelBase.register(name='Chinese', fn_regular=font_path)
                    print(f"成功加载字体: {font_path}")
                    return
            
            print("警告: 未找到中文字体，中文可能显示为方框")
        except Exception as e:
            print(f"注册字体时出错: {e}")
        
    def build(self):
        """构建应用界面"""
        # 设置窗口背景色
        Window.clearcolor = (0.96, 0.96, 0.96, 1)
        
        # 初始化词库
        self.word_bank = WordBank(show_error_callback=self.show_popup)
        
        # 主布局
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 顶部标题
        title = Label(
            text='单词高亮工具 (Android)',
            size_hint_y=None,
            height=50,
            font_size='20sp',
            font_name='Chinese',
            bold=True,
            color=(0.13, 0.59, 0.95, 1)
        )
        main_layout.add_widget(title)
        
        # 选项卡面板
        tabs = TabbedPanel(do_default_tab=False, tab_width=150)
        
        # 第一个选项卡：文本处理
        text_tab = TabbedPanelItem(text='文本处理')
        text_tab.content = self.create_text_panel()
        tabs.add_widget(text_tab)
        
        # 第二个选项卡：词库管理
        word_tab = TabbedPanelItem(text='词库管理')
        word_tab.content = self.create_word_panel()
        tabs.add_widget(word_tab)
        
        # 第三个选项卡：文件操作
        file_tab = TabbedPanelItem(text='文件操作')
        file_tab.content = self.create_file_panel()
        tabs.add_widget(file_tab)
        
        main_layout.add_widget(tabs)
        
        return main_layout
    
    def create_text_panel(self):
        """创建文本处理面板"""
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # URL 输入区域
        url_box = BoxLayout(size_hint_y=None, height=50, spacing=5)
        url_box.add_widget(Label(text='URL:', size_hint_x=0.15, font_name='Chinese'))
        self.url_input = TextInput(
            hint_text='输入网页地址',
            multiline=False,
            size_hint_x=0.6,
            font_name='Chinese'
        )
        url_box.add_widget(self.url_input)
        fetch_btn = Button(
            text='获取',
            size_hint_x=0.25,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        fetch_btn.bind(on_press=self.fetch_webpage)
        url_box.add_widget(fetch_btn)
        layout.add_widget(url_box)
        
        # 输入文本区域
        layout.add_widget(Label(text='输入文本:', size_hint_y=None, height=30, font_name='Chinese'))
        self.input_text = TextInput(
            hint_text='在此输入或粘贴文本...',
            multiline=True,
            font_name='Chinese'
        )
        layout.add_widget(self.input_text)
        
        # 按钮组
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=5)
        highlight_btn = Button(
            text='高亮文本',
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        highlight_btn.bind(on_press=self.highlight_text)
        btn_box.add_widget(highlight_btn)
        
        translate_btn = Button(
            text='翻译选中',
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        translate_btn.bind(on_press=self.translate_text)
        btn_box.add_widget(translate_btn)
        layout.add_widget(btn_box)
        
        # 进度条
        self.progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        layout.add_widget(self.progress_bar)
        self.progress_label = Label(text='0%', size_hint_y=None, height=20, font_name='Chinese')
        layout.add_widget(self.progress_label)
        
        # 输出文本区域
        layout.add_widget(Label(text='输出文本:', size_hint_y=None, height=30, font_name='Chinese'))
        
        # 使用 Label 显示输出文本（支持markup和点击）
        scroll = ScrollView()
        
        self.output_text = Label(
            text='高亮结果将显示在此...\n\n提示：\n1. 橙色单词：已在词库中，可点击定位或删除\n2. 普通单词：点击可直接添加到词库',
            markup=True,
            font_name='Chinese',
            size_hint_y=None,
            text_size=(Window.width - 40, None),
            halign='left',
            valign='top'
        )
        self.output_text.bind(texture_size=self.output_text.setter('size'))
        self.output_text.bind(on_ref_press=self.on_word_click)  # 绑定高亮单词点击
        scroll.add_widget(self.output_text)
        layout.add_widget(scroll)
        
        return layout
    
    def create_word_panel(self):
        """创建词库管理面板"""
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # 提示信息
        warning = Label(
            text='词库存储在内存中，关闭程序后将丢失。请及时保存到文件。',
            size_hint_y=None,
            height=40,
            font_name='Chinese',
            color=(1, 0, 0, 1)
        )
        layout.add_widget(warning)
        
        # 搜索框
        search_box = BoxLayout(size_hint_y=None, height=50, spacing=5)
        search_box.add_widget(Label(text='搜索:', size_hint_x=0.2, font_name='Chinese'))
        self.search_input = TextInput(
            hint_text='输入关键词',
            multiline=False,
            size_hint_x=0.5,
            font_name='Chinese'
        )
        search_box.add_widget(self.search_input)
        search_btn = Button(
            text='搜索',
            size_hint_x=0.15,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        search_btn.bind(on_press=self.search_word)
        search_box.add_widget(search_btn)
        next_btn = Button(
            text='下一个',
            size_hint_x=0.15,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        next_btn.bind(on_press=self.search_next)
        search_box.add_widget(next_btn)
        layout.add_widget(search_box)
        
        # 单词输入框
        word_box = BoxLayout(size_hint_y=None, height=50, spacing=5)
        word_box.add_widget(Label(text='单词:', size_hint_x=0.2, font_name='Chinese'))
        self.word_input = TextInput(
            hint_text='输入单词',
            multiline=False,
            size_hint_x=0.5,
            font_name='Chinese'
        )
        self.word_input.bind(on_text_validate=self.add_word)
        word_box.add_widget(self.word_input)
        add_btn = Button(
            text='添加',
            size_hint_x=0.15,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        add_btn.bind(on_press=self.add_word)
        word_box.add_widget(add_btn)
        remove_btn = Button(
            text='移除',
            size_hint_x=0.15,
            font_name='Chinese',
            background_color=(0.8, 0.2, 0.2, 1)
        )
        remove_btn.bind(on_press=self.remove_word)
        word_box.add_widget(remove_btn)
        layout.add_widget(word_box)
        
        # 快速添加按钮（从输出文本添加单词）
        quick_add_btn = Button(
            text='从输出文本添加单词',
            size_hint_y=None,
            height=50,
            font_name='Chinese',
            background_color=(0.2, 0.7, 0.2, 1)
        )
        quick_add_btn.bind(on_press=lambda x: self.show_add_word_dialog())
        layout.add_widget(quick_add_btn)
        
        # 词库列表标题
        list_label = Label(
            text='词库列表 (向下滚动查看更多):',
            size_hint_y=None,
            height=30,
            font_name='Chinese',
            color=(0, 0, 0, 1),
            bold=True
        )
        layout.add_widget(list_label)
        
        # 创建滚动视图来显示词库列表
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=10)
        
        # 添加白色背景到 ScrollView
        from kivy.graphics import Color, Rectangle
        with scroll_view.canvas.before:
            Color(1, 1, 1, 1)
            scroll_view.bg_rect = Rectangle(pos=scroll_view.pos, size=scroll_view.size)
        scroll_view.bind(pos=lambda i, v: setattr(scroll_view.bg_rect, 'pos', v))
        scroll_view.bind(size=lambda i, v: setattr(scroll_view.bg_rect, 'size', v))
        
        # 创建列表容器
        self.word_list_container = GridLayout(
            cols=1,
            spacing=3,
            size_hint_y=None,
            padding=[5, 5, 5, 5]
        )
        self.word_list_container.bind(minimum_height=self.word_list_container.setter('height'))
        
        scroll_view.add_widget(self.word_list_container)
        layout.add_widget(scroll_view)
        
        # 更新按钮
        update_btn = Button(
            text='刷新词库列表',
            size_hint_y=None,
            height=50,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        update_btn.bind(on_press=self.update_word_list)
        layout.add_widget(update_btn)
        
        return layout
    
    def create_file_panel(self):
        """创建文件操作面板"""
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # 词库文件操作
        layout.add_widget(Label(text='词库文件操作', size_hint_y=None, height=40, font_name='Chinese', bold=True))
        
        save_btn = Button(
            text='保存词库到文件',
            size_hint_y=None,
            height=50,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        save_btn.bind(on_press=self.save_word_bank)
        layout.add_widget(save_btn)
        
        load_btn = Button(
            text='从文件加载词库',
            size_hint_y=None,
            height=50,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        load_btn.bind(on_press=self.load_word_bank)
        layout.add_widget(load_btn)
        
        # 文本文件操作
        layout.add_widget(Label(text='文本文件操作', size_hint_y=None, height=40, font_name='Chinese', bold=True))
        
        import_txt_btn = Button(
            text='导入 TXT 文件',
            size_hint_y=None,
            height=50,
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        import_txt_btn.bind(on_press=self.import_txt_file)
        layout.add_widget(import_txt_btn)
        
        # 文件路径输入（所有平台）
        if platform == 'android':
            hint_text = '/sdcard/wordbank.txt'
            info_text = 'Android 文件路径提示:\n• 默认路径：/sdcard/ 或 /storage/emulated/0/\n• 下载文件夹：/sdcard/Download/\n• 需要存储权限'
        else:
            hint_text = 'wordbank.txt'
            info_text = '文件路径提示:\n输入完整路径或相对路径（相对于当前目录）'
        
        layout.add_widget(Label(
            text=info_text,
            size_hint_y=None,
            height=80 if platform == 'android' else 60,
            font_name='Chinese'
        ))
        
        path_box = BoxLayout(size_hint_y=None, height=50, spacing=5)
        path_box.add_widget(Label(text='文件路径:', size_hint_x=0.25, font_name='Chinese'))
        self.file_path_input = TextInput(
            hint_text=hint_text,
            text=hint_text if platform != 'android' else '',
            multiline=False,
            font_name='Chinese',
            size_hint_x=0.55
        )
        path_box.add_widget(self.file_path_input)
        
        # 浏览按钮
        browse_btn = Button(
            text='浏览',
            size_hint_x=0.2,
            font_name='Chinese',
            background_color=(0.2, 0.7, 0.2, 1)
        )
        browse_btn.bind(on_press=self.browse_file)
        path_box.add_widget(browse_btn)
        
        layout.add_widget(path_box)
        
        # 占位符
        layout.add_widget(Label(text='', font_name='Chinese'))
        
        return layout
    
    @mainthread
    def show_popup(self, title, message):
        """显示弹窗"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=message, text_size=(300, None), font_name='Chinese'))
        
        btn = Button(text='确定', size_hint_y=None, height=50, font_name='Chinese')
        content.add_widget(btn)
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.4)
        )
        btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def show_file_chooser(self, callback, mode='open', filters=None):
        """显示文件选择对话框"""
        self.file_chooser_callback = callback
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # 文件选择器
        if platform == 'android':
            # Android 上显示手动输入（因为文件选择器在 Android 上较复杂）
            content.add_widget(Label(
                text='请在下方输入文件路径:',
                size_hint_y=None,
                height=40,
                font_name='Chinese'
            ))
            
            path_input = TextInput(
                text='/sdcard/',
                multiline=False,
                size_hint_y=None,
                height=50,
                font_name='Chinese'
            )
            content.add_widget(path_input)
            
            btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
            confirm_btn = Button(text='确定', font_name='Chinese', background_color=(0.13, 0.59, 0.95, 1))
            cancel_btn = Button(text='取消', font_name='Chinese', background_color=(0.8, 0.2, 0.2, 1))
            
            def confirm(instance):
                if self.file_chooser_callback:
                    self.file_chooser_callback(path_input.text)
                self.file_chooser_popup.dismiss()
            
            confirm_btn.bind(on_press=confirm)
            cancel_btn.bind(on_press=lambda x: self.file_chooser_popup.dismiss())
            
            btn_box.add_widget(confirm_btn)
            btn_box.add_widget(cancel_btn)
            content.add_widget(btn_box)
        else:
            # 桌面平台使用文件选择器
            filechooser = FileChooserListView(
                path=os.path.expanduser('~'),
                filters=filters if filters else ['*.*']
            )
            content.add_widget(filechooser)
            
            # 路径显示
            path_label = Label(
                text='',
                size_hint_y=None,
                height=30,
                font_name='Chinese'
            )
            content.add_widget(path_label)
            
            def update_selection(instance, value):
                if value:
                    path_label.text = f'选中: {value[0]}'
            
            filechooser.bind(selection=update_selection)
            
            # 按钮
            btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
            confirm_btn = Button(text='确定', font_name='Chinese', background_color=(0.13, 0.59, 0.95, 1))
            cancel_btn = Button(text='取消', font_name='Chinese', background_color=(0.8, 0.2, 0.2, 1))
            
            def confirm(instance):
                if filechooser.selection and self.file_chooser_callback:
                    self.file_chooser_callback(filechooser.selection[0])
                self.file_chooser_popup.dismiss()
            
            confirm_btn.bind(on_press=confirm)
            cancel_btn.bind(on_press=lambda x: self.file_chooser_popup.dismiss())
            
            btn_box.add_widget(confirm_btn)
            btn_box.add_widget(cancel_btn)
            content.add_widget(btn_box)
        
        # 创建弹窗
        self.file_chooser_popup = Popup(
            title='选择文件' if mode == 'open' else '保存文件',
            content=content,
            size_hint=(0.9, 0.9)
        )
        self.file_chooser_popup.open()
    
    def browse_file(self, instance):
        """打开文件浏览对话框"""
        def on_file_selected(filepath):
            self.file_path_input.text = filepath
        
        self.show_file_chooser(on_file_selected, mode='open')
    
    def fetch_webpage(self, instance):
        """获取网页内容"""
        url = self.url_input.text.strip()
        if not url:
            self.show_popup('错误', '请输入有效的URL！')
            return
        
        def fetch():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text()
                Clock.schedule_once(lambda dt: self._set_input_text(text))
                self.show_popup('成功', '网页内容已成功导入！')
            except Exception as e:
                self.show_popup('错误', f'获取网页内容失败：{e}')
        
        threading.Thread(target=fetch, daemon=True).start()
    
    @mainthread
    def _set_input_text(self, text):
        """设置输入文本"""
        self.input_text.text = text
    
    def highlight_text(self, instance):
        """高亮文本"""
        text = self.input_text.text.strip()
        if not text:
            self.show_popup('错误', '请输入文本以进行高亮！')
            return
        
        def process():
            text_cleaned = re.sub(r'\n\s*\n', '\n\n', text)
            paragraphs = text_cleaned.split('\n\n')
            total = len(paragraphs)
            
            result_markup = ''
            word_count = 0  # 用于唯一标识每个单词
            
            for i, paragraph in enumerate(paragraphs):
                if paragraph.strip():
                    highlighted = self.word_bank.highlight_words(paragraph)
                    for segment, tag, lemma in highlighted:
                        if tag == "highlight":
                            # 使用 Kivy ref 标签实现可点击的高亮（已在词库）
                            result_markup += f'[b][color=ff6b00][ref={lemma}_{word_count}_IN]{segment}[/ref][/color][/b]'
                            word_count += 1
                        else:
                            # 检查是否为单词，如果是则添加可点击功能（未在词库）
                            if segment.strip() and segment.strip().isalpha():
                                word = segment.strip()
                                lemma_normalized = self.word_bank.normalize_word(word)
                                result_markup += f'[ref={lemma_normalized}_{word_count}_OUT]{segment}[/ref]'
                                word_count += 1
                            else:
                                result_markup += segment
                    
                    if i < len(paragraphs) - 1:
                        result_markup += '\n\n'
                
                # 更新进度
                progress = (i + 1) / total * 100
                Clock.schedule_once(lambda dt, p=progress: self._update_progress(p))
            
            Clock.schedule_once(lambda dt: self._set_output_text(result_markup))
            Clock.schedule_once(lambda dt: self._update_progress(100))
            time.sleep(0.5)
            Clock.schedule_once(lambda dt: self._update_progress(0))
        
        threading.Thread(target=process, daemon=True).start()
    
    @mainthread
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_bar.value = value
        if value > 0:
            self.progress_label.text = f'{int(value)}%'
        else:
            self.progress_label.text = ''
    
    @mainthread
    def _set_output_text(self, text):
        """设置输出文本"""
        self.output_text.text = text
    
    def remove_word_from_list(self, word):
        """从列表中删除单词"""
        if word in self.word_bank.words:
            self.word_bank.remove_word(word)
            self.update_word_list(None)
            self.show_popup('成功', f"单词 '{word}' 已从词库删除！")
    
    def show_add_word_dialog(self):
        """显示添加单词对话框"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        content.add_widget(Label(
            text='添加单词到词库',
            size_hint_y=None,
            height=40,
            font_name='Chinese',
            font_size='18sp',
            bold=True
        ))
        
        word_input = TextInput(
            hint_text='输入单词（英文）',
            multiline=False,
            size_hint_y=None,
            height=50,
            font_name='Chinese'
        )
        content.add_widget(word_input)
        
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        def add_word(instance):
            word = word_input.text.strip().lower()
            if word and word.isalpha():
                self.word_bank.add_word(word)
                self.update_word_list(None)
                self.show_popup('成功', f"单词 '{word}' 已添加到词库！")
                add_popup.dismiss()
            else:
                self.show_popup('错误', '请输入有效的英文单词！')
        
        add_btn = Button(text='添加', font_name='Chinese', background_color=(0.13, 0.59, 0.95, 1))
        add_btn.bind(on_press=add_word)
        btn_box.add_widget(add_btn)
        
        cancel_btn = Button(text='取消', font_name='Chinese', background_color=(0.5, 0.5, 0.5, 1))
        btn_box.add_widget(cancel_btn)
        
        content.add_widget(btn_box)
        
        add_popup = Popup(
            title='添加单词',
            content=content,
            size_hint=(0.8, 0.4)
        )
        cancel_btn.bind(on_press=add_popup.dismiss)
        add_popup.open()
    
    def on_word_click(self, instance, ref):
        """处理高亮单词的点击事件"""
        # ref格式为 "lemma_count_STATUS"，提取lemma和状态
        parts = ref.rsplit('_', 2)
        if len(parts) >= 3:
            lemma = parts[0]
            status = parts[2]  # 'IN' 或 'OUT'
        else:
            lemma = ref
            status = 'IN'  # 默认为已在词库
        
        in_wordbank = (status == 'IN')
        
        # 显示单词操作菜单
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        content.add_widget(Label(
            text=f'单词: {lemma}',
            size_hint_y=None,
            height=40,
            font_name='Chinese',
            font_size='18sp',
            bold=True
        ))
        
        # 根据单词是否在词库显示不同的操作
        if in_wordbank:
            # 已在词库中的单词
            btn_box = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=170)
            
            # 在词库列表中定位
            locate_btn = Button(
                text='在词库中定位',
                font_name='Chinese',
                background_color=(0.13, 0.59, 0.95, 1)
            )
            locate_btn.bind(on_press=lambda x: self.locate_word_in_list(lemma))
            btn_box.add_widget(locate_btn)
            
            # 从词库删除
            remove_btn = Button(
                text='从词库删除',
                font_name='Chinese',
                background_color=(0.8, 0.2, 0.2, 1)
            )
            remove_btn.bind(on_press=lambda x: self.remove_word_from_click(lemma))
            btn_box.add_widget(remove_btn)
            
            # 关闭按钮
            close_btn = Button(
                text='关闭',
                font_name='Chinese',
                background_color=(0.5, 0.5, 0.5, 1)
            )
            btn_box.add_widget(close_btn)
        else:
            # 未在词库中的单词
            btn_box = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=120)
            
            # 添加到词库
            add_btn = Button(
                text='添加到词库',
                font_name='Chinese',
                background_color=(0.2, 0.7, 0.2, 1)
            )
            add_btn.bind(on_press=lambda x: self.add_word_from_click(lemma))
            btn_box.add_widget(add_btn)
            
            # 关闭按钮
            close_btn = Button(
                text='关闭',
                font_name='Chinese',
                background_color=(0.5, 0.5, 0.5, 1)
            )
            btn_box.add_widget(close_btn)
        
        content.add_widget(btn_box)
        
        popup = Popup(
            title='单词操作',
            content=content,
            size_hint=(0.8, 0.4)
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def locate_word_in_list(self, lemma):
        """在词库列表中定位单词"""
        from kivy.graphics import Color, Rectangle
        
        words = sorted(self.word_bank.words)
        if lemma in words:
            index = words.index(lemma)
            # 重新显示完整列表，并高亮目标单词
            self.word_list_container.clear_widgets()
            for i, word in enumerate(words):
                item = WordListItem(word, self.remove_word_from_list)
                # 如果是目标单词，改变背景色高亮显示
                if word == lemma:
                    with item.canvas.before:
                        Color(1, 1, 0.7, 1)  # 黄色高亮
                        item.highlight_rect = Rectangle(pos=item.pos, size=item.size)
                    item.bind(pos=lambda i, v, r=item.highlight_rect: setattr(r, 'pos', v))
                    item.bind(size=lambda i, v, r=item.highlight_rect: setattr(r, 'size', v))
                self.word_list_container.add_widget(item)
            
            self.show_popup('定位', f'单词 "{lemma}" 在词库列表第 {index + 1} 位\n已用黄色高亮显示\n\n请切换到"词库管理"选项卡查看')
        else:
            self.show_popup('提示', f'单词 "{lemma}" 不在词库中')
    
    def remove_word_from_click(self, lemma):
        """从点击的单词删除"""
        if self.word_bank.remove_word(lemma):
            self.update_word_list(None)
            self.show_popup('成功', f"单词 '{lemma}' 已从词库移除！\n请重新高亮文本以更新显示。")
        else:
            self.show_popup('错误', f"单词 '{lemma}' 不在词库中！")
    
    def add_word_from_click(self, lemma):
        """从点击添加单词到词库"""
        if lemma in self.word_bank.words:
            self.show_popup('提示', f"单词 '{lemma}' 已在词库中！")
        else:
            self.word_bank.add_word(lemma)
            self.update_word_list(None)
            self.show_popup('成功', f"单词 '{lemma}' 已添加到词库！\n请重新高亮文本以更新显示。")
    
    def translate_text(self, instance):
        """翻译文本（Android版本 - 使用对话框输入）"""
        if not _TRANSLATOR_AVAILABLE:
            self.show_popup('错误', '翻译功能不可用：未安装 googletrans 库')
            return
        
        # 显示翻译输入对话框
        self.show_translate_dialog()
    
    def show_translate_dialog(self):
        """显示翻译输入对话框"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        content.add_widget(Label(
            text='翻译功能',
            size_hint_y=None,
            height=40,
            font_name='Chinese',
            font_size='18sp',
            bold=True
        ))
        
        # 输入框
        text_input = TextInput(
            hint_text='输入要翻译的文本（英文）',
            multiline=True,
            size_hint_y=None,
            height=100,
            font_name='Chinese'
        )
        content.add_widget(text_input)
        
        # 翻译结果显示
        result_label = Label(
            text='翻译结果将显示在这里...',
            size_hint_y=None,
            height=150,
            font_name='Chinese',
            color=(0.2, 0.6, 0.2, 1),
            text_size=(300, None),
            halign='left',
            valign='top'
        )
        content.add_widget(result_label)
        
        # 按钮区域
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        # 翻译按钮
        def do_translate(instance):
            text = text_input.text.strip()
            if text:
                try:
                    result_label.text = '翻译中...'
                    # 在新线程中执行翻译
                    def translate_thread():
                        try:
                            translation = translator.translate(text, dest='zh-CN')
                            Clock.schedule_once(
                                lambda dt: setattr(result_label, 'text', 
                                    f'原文：{text}\n\n译文：{translation.text}')
                            )
                        except Exception as e:
                            Clock.schedule_once(
                                lambda dt: setattr(result_label, 'text', f'翻译失败：{e}')
                            )
                    threading.Thread(target=translate_thread, daemon=True).start()
                except Exception as e:
                    result_label.text = f'翻译出错：{e}'
            else:
                result_label.text = '请输入要翻译的文本！'
        
        translate_btn = Button(
            text='翻译',
            font_name='Chinese',
            background_color=(0.13, 0.59, 0.95, 1)
        )
        translate_btn.bind(on_press=do_translate)
        btn_box.add_widget(translate_btn)
        
        # 关闭按钮
        close_btn = Button(
            text='关闭',
            font_name='Chinese',
            background_color=(0.5, 0.5, 0.5, 1)
        )
        btn_box.add_widget(close_btn)
        
        content.add_widget(btn_box)
        
        # 创建弹窗
        translate_popup = Popup(
            title='翻译工具',
            content=content,
            size_hint=(0.9, 0.7)
        )
        close_btn.bind(on_press=translate_popup.dismiss)
        translate_popup.open()
    
    def add_word(self, instance):
        """添加单词到词库"""
        word = self.word_input.text.strip()
        if word:
            word_lower = word.lower()
            self.word_bank.add_word(word_lower)
            self.update_word_list(None)  # 自动更新列表
            self.show_popup('成功', f"单词 '{word_lower}' 已添加到词库！")
            self.word_input.text = ''
        else:
            self.show_popup('错误', '请输入有效的单词！')
    
    def remove_word(self, instance):
        """从词库移除单词"""
        word = self.word_input.text.strip().lower()
        if word:
            if self.word_bank.remove_word(word):
                self.update_word_list(None)
                self.show_popup('成功', f"单词 '{word}' 已从词库移除！")
                self.word_input.text = ''
            else:
                self.show_popup('错误', f"单词 '{word}' 不在词库中！")
        else:
            self.show_popup('错误', '请输入要移除的单词！')
    
    def remove_word_from_list(self, word):
        """从列表中移除单词"""
        if self.word_bank.remove_word(word):
            self.update_word_list(None)
            self.show_popup('成功', f"单词 '{word}' 已移除！")
    
    def search_word(self, instance):
        """搜索单词"""
        keyword = self.search_input.text.strip().lower()
        if keyword:
            matching_words = [w for w in sorted(self.word_bank.words) if keyword in w]
            if matching_words:
                # 清空并显示匹配的单词
                self.word_list_container.clear_widgets()
                for word in matching_words:
                    item = WordListItem(word, self.remove_word_from_list)
                    self.word_list_container.add_widget(item)
                self.show_popup('搜索结果', f'找到 {len(matching_words)} 个匹配项')
            else:
                self.show_popup('提示', '未找到匹配项')
        else:
            self.update_word_list(None)
    
    def search_next(self, instance):
        """搜索下一个（简化版）"""
        self.search_word(instance)
    
    def update_word_list(self, instance):
        """更新词库列表（使用GridLayout显示）"""
        words = sorted(self.word_bank.words)
        
        # 清空现有列表
        self.word_list_container.clear_widgets()
        
        # 调试输出
        print(f"[调试] 更新词库列表：共 {len(words)} 个单词")
        if len(words) > 0:
            print(f"[调试] 前5个单词: {words[:5]}")
        
        # 如果词库为空，显示提示
        if len(words) == 0:
            empty_label = Label(
                text='词库为空\n\n请在上方输入框添加单词\n或在"文本处理"选项卡点击单词添加',
                font_name='Chinese',
                color=(0.5, 0.5, 0.5, 1),
                font_size='16sp',
                size_hint_y=None,
                height=100
            )
            self.word_list_container.add_widget(empty_label)
        else:
            # 添加每个单词到列表
            for word in words:
                item = WordListItem(word, self.remove_word_from_list)
                self.word_list_container.add_widget(item)
        
        print(f"[调试] word_list_container 子控件数量: {len(self.word_list_container.children)}")
        
        if instance:  # 只在手动刷新时显示提示
            if len(words) > 0:
                self.show_popup('提示', f'词库共有 {len(words)} 个单词\n列表已更新！')
            else:
                self.show_popup('提示', '词库为空，请添加单词。')
    
    def save_word_bank(self, instance):
        """保存词库到文件"""
        filepath = self.file_path_input.text.strip()
        if not filepath:
            if platform == 'android':
                filepath = '/sdcard/wordbank.txt'
            else:
                filepath = 'wordbank.txt'
        
        if len(self.word_bank.words) == 0:
            self.show_popup('提示', '词库为空，无需保存。')
            return
        
        if self.word_bank.save_word_bank(filepath):
            self.show_popup('成功', f'词库已保存到：{filepath}\n共 {len(self.word_bank.words)} 个单词')
        else:
            self.show_popup('错误', f'保存词库时出错！\n请检查文件路径和写入权限。\n路径：{filepath}')
    
    def load_word_bank(self, instance):
        """从文件加载词库"""
        filepath = self.file_path_input.text.strip()
        if not filepath:
            if platform == 'android':
                filepath = '/sdcard/wordbank.txt'
            else:
                filepath = 'wordbank.txt'
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            self.show_popup('提示', f'文件不存在：{filepath}\n请先保存词库或检查文件路径。')
            return
        
        if self.word_bank.load_word_bank(filepath):
            # 重要：加载后立即更新词库列表显示
            self.update_word_list(None)  # 不显示提示，让下面的成功消息显示
            self.show_popup('成功', f'词库已从 {filepath} 加载！\n共 {len(self.word_bank.words)} 个单词\n\n请切换到"词库管理"选项卡查看列表。')
        else:
            self.show_popup('错误', f'加载词库时出错！文件路径：{filepath}')
    
    def import_txt_file(self, instance):
        """导入 TXT 文件"""
        filepath = self.file_path_input.text.strip()
        if not filepath:
            self.show_popup('错误', '请输入文件路径！')
            return
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            self.show_popup('提示', f'文件不存在：{filepath}\n请检查文件路径。')
            return
        
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            text = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(filepath, 'r', encoding=encoding) as file:
                        text = file.read()
                        used_encoding = encoding
                        break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                self.show_popup('错误', '无法读取文件，编码格式不支持。')
                return
            
            text = re.sub(r'\n\s*\n', '\n\n', text)
            self.input_text.text = text
            self.show_popup('成功', f'TXT 文件已成功导入！\n路径：{filepath}\n编码：{used_encoding}')
        except Exception as e:
            self.show_popup('错误', f'导入 TXT 文件时出错：{e}')


if __name__ == '__main__':
    WordHighlighterApp().run()

