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
        self.input_text.setPlaceholderText("在这里粘贴包含 <div> 和 </div> 等标签的 HTML 代码片段...")
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
                if self.ignore_stack:
                    if self.ignore_stack[-1] == tag:
                        self.ignore_stack.pop()
                    return
                if self.math_stack:
                    # 匹配到结束标签，出栈。如果栈空了，说明最外层的 math 节点结束了
                    if self.math_stack[-1] == tag:
                        self.math_stack.pop()
                    return
                self.result.append(f"</{tag}>")

            def handle_data(self, data):
                if not self.math_stack and not self.ignore_stack:
                    self.result.append(data)
                    
            def handle_entityref(self, name):
                if not self.math_stack and not self.ignore_stack:
                    self.result.append(f"&{name};")
                    
            def handle_charref(self, name):
                if not self.math_stack and not self.ignore_stack:
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
    </style>
</head>
<body>
<!-- 这里是正常用于带样式渲染的真实数据 -->
{clean_fragment}

<!-- 这是一个隐藏的模板，里面存放的是被 Python 强行剥离出原生 LaTeX 的纯净版本 -->
<template id="obsidian-clipboard-data">
{self.clipboard_html_cache}
</template>

<!-- 注入 JavaScript 拦截内核的 Copy 动作，强行将我们提取的 LaTeX 喂给操作系统的富文本剪贴板 -->
<script>
document.addEventListener('copy', function(e) {{
    var template = document.getElementById('obsidian-clipboard-data');
    if (template) {{
        var htmlContent = template.innerHTML;
        var textContent = template.textContent || template.innerText;
        // 构建标准的最简 HTML 包裹，让 Word 或 Obsidian 能正确识别 HTML 头
        var finalHtml = "<html><body>" + htmlContent + "</body></html>";
        
        e.clipboardData.setData('text/html', finalHtml);
        e.clipboardData.setData('text/plain', textContent);
        e.preventDefault(); // 阻止浏览器本身的默认拷贝（即阻止拷贝那些用于视觉渲染的复杂节点）
    }}
}});
</script>
</body>
</html>"""
        
        self.output_view.setHtml(complete_html)

    def copy_output(self):
        from PySide6.QtCore import QTimer
        
        # 将焦点设置到网页视图，防止由于按钮具有焦点而导致复制动作被内核忽略
        self.output_view.setFocus()
        self.output_view.page().triggerAction(QWebEnginePage.WebAction.SelectAll)
        self.output_view.page().triggerAction(QWebEnginePage.WebAction.Copy)
        
        # 延迟 100 毫秒后取消全选。由于 Chromium 内核处理复制是异步且在独立进程的，
        # 如果立刻执行 Unselect，会导致复制毫无效果，所以之前才不生效。
        # 这里给内核一点时间把带样式的富文本完美推入 Windows 剪贴板。
        QTimer.singleShot(100, lambda: self.output_view.page().triggerAction(QWebEnginePage.WebAction.Unselect))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HtmlRichTextConverter()
    window.show()
    sys.exit(app.exec())
