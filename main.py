import sys
import re
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, 
                               QVBoxLayout, QPlainTextEdit, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QLabel)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QGuiApplication, QFont, QIcon
import markdownify
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

class ClipboardInspector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统剪贴板数据检测器")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel("当前剪贴板中的 MIME 类型 (双击行查看详细数据):")
        layout.addWidget(self.label)
        
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["MIME Type", "Data Size (Bytes)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.show_data)
        layout.addWidget(self.table)
        
        self.data_view = QTextEdit()
        self.data_view.setReadOnly(True)
        self.data_view.setPlaceholderText("在这里显示选中类型的原始数据...")
        self.data_view.setFont(QFont("Courier New", 10))
        layout.addWidget(self.data_view)
        
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新剪贴板")
        self.refresh_btn.clicked.connect(self.refresh_clipboard)
        btn_layout.addWidget(self.refresh_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        self.refresh_clipboard()

    def refresh_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        formats = mime_data.formats()
        
        self.table.setRowCount(0)
        self.data_view.clear()
        
        for fmt in formats:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(fmt))
            
            data = mime_data.data(fmt)
            self.table.setItem(row, 1, QTableWidgetItem(str(len(data))))

    def show_data(self, item):
        row = item.row()
        fmt = self.table.item(row, 0).text()
        
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        data = mime_data.data(fmt)
        
        try:
            # 尝试作为文本读取
            text = bytes(data).decode('utf-8', errors='replace')
            self.data_view.setPlainText(text)
        except Exception:
            # 否则显示十六进制
            hex_data = data.toHex(b' ')
            self.data_view.setPlainText(str(hex_data, 'ascii'))

class HtmlRichTextConverter(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HTML to Rich Text Converter (WebEngine)")
        # Windows/Linux环境下给 QDialog 增加默认的最大化/最小化控制按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1100, 650)
        
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText("在这里粘贴完整的网页 HTML 源码 (如 Gemini 或 ChatGPT 页面)...")
        self.input_text.textChanged.connect(self.update_html)
        
        # 使用 QWebEngineView 替换 QTextBrowser，完全接管复杂的 DOM和CSS渲染
        self.output_view = QWebEngineView()
        self.markdown_cache = ""
        
        splitter.addWidget(self.input_text)
        splitter.addWidget(self.output_view)
        
        splitter.setSizes([550, 550])
        main_layout.addWidget(splitter)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.inspect_btn = QPushButton("检测剪贴板数据类型")
        self.inspect_btn.setMinimumHeight(40)
        self.inspect_btn.clicked.connect(self.inspect_clipboard)
        bottom_layout.addWidget(self.inspect_btn)

        self.process_clipboard_btn = QPushButton("读取剪贴板并处理")
        self.process_clipboard_btn.setMinimumHeight(40)
        self.process_clipboard_btn.clicked.connect(self.process_clipboard)
        bottom_layout.addWidget(self.process_clipboard_btn)
        
        self.copy_btn = QPushButton("将右侧结果全选并复制到剪贴板")
        self.copy_btn.setMinimumHeight(40)
        self.copy_btn.setEnabled(False) # 默认禁用，直到网页渲染完毕
        self.copy_btn.clicked.connect(self.copy_output)
        bottom_layout.addWidget(self.copy_btn)
        
        main_layout.addLayout(bottom_layout)
        
        # 监听渲染完毕的信号来重新启用复制按钮
        self.output_view.loadFinished.connect(lambda ok: self.copy_btn.setEnabled(ok))

    def update_html(self):
        fragment = self.input_text.toPlainText()
        if not fragment.strip():
            self.output_view.setHtml("")
            self.copy_btn.setEnabled(False)
            return
            
        # 开始渲染新的 HTML，先禁用复制按钮
        self.copy_btn.setEnabled(False)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(fragment, 'html.parser')
        
        gemini_div = soup.find('div', id='chat-history')
        if gemini_div:
            container = gemini_div
        else:
            chatgpt_div = soup.find('div', id='thread')
            if chatgpt_div:
                bottom_container = chatgpt_div.find(id='thread-bottom-container')
                if bottom_container:
                    bottom_container.decompose()
                container = chatgpt_div
            else:
                container = None

        if container:
            # 提前处理代码块：将其转换为标准的 <pre><code class="language-xxx">...</code></pre> 格式
            for pre in container.find_all('pre'):
                language = ""
                # 尝试查找 ChatGPT 的语言头部
                header_div = pre.find('div', class_=lambda c: c and 'items-center' in c and 'justify-between' in c)
                if header_div:
                    lang_div = header_div.find('div', class_=lambda c: c and 'justify-self-start' in c)
                    if lang_div:
                        language = lang_div.get_text(strip=True)
                        
                # 尝试查找 Gemini 的语言类名
                code_tag = pre.find('code')
                if not language and code_tag:
                    classes = code_tag.get('class', [])
                    for c in classes:
                        if c.startswith('language-'):
                            language = c[9:]
                            break

                # ChatGPT 使用了 CodeMirror，每一行可能是 span 然后用 <br> 结尾。将其替换为 \n 才能使用 get_text 提取纯文本
                for br in pre.find_all('br'):
                    br.replace_with('\n')
                    
                # 从 DOM 树中移除 ChatGPT 代码块自带的复制按钮/标题头部，防止被当做代码混入文本
                if header_div:
                    header_div.decompose()
                    
                raw_code = pre.get_text()

                new_pre = soup.new_tag('pre')
                new_code = soup.new_tag('code')
                if language:
                    new_code['class'] = f"language-{language.lower()}"
                    
                new_code.string = raw_code
                new_pre.append(new_code)
                
                pre.replace_with(new_pre)

            fragment = container.decode_contents()
        else:
            fragment = ""

        import re
        import html
        from html.parser import HTMLParser

        # 移除包含干扰头像的 bard-avatar 标签及其内部的所有内容
        clean_fragment = re.sub(r'<bard-avatar.*?</bard-avatar>', '', fragment, flags=re.DOTALL)
        
        # 使用基于原生解析器的类来安全剥离包含无数嵌套 span 的数学公式 DOM节点
        class MathExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.result = []
                self.math_stack = [] # 记录当前是否在 math 节点内
                self.ignore_stack = [] # 记录当前是否在被丢弃的隐藏节点内
                
                self.katex_stack = [] # 记录 ChatGPT公式栈
                self.katex_is_block = False
                self.katex_in_annotation = False
                self.katex_latex = []
            
            def handle_starttag(self, tag, attrs):
                attr_dict = dict(attrs)
                
                # 如果当前属于被系统强行隐藏的垃圾容器（比如 Show thinking 文本、TTS控制栏），就不输出内容并不再递归
                if self.ignore_stack:
                    self.ignore_stack.append(tag)
                    return
                
                cls = attr_dict.get('class', '')
                ignore_tags = {'model-thoughts', 'tts-control', 'bard-avatar'}
                ignore_classes = {'thoughts-container', 'thoughts-wrapper', 'response-tts-container', 'tts', 'avatar-gutter', 'avatar-container'}
                
                # 判断当前标签是否中了垃圾拦截规则
                is_ignored = tag in ignore_tags
                if not is_ignored and any(c in ignore_classes for c in cls.split()):
                    is_ignored = True
                    
                if is_ignored:
                    self.ignore_stack.append(tag)
                    return

                # 如果我们已经在剥离一个数学节点，只需增加层级栈以跟踪嵌套，不输出原样标签
                if self.math_stack:
                    self.math_stack.append(tag)
                    return
                    
                if self.katex_stack:
                    self.katex_stack.append(tag)
                    if tag == 'annotation' and attr_dict.get('encoding') == 'application/x-tex':
                        self.katex_in_annotation = True
                    return

                # Check ChatGPT katex
                classes = cls.split()
                if 'katex-display' in classes:
                    self.katex_stack.append(tag)
                    self.katex_is_block = True
                    self.katex_latex = []
                    return
                elif 'katex' in classes:
                    self.katex_stack.append(tag)
                    self.katex_is_block = False
                    self.katex_latex = []
                    return
                
                # 检测是否是新的公式切入点
                if 'data-math' in attr_dict:
                    raw_latex = html.unescape(attr_dict['data-math'])
                    if 'math-inline' in cls:
                        self.result.append(f"${raw_latex}$")
                        self.math_stack.append(tag)
                        return
                    elif 'math-block' in cls:
                        self.result.append(f"$$\n{raw_latex}\n$$")
                        self.math_stack.append(tag)
                        return
                
                # 原样输出其他标签
                attrs_str = "".join([f' {k}="{html.escape(v)}"' if v is not None else f' {k}' for k, v in attrs])
                self.result.append(f"<{tag}{attrs_str}>")

            def handle_endtag(self, tag):
                # 鲁棒性增强：如果遇到了结束标签，我们应该尝试在栈中找到它
                # 如果它不在栈顶，说明中间有标签没闭合，我们需要强制弹出中间的所有标签
                if self.ignore_stack:
                    if tag in self.ignore_stack:
                        while self.ignore_stack:
                            popped = self.ignore_stack.pop()
                            if popped == tag: break
                    return
                    
                if self.math_stack:
                    if tag in self.math_stack:
                        while self.math_stack:
                            popped = self.math_stack.pop()
                            if popped == tag: break
                    return
                    
                if self.katex_stack:
                    if tag == 'annotation':
                        self.katex_in_annotation = False
                        
                    if tag in self.katex_stack:
                        while self.katex_stack:
                            popped = self.katex_stack.pop()
                            if popped == tag: break
                            
                    if not self.katex_stack:
                        raw_latex = html.unescape("".join(self.katex_latex))
                        if self.katex_is_block:
                            self.result.append(f"$$\n{raw_latex}\n$$")
                        else:
                            self.result.append(f"${raw_latex}$")
                    return
                    
                self.result.append(f"</{tag}>")

            def handle_data(self, data):
                if self.katex_in_annotation:
                    self.katex_latex.append(data)
                elif not self.math_stack and not self.ignore_stack and not self.katex_stack:
                    self.result.append(data)
                    
            def handle_entityref(self, name):
                if self.katex_in_annotation:
                    self.katex_latex.append(f"&{name};")
                elif not self.math_stack and not self.ignore_stack and not self.katex_stack:
                    self.result.append(f"&{name};")
                    
            def handle_charref(self, name):
                if self.katex_in_annotation:
                    self.katex_latex.append(f"&#{name};")
                elif not self.math_stack and not self.ignore_stack and not self.katex_stack:
                    self.result.append(f"&#{name};")

        parser = MathExtractor()
        parser.feed(clean_fragment)
        clipboard_html = "".join(parser.result)
        
        self.clipboard_html_cache = clipboard_html # 供复制按钮专用
        
        # 加上完整的 HTML 骨架
        # 特地为您补充了 KaTeX 的核心 CSS 样式库。
        # 这样即使您复制下来的这部分局部 HTML 没有涵盖原网站 head 里的样式，也能保障数学公式完美呈现和定位。
        complete_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            padding: 20px;
            font-size: 16px;
            line-height: 1.6;
        }}
        /* 强制重置复杂的网格或弹性布局，防止左右布局断裂或内容消失 */
        .conversation-container, .presented-response-container, .response-container, .response-container-content, .response-content {{
            display: block !important;
            padding-left: 0 !important;
            margin-left: 0 !important;
            width: auto !important;
            max-width: 100% !important;
        }}
        /* 强制隐藏由于移除头像引起的空白占位列 */
        .avatar-gutter, .avatar-container, bard-avatar {{
            display: none !important;
            width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        /* 强制隐藏 Gemini 遗留的隐藏发音辅助（TTS）容器。
           这些容器在原始 HTML 中往往带有几千像素的内联 height 空白占位，会导致大片虚空！ */
        .response-tts-container, tts-control, .tts {{
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        /* 强制隐藏 Show thinking（显示思考过程）相关的按钮和容器 */
        model-thoughts, .model-thoughts, .thoughts-container, .thoughts-wrapper {{
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        /* 防止暗黑模式样式缺失导致的白底白字隐形问题，给予通用文本颜色 */
        body {{
            color: #202124 !important;
            background: #ffffff !important;
        }}
        /* 代码块基础样式 */
        pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 85%;
            line-height: 1.45;
            margin-top: 0;
            margin-bottom: 16px;
            border: 1px solid #d0d7de;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
            border-radius: 0;
            display: inline;
            max-width: auto;
            border: 0;
            margin: 0;
            overflow: visible;
            line-height: inherit;
            word-wrap: normal;
        }}
        /* 行内代码样式 */
        code {{
            background-color: rgba(175,184,193,0.2);
            border-radius: 6px;
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
        }}
    </style>
</head>
<body>
<!-- 这里是正常用于带样式渲染的真实数据 -->
{clean_fragment}

<!-- 这是一个隐藏的模板，里面存放的是被 Python 强行剥离出原生 LaTeX 的纯净版本 -->
<template id="obsidian-clipboard-data">
{self.clipboard_html_cache}
</template>
</body>
</html>"""
        
        self.output_view.setHtml(complete_html)

    def html_to_markdown(self, html_content):
        if not html_content:
            return ""
        
        import re
        from bs4 import BeautifulSoup, NavigableString
        from markdownify import MarkdownConverter
        
        # 1. 强力预清洗：直接从字符串中移除 script, style, head, meta
        # 很多 AI 页面（如 Gemini）包含极其庞大的 JSON 数据块，必须优先剔除
        clean_html = re.sub(r'<(script|style|head|meta|link|noscript)[^>]*>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        # 处理可能的单标签
        clean_html = re.sub(r'<(meta|link|base)[^>]*>', '', clean_html, flags=re.IGNORECASE)
        
        # 2. 预处理：使用 lxml 快速解析
        soup = BeautifulSoup(clean_html, 'lxml')
        
        # 尝试只处理 body 内容
        target = soup.body if soup.body else soup
        
        # 3. 深度清理：移除所有非内容型标签 (如脚本、样式、导航、页脚等)
        # 将 button 也加入清理列表，因为它们通常是 UI 交互元素（如“复制代码”、“显示思维过程”）
        for tag in target(['script', 'style', 'template', 'noscript', 'header', 'footer', 'nav', 'svg', 'aside', 'button']):
            tag.decompose()
            
        # 3.1 针对 Gemini 的特殊清理：移除“显示思维过程 (Show thinking)”按钮或小容器
        # 仅针对包含相关文本的节点进行精准删除，不再向上递归查找过于宽泛的父容器
        for thinking in target.find_all(string=re.compile(r'Show thinking|Hide thinking|思维过程', re.I)):
            parent = thinking.parent
            if parent:
                # 仅在父容器是小型容器（如 span 或小的 div）时才删除，防止误伤大区
                if parent.name in ['span', 'div'] and not parent.find_all(['p', 'pre', 'li']):
                    parent.decompose()
                else:
                    # 如果父容器很大，只移除文本节点本身
                    thinking.extract()
                    
        # 3.2 针对具有显著思维过程特征的类名进行清理
        # 仅针对明确属于思维展示区的类名（常见于 Gemini 和 Claude）
        thought_classes = re.compile(r'thought-container|thinking-content|thought-block', re.I)
        for t_container in target.find_all(['div', 'section'], class_=thought_classes):
            t_container.decompose()
            
        # 4. 全局空白预处理：消除非 pre 块中的物理换行，防止干扰转换器逻辑
        # 模仿浏览器行为：HTML 中的换行通常被视为一个空格
        math_pattern = re.compile(r'math-(inline|block)|katex')
        for text_node in target.find_all(string=True):
            is_protected = False
            curr = text_node.parent
            while curr:
                if curr.name == 'pre' or math_pattern.search(" ".join(curr.get('class', []))):
                    is_protected = True
                    break
                curr = curr.parent
            
            if not is_protected:
                # 将物理换行替换为空格
                # 注意：这里仅处理 NavigableString 自带的文本
                if '\n' in text_node or '\r' in text_node:
                    new_text = text_node.replace('\n', ' ').replace('\r', ' ')
                    text_node.replace_with(NavigableString(new_text))
            
        # 5. 核心优化：预提取数学公式
        math_prot_store = []
        for math_el in target.find_all(['span', 'div'], class_=math_pattern):
            data_math = math_el.get('data-math')
            if not data_math:
                ann = math_el.find('annotation')
                if ann: data_math = ann.get_text().strip()
            
            if data_math:
                is_block = ('math-block' in math_el.get('class', []) or math_el.name == 'div')
                if is_block:
                    replacement = f"\n$$\n{data_math}\n$$\n"
                else:
                    replacement = f"${data_math}$"
                
                # 使用占位符防止 markdownify 转义 $ 和 _
                proto_id = f"MATHPROTO{len(math_prot_store)}MATH"
                math_prot_store.append((proto_id, replacement))
                math_el.replace_with(NavigableString(proto_id))
            elif 'katex-html' in math_el.get('class', []):
                # 移除展示用的 HTML 节点，保留上面的数据节点（或已替换为协议 ID）
                math_el.decompose()

        # 5. 配置 Markdown 转换器
        class ObsidianConverter(MarkdownConverter):
            def convert_br(self, el, text, parent_tags):
                # 返回纯净的 \n。预览时的换行由 marked 的 breaks: true 选项处理。
                return "\n"
            
            def convert_li(self, el, text, parent_tags):
                content = text.strip()
                if not content: return ""
                lines = [l for l in content.split('\n') if l.strip()]
                if not lines: return ""
                indented = lines[0]
                if len(lines) > 1:
                    indented += "\n" + "\n".join(["  " + l for l in lines[1:]])
                return f"\n- {indented}\n"

            def convert_pre(self, el, text, parent_tags):
                # 使用 deepcopy 确保完全克隆
                import copy
                temp_el = copy.deepcopy(el)
                
                # 显式处理换行标签，防止 get_text() 丢失换行或过度分行
                for br in temp_el.find_all('br'):
                    br.replace_with('\n')
                for block in temp_el.find_all(['div', 'p']):
                    if block.next_sibling:
                        block.insert_after('\n')
                
                code = temp_el.find('code')
                lang = ""
                if code:
                    classes = code.get('class', [])
                    for c in classes:
                        if c.startswith('language-'):
                            lang = c[9:]
                            break
                    content = code.get_text()
                else:
                    content = temp_el.get_text()
                
                return f"\n```{lang}\n{content.strip()}\n```\n"

        converter = ObsidianConverter(heading_style="ATX", bullets="-")
        md = converter.convert_soup(target)
        
        # 还原数学公式占位符 (此时 md 已经生成，不会再被转义)
        for proto_id, original in math_prot_store:
            md = md.replace(proto_id, original)
        
        # 6. 后处理：最终清理（移除可能的 JS 残留，不再过分压缩空行）
        md = md.replace('\r\n', '\n').replace('\r', '\n')
        lines = [l.rstrip() for l in md.split('\n')]
        
        final_lines = []
        for l in lines:
            # 过滤掉明显的非正文行 (例如过长的 JSON 或代码残留)
            if len(l) > 100 and (l.count('{') + l.count(':') + l.count('"')) > len(l) * 0.2:
                # 额外检查：如果是 WIZ_global_data 或类似脚本关键字
                if "WIZ_global_data" in l or "SignOutOptions" in l:
                    continue
                # 如果是普通的 Markdown 语法且包含空格，则保留（防止误伤代码块）
                if " " not in l:
                    continue
                    
            final_lines.append(l)
        
        res = "\n".join(final_lines).strip()
        # 仅压缩 3 个或以上的空行为 2 个（即保留最多一个空行），防止过分分段
        res = re.sub(r'\n{3,}', '\n\n', res)
        # 针对独立数学公式，移除上下的空行（直接贴合正文）
        res = re.sub(r'\n\s*\n\$\$', '\n$$', res)
        res = re.sub(r'\$\$\n\s*\n', '$$\n', res)
        return res

    def generate_preview_html(self, markdown_text):
        import base64
        # 使用 Base64 编码防止 Markdown 中的特殊字符 (如 </script>) 破坏预览页面的 JS 结构
        md_base64 = base64.b64encode(markdown_text.encode('utf-8')).decode('utf-8')
        
        template = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/11.1.1/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <style>
        body {
            font-family: "霞鹜文楷等宽 GB 屏幕阅读版", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            padding: 20px;
            max-width: 95%;
            margin: 0 auto;
            background-color: #fff;
        }
        pre {
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            white-space: pre !important; 
        }
        code {
            font-family: "霞鹜文楷等宽 GB 屏幕阅读版", ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
            background-color: rgba(175, 184, 193, 0.2);
            padding: 0.2em 0.4em;
            border-radius: 6px;
        }
        pre code {
            background-color: transparent;
            padding: 0;
            white-space: pre !important; 
            display: block; 
        }
        .katex-display {
            margin: 0.3em 0 !important;
        }
        blockquote {
            border-left: 0.25em solid #d0d7de;
            color: #57606a;
            padding: 0 1em;
            margin: 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }
        th, td {
            border: 1px solid #d0d7de;
            padding: 6px 13px;
        }
        tr:nth-child(even) {
            background-color: #f6f8fa;
        }
    </style>
</head>
<body>
    <div id="content">正在加载预览...</div>
    <script>
        (function() {
            try {
                // 解码 Base64 数据 (处理 UTF-8)
                const b64 = "{md_base64}";
                const bin = atob(b64);
                const bytes = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) {
                    bytes[i] = bin.charCodeAt(i);
                }
                const md = new TextDecoder("utf-8").decode(bytes);

                const contentDiv = document.getElementById('content');
                
                // 1. 保护数学公式 (防止 marked 解析特殊符号如 _ 或 ^)
                let mathStore = [];
                let processed = md.replace(/(\$\$[\s\S]*?\$\$|\$[^\$\n]+?\$)/g, function(match) {
                    mathStore.push(match);
                    return '%%MATH' + (mathStore.length - 1) + '%%';
                });
                
                // 2. 解析 Markdown (启用 breaks: true)
                // 在解析前，针对块级数学占位符，暂时减掉其前后的主换行，
                // 以防止 breaks: true 产生额外的 <br> 导致看上去有空行。
                let tightMd = processed.replace(/\n(%%MATH\d+%%)\n/g, '$1');
                tightMd = tightMd.replace(/^(%%MATH\d+%%)\n/g, '$1');
                tightMd = tightMd.replace(/\n(%%MATH\d+%%)$/g, '$1');
                
                let html = marked.parse(tightMd, { gfm: true, breaks: true });
                
                // 3. 还原数学公式
                for (let i = 0; i < mathStore.length; i++) {
                    const key = '%%MATH' + i + '%%';
                    html = html.split(key).join(mathStore[i]);
                }
                
                contentDiv.innerHTML = html;

                // 4. 代码高亮
                if (typeof hljs !== 'undefined') {
                    hljs.highlightAll();
                }
                
                // 5. 渲染数学公式 (KaTeX)
                if (typeof renderMathInElement !== 'undefined') {
                    renderMathInElement(contentDiv, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false},
                            {left: '\\(', right: '\\)', display: false},
                            {left: '\\[', right: '\\]', display: true}
                        ],
                        throwOnError: false
                    });
                }
            } catch (e) {
                document.getElementById('content').innerHTML = 
                    '<div style="color:red; padding: 20px; border: 1px solid red;">' +
                    '<h3>渲染错误</h3>' +
                    '<pre>' + e.toString() + '</pre>' +
                    '</div>';
            }
        })();
    </script>
</body>
</html>"""
        return template.replace("{md_base64}", md_base64)

    def update_html(self):
        # 1. 提取清理
        raw_input = self.input_text.toPlainText()
        if not raw_input.strip():
            return
            
        import re
        # 针对 Bard / Gemini 的特殊清理（保持原逻辑）
        clean_fragment = raw_input
        if '<!--StartFragment-->' in raw_input:
            clean_fragment = raw_input.split('<!--StartFragment-->')[-1]
        if '<!--EndFragment-->' in clean_fragment:
            clean_fragment = clean_fragment.split('<!--EndFragment-->')[0]
        
        # 2. 转换 Markdown 并缓存
        try:
            self.markdown_cache = self.html_to_markdown(clean_fragment)
        except Exception as e:
            self.markdown_cache = f"Conversion Error: {str(e)}"
        
        # 3. 渲染预览
        preview_html = self.generate_preview_html(self.markdown_cache)
        self.output_view.setHtml(preview_html)

    def copy_output(self):
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QGuiApplication
        
        if not hasattr(self, 'markdown_cache') or not self.markdown_cache:
            return
            
        mime_data = QMimeData()
        # 此时只把转换好的 Markdown 布置到剪贴板，因为预览只是为了视觉核对
        mime_data.setText(self.markdown_cache)
        QGuiApplication.clipboard().setMimeData(mime_data)

    def inspect_clipboard(self):
        inspector = ClipboardInspector(self)
        inspector.exec()

    def process_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        # 记录一份到检测器日志（可选，这里直接提取重要的数据）
        if mime_data.hasHtml():
            html_content = mime_data.html()
            self.input_text.setPlainText(html_content)
        elif mime_data.hasText():
            text_content = mime_data.text()
            self.input_text.setPlainText(text_content)
        else:
            # 如果没有标准 HTML/Text，尝试查找所有可能的 text 相关 format
            formats = mime_data.formats()
            for fmt in formats:
                if 'html' in fmt.lower() or 'text' in fmt.lower():
                    data = mime_data.data(fmt)
                    text = bytes(data).decode('utf-8', errors='replace')
                    self.input_text.setPlainText(text)
                    return
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HtmlRichTextConverter()
    window.show()
    sys.exit(app.exec())
