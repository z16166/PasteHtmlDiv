# PasteHtmlDiv

PasteHtmlDiv 是一款基于 PySide6 (Qt for Python) 构建的桌面小工具。主要作用是将复制自网页（如 Gemini / Google Bard 对话界面）的带有复杂 DOM 和样式结构的 HTML 代码片段进行清理、重排与转换，使其能够以格式完美、排版紧凑的富文本（Rich Text）和原生 LaTeX 代码形式粘贴到 Obsidian、Microsoft Word 等软件中。

## 🎯 核心痛点与功能
在从 AI 聊天界面复制对话时，经常会遇到以下令人头疼的排版问题：
1. **庞大的空白占位**：由于头像、状态图标占领独立栅格，复制后会留下大片虚无的空白列。
2. **隐藏辅助元素的现形**：原本被网页通过绝对定位和负边界隐藏的“发音 (TTS) 容器”和“思考过程按钮”，在其他编辑器粘贴时经常暴露出高达几千像素的惊人空白。
3. **数学公式乱码**：复杂的数学公式（KaTeX 渲染出来的上百个互相嵌套的 `<span>` 字符）一旦脱离原始 CSS 环境，就会变成一长串天书乱码；同时 Markdown 笔记软件（如 Obsidian 的 MathJax）也无法识别这类已经被预渲染的非标准标签代码。

**PasteHtmlDiv 的解决方案：**
- **强效 CSS 降维打击**：在内部通过 PySide6 的 QWebEngineView 模拟无头浏览器进行渲染。注入了高优先级 (`!important`) 的自定义 CSS，强制剥除多余的辅助占位、头像列占位，消除所有因 Flex/Grid 弹性失效导致的不合理断层空白，恢复干净紧凑的左对齐文档流。
- **底层 DOM 解析与精确打击**：避免使用脆弱的正则表达式破坏 HTML 的层级结构。内置了一套基于 Python 原生 `HTMLParser` 的栈式解析器，专门瞄准 KaTeX 嵌套矩阵。
- **双轨制提取引擎**：
  * **视觉层**：在渲染视窗中，依然给用户呈现原汁原味的、带高亮和复杂层级的数学公式排版，赏心悦目。
  * **剪贴板层**：在内存中利用解析器剥离无效数学结构，逆向提取储存在 `data-math` 属性里的最纯粹的 LaTeX 原代码（并自动根据行间或独行添加 `$` 和 `$$` 占位符）。当用户点击“全选复制”按钮时，利用 JavaScript 底层 `copy` 事件拦截器，神不知鬼不觉地把这段专属的洁净数据直接塞入操作系统的 HTML 富文本前缀剪贴板流中，让 Obsidian 一秒顺滑识别并重新原生渲染。

## 🚀 使用方法

### 1环境配置
请确保你的电脑上安装了 Python 3.10 及以上版本。之后安装项目的核心依赖 `PySide6` 及 `PySide6-WebEngine`。

```bash
pip install -r requirements.txt
```

### 2启动工具
```bash
python main.py
```

### 3复制与转换
1. 在浏览器里（如打开 F12 或选中内容）复制包含 `<div>...</div>` 等复杂层级的 HTML 片段文本。
2. 将其直接粘贴到 PasteHtmlDiv 的左侧输入框中。
3. 工具的右侧窗口将利用 WebEngine 核心对其进行静默处理和降级渲染预览。
4. 点击底部的 **“将右侧结果全选并复制到剪贴板”**。
5. 去到任何编辑器（如 Obsidian，Word 等）里按下 `Ctrl+V`，享受丝滑的纯粹富文本！

## 👨‍💻 技术栈
- Python 3.x
- PySide6 (GUI Toolkit)
- QtWebEngine (Chromium runtime for DOM manipulation and execution)

## 📄 开源协议
MIT License
