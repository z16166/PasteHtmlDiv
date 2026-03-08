# PasteHtmlDiv

PasteHtmlDiv 是一款基于 PySide6 (Qt for Python) 构建的桌面小工具。主要作用是将复制自Gemini网页版、Chatgpt网页版的单个聊天会话里的内容提取出来，还原其中的Katex数学公式，方便粘贴到Obsidian等支持markdown和Latex的软件中进行保存。


## 🚀 使用方法
首先在Chrome等浏览器中选中Gemini或者Chatgpt的某个聊天会话，查看整个会话从头至尾的详细内容。
按F12打开浏览器的DevTools，复制<html></html>这个顶层节点，粘贴到本工具左侧的文本框里。
然后点击本工具下面的复制按钮，再粘贴到Obsidian等工具中即可。

### 1. 环境配置
请确保你的电脑上安装了 Python 3.10 及以上版本。之后安装项目的核心依赖：

```bash
pip install -r requirements.txt
```

### 2. 启动工具
```bash
pythonw main.py
```

## 环境要求

-   Python 3.10+

## 📄 开源协议
MIT License
