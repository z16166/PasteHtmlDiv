import sys
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, 
                               QVBoxLayout, QPlainTextEdit, QPushButton, QSplitter)
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

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
        
        splitter.addWidget(self.input_text)
        splitter.addWidget(self.output_view)
        
        splitter.setSizes([550, 550])
        main_layout.addWidget(splitter)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
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

    def copy_output(self):
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QGuiApplication
        
        # 100% 稳定的同步注入方案：直接在 Python 层操作剪贴板
        # 彻底废弃 SelectAll -> Copy -> Unselect 的异步不确定流程
        mime_data = QMimeData()
        
        # 构建标准 HTML 包裹，确保 Obsidian 能识别
        final_html = f"<html><body>{self.clipboard_html_cache}</body></html>"
        
        # 注入富文本（HTML）和纯文本（LaTeX）
        mime_data.setHtml(final_html)
        mime_data.setText(self.clipboard_html_cache)
        
        # 立即写入系统剪贴板（同步操作，无延迟，无截断）
        QGuiApplication.clipboard().setMimeData(mime_data)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HtmlRichTextConverter()
    window.show()
    sys.exit(app.exec())
