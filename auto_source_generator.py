# -*- coding: utf-8 -*-
"""
阅读书源自动生成器 - Python版
自动分析网站结构，生成符合阅读3.0格式的书源JSON
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import re
from urllib.parse import urljoin, urlparse, urlencode, parse_qs
from html.parser import HTMLParser
import os
import json
from datetime import datetime


class HTMLTextExtractor(HTMLParser):
    """HTML文本提取器"""
    def __init__(self):
        super().__init__()
        self.texts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.in_script = True

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.in_script = False

    def handle_data(self, data):
        if not self.in_script:
            self.texts.append(data.strip())

    def get_text(self):
        return ' '.join(t for t in self.texts if t)


class JSOUPRuleExtractor:
    """JSOUP规则提取器 - 从HTML结构中提取阅读书源规则"""
    
    def __init__(self, html, base_url=''):
        self.html = html
        self.base_url = base_url
        self.elements = self._parse_elements()
    
    def _parse_elements(self):
        """解析HTML元素结构"""
        elements = []
        
        class ElementParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.elements = []
                self.current_path = []
                self.depth = 0
            
            def handle_starttag(self, tag, attrs):
                attrs_dict = {k.lower(): v for k, v in attrs}
                element = {
                    'tag': tag,
                    'class': attrs_dict.get('class', ''),
                    'id': attrs_dict.get('id', ''),
                    'href': attrs_dict.get('href', ''),
                    'src': attrs_dict.get('src', ''),
                    'data_src': attrs_dict.get('data-src', ''),
                    'text': '',
                    'depth': self.depth
                }
                self.elements.append(element)
                self.current_path.append(element)
                self.depth += 1
            
            def handle_endtag(self, tag):
                if self.current_path:
                    self.current_path.pop()
                self.depth = max(0, self.depth - 1)
            
            def handle_data(self, data):
                if self.current_path and data.strip():
                    self.current_path[-1]['text'] += ' ' + data.strip()
        
        parser = ElementParser()
        parser.feed(self.html)
        return parser.elements
    
    def find_book_list_container(self):
        """查找书籍列表容器"""
        common_containers = [
            ('ul', 'txt-list'), ('div', 'result-list'), ('div', 'book-list'),
            ('ul', 'book-list'), ('div', 'list'), ('ul', 'list'),
            ('table', ''), ('div', 'item-list'), ('div', 'search-result')
        ]
        
        for tag, class_name in common_containers:
            for el in self.elements:
                if el['tag'] == tag:
                    if class_name and class_name in el['class']:
                        return self._build_jsoup_rule(el)
                    elif not class_name and tag == 'table':
                        return 'table@tag.tr'
        
        return 'tag.li'
    
    def _build_jsoup_rule(self, element):
        """构建JSOUP规则"""
        if element['id']:
            return f"id.{element['id']}"
        elif element['class']:
            classes = element['class'].split()[0]
            return f"class.{classes}"
        else:
            return f"tag.{element['tag']}"
    
    def extract_search_rules(self):
        """提取搜索页规则"""
        book_list = self.find_book_list_container()
        
        name_rule = self._find_name_rule()
        author_rule = self._find_author_rule()
        cover_rule = self._find_cover_rule()
        book_url_rule = self._find_book_url_rule()
        last_chapter_rule = self._find_last_chapter_rule()
        kind_rule = self._find_kind_rule()
        intro_rule = self._find_intro_rule()
        
        return {
            'bookList': book_list,
            'name': name_rule,
            'author': author_rule,
            'coverUrl': cover_rule,
            'bookUrl': book_url_rule,
            'lastChapter': last_chapter_rule,
            'kind': kind_rule,
            'intro': intro_rule,
            'wordCount': ''
        }
    
    def _find_name_rule(self):
        """查找书名规则"""
        patterns = [
            ('class', 'bookname'), ('class', 'name'), ('class', 'title'),
            ('class', 's2'), ('class', 'book-name'), ('tag', 'h3'), ('tag', 'h4')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    if el['tag'] == 'a':
                        return f"class.{value}@text"
                    else:
                        return f"class.{value}@tag.a@text"
                elif type_ == 'tag' and el['tag'] == value:
                    if el['text'] and len(el['text']) < 50:
                        return f"tag.{value}@tag.a@text"
        
        return ''
    
    def _find_author_rule(self):
        """查找作者规则"""
        patterns = [
            ('class', 'author'), ('class', 's4'), ('class', 'au'),
            ('class', 'writer'), ('class', 'zz')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    text = el['text'].strip()
                    if '作者' in text or len(text) < 20:
                        rule = f"class.{value}@text"
                        if '作者' in text:
                            rule += '##作者：##'
                        return rule
        
        return ''
    
    def _find_cover_rule(self):
        """查找封面规则"""
        for el in self.elements:
            if el['tag'] == 'img':
                if el['src'] and ('cover' in el['class'] or 'cover' in el['src']):
                    return 'img@src'
                elif el['data_src']:
                    return 'img@data-src'
        
        for el in self.elements:
            if el['tag'] == 'img' and el['src']:
                return 'img@src'
        
        return ''
    
    def _find_book_url_rule(self):
        """查找详情页URL规则"""
        for el in self.elements:
            if el['tag'] == 'a' and el['href']:
                text = el['text'].strip()
                if text and len(text) < 50 and 'javascript' not in el['href'].lower():
                    if '/book/' in el['href'] or '/novel/' in el['href'] or '/xiaoshuo/' in el['href']:
                        return 'tag.a@href'
        
        return 'tag.a@href'
    
    def _find_last_chapter_rule(self):
        """查找最新章节规则"""
        patterns = [
            ('class', 's3'), ('class', 'last'), ('class', 'chapter'),
            ('class', 'new'), ('class', 'update')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    if el['tag'] == 'a':
                        return f"class.{value}@tag.a@text"
                    else:
                        text = el['text'].strip()
                        if '章' in text or '节' in text:
                            return f"class.{value}@text"
        
        return ''
    
    def _find_kind_rule(self):
        """查找分类规则"""
        patterns = [
            ('class', 's1'), ('class', 'kind'), ('class', 'category'),
            ('class', 'type'), ('class', 'sort')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    text = el['text'].strip()
                    if text and len(text) < 20:
                        rule = f"class.{value}@text"
                        if '[' in text or '【' in text:
                            rule += '##[\\[\\]【】]##'
                        return rule
        
        return ''
    
    def _find_intro_rule(self):
        """查找简介规则"""
        patterns = [
            ('class', 'intro'), ('class', 'desc'), ('class', 'summary'),
            ('class', 'jianjie'), ('class', 'jj')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    if el['text'] and len(el['text']) > 20:
                        return f"class.{value}@text"
        
        return ''
    
    def extract_book_info_rules(self):
        """提取详情页规则"""
        name_rule = self._find_detail_name_rule()
        author_rule = self._find_detail_author_rule()
        cover_rule = self._find_detail_cover_rule()
        intro_rule = self._find_detail_intro_rule()
        kind_rule = self._find_detail_kind_rule()
        last_chapter_rule = self._find_detail_last_chapter_rule()
        word_count_rule = self._find_word_count_rule()
        toc_url_rule = self._find_toc_url_rule()
        
        return {
            'init': '',
            'name': name_rule,
            'author': author_rule,
            'coverUrl': cover_rule,
            'intro': intro_rule,
            'kind': kind_rule,
            'lastChapter': last_chapter_rule,
            'wordCount': word_count_rule,
            'tocUrl': toc_url_rule
        }
    
    def _find_detail_name_rule(self):
        """查找详情页书名规则"""
        patterns = [
            ('class', 'bookname'), ('class', 'name'), ('class', 'title'),
            ('id', 'info'), ('tag', 'h1')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    return f"class.{value}@text"
                elif type_ == 'id' and el['id'] == value:
                    return f"id.{value}@tag.h1@text"
                elif type_ == 'tag' and el['tag'] == value:
                    text = el['text'].strip()
                    if text and len(text) < 50:
                        return f"tag.{value}@text"
        
        return ''
    
    def _find_detail_author_rule(self):
        """查找详情页作者规则"""
        for el in self.elements:
            text = el['text'].strip()
            if '作者' in text and len(text) < 50:
                if el['class']:
                    rule = f"class.{el['class'].split()[0]}@text"
                    rule += '##作者：##'
                    return rule
                elif el['tag'] == 'p' or el['tag'] == 'span':
                    return f"tag.{el['tag']}@text##作者：##"
        
        return ''
    
    def _find_detail_cover_rule(self):
        """查找详情页封面规则"""
        for el in self.elements:
            if el['tag'] == 'img':
                if el['src'] and ('cover' in el['class'] or 'cover' in el['src'] or 'book' in el['src']):
                    return 'img@src'
                elif el['data_src']:
                    return 'img@data-src'
        
        for el in self.elements:
            if el['tag'] == 'img' and el['id'] and 'cover' in el['id']:
                return f"id.{el['id']}@src"
        
        return ''
    
    def _find_detail_intro_rule(self):
        """查找详情页简介规则"""
        patterns = [
            ('class', 'intro'), ('class', 'desc'), ('class', 'summary'),
            ('class', 'jianjie'), ('id', 'intro'), ('id', 'desc')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    if el['text'] and len(el['text']) > 20:
                        return f"class.{value}@text"
                elif type_ == 'id' and el['id'] == value:
                    if el['text'] and len(el['text']) > 20:
                        return f"id.{value}@text"
        
        return ''
    
    def _find_detail_kind_rule(self):
        """查找详情页分类规则"""
        for el in self.elements:
            text = el['text'].strip()
            if ('分类' in text or '类型' in text) and len(text) < 30:
                if el['class']:
                    return f"class.{el['class'].split()[0]}@text##分类：|类型：##"
        
        return ''
    
    def _find_detail_last_chapter_rule(self):
        """查找详情页最新章节规则"""
        for el in self.elements:
            text = el['text'].strip()
            if ('最新' in text or '更新' in text) and ('章' in text or '节' in text):
                if el['tag'] == 'a':
                    if el['class']:
                        return f"class.{el['class'].split()[0]}@tag.a@text"
                    return 'tag.a@text'
                elif el['class']:
                    return f"class.{el['class'].split()[0]}@text##最新：|更新：##"
        
        return ''
    
    def _find_word_count_rule(self):
        """查找字数规则"""
        for el in self.elements:
            text = el['text'].strip()
            if '字' in text and ('万' in text or len(text) < 20):
                if el['class']:
                    return f"class.{el['class'].split()[0]}@text"
        
        return ''
    
    def _find_toc_url_rule(self):
        """查找目录URL规则"""
        for el in self.elements:
            text = el['text'].strip()
            if el['tag'] == 'a' and el['href']:
                if any(x in text for x in ['点击阅读', '开始阅读', '查看目录', '全部目录', '章节目录', '阅读']):
                    if el['class']:
                        return f"class.{el['class'].split()[0]}@href"
                    return 'tag.a@href'
        
        return ''
    
    def extract_toc_rules(self):
        """提取目录页规则"""
        chapter_list_rule = self._find_chapter_list_rule()
        is_reverse = self._check_chapter_order()
        
        if is_reverse:
            chapter_list_rule = '-' + chapter_list_rule
        
        next_toc_url_rule = self._find_next_toc_url_rule()
        
        return {
            'chapterList': chapter_list_rule,
            'chapterName': '@text',
            'chapterUrl': '@href',
            'nextTocUrl': next_toc_url_rule,
            'preUpdateJs': ''
        }, is_reverse
    
    def _find_chapter_list_rule(self):
        """查找章节列表规则"""
        patterns = [
            ('class', 'chapter'), ('class', 'list'), ('class', 'catalog'),
            ('id', 'list'), ('id', 'chapter'), ('tag', 'dd')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'class' and value in el['class']:
                    if el['tag'] == 'div' or el['tag'] == 'ul':
                        return f"class.{el['class'].split()[0]}@tag.a"
                    elif el['tag'] == 'dl':
                        return f"class.{el['class'].split()[0]}@tag.dd@tag.a"
                elif type_ == 'id' and value in el['id']:
                    return f"id.{el['id']}@tag.a"
                elif type_ == 'tag' and el['tag'] == value:
                    return f"tag.{value}@tag.a"
        
        return 'tag.dd@tag.a'
    
    def _check_chapter_order(self):
        """检查章节顺序"""
        chapter_texts = []
        for el in self.elements:
            text = el['text'].strip()
            if '第' in text and ('章' in text or '节' in text) and len(text) < 50:
                chapter_texts.append(text)
        
        if len(chapter_texts) >= 2:
            first = chapter_texts[0]
            last = chapter_texts[-1]
            
            first_num = self._extract_chapter_number(first)
            last_num = self._extract_chapter_number(last)
            
            if first_num and last_num and first_num > last_num:
                return True
        
        return False
    
    def _extract_chapter_number(self, text):
        """提取章节号"""
        match = re.search(r'第(\d+)', text)
        if match:
            return int(match.group(1))
        
        chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                       '百': 100, '千': 1000}
        
        match = re.search(r'第([一二三四五六七八九十百千]+)', text)
        if match:
            num_str = match.group(1)
            num = 0
            for char in num_str:
                if char in chinese_nums:
                    num += chinese_nums[char]
            return num
        
        return None
    
    def _find_next_toc_url_rule(self):
        """查找目录下一页规则"""
        for el in self.elements:
            text = el['text'].strip()
            if el['tag'] == 'a' and el['href']:
                if '下一页' in text or 'next' in text.lower():
                    if el['class']:
                        return f"class.{el['class'].split()[0]}@href"
                    return 'tag.a@href'
        
        return ''
    
    def extract_content_rules(self):
        """提取正文页规则"""
        content_rule = self._find_content_rule()
        next_content_url_rule = self._find_next_content_url_rule()
        replace_regex = self._find_ads_pattern()
        
        return {
            'content': content_rule,
            'nextContentUrl': next_content_url_rule,
            'replaceRegex': replace_regex,
            'webJs': '',
            'sourceRegex': ''
        }
    
    def _find_content_rule(self):
        """查找正文规则"""
        patterns = [
            ('id', 'content'), ('id', 'chaptercontent'), ('class', 'content'),
            ('class', 'chapter-content'), ('class', 'read-content'), ('class', 'txt')
        ]
        
        for type_, value in patterns:
            for el in self.elements:
                if type_ == 'id' and el['id'] == value:
                    return f"id.{value}@textNodes"
                elif type_ == 'class' and value in el['class']:
                    return f"class.{el['class'].split()[0]}@textNodes"
        
        return 'id.content@textNodes'
    
    def _find_next_content_url_rule(self):
        """查找正文下一页规则"""
        for el in self.elements:
            text = el['text'].strip()
            if el['tag'] == 'a' and el['href']:
                if '下一页' in text or '下一章' in text or 'next' in text.lower():
                    if el['class']:
                        return f"class.{el['class'].split()[0]}@href"
                    return 'tag.a@href'
        
        return ''
    
    def _find_ads_pattern(self):
        """查找广告模式"""
        ads_keywords = [
            '本章未完', '点击下一页', '手机阅读', '最新网址',
            '请记住', '首发域名', '笔趣阁', '阅读更多'
        ]
        
        found_ads = []
        for keyword in ads_keywords:
            if keyword in self.html:
                found_ads.append(keyword)
        
        if found_ads:
            return '##' + '|'.join(found_ads) + '.*?##'
        
        return ''


class AutoSourceGenerator:
    """阅读书源自动生成器"""

    FIXED_WORDS = {'book', 'novel', 'read', 'view', 'article', 'info', 'detail', 'index', 'page',
                   'www', 'm', 'wap', 'mobile', 'api', 'static', 'css', 'js', 'img', 'images',
                   'boshi', 'sort', 'list', 'category', 'tag', 'author', 'books', 'xiaoshuo'}

    def __init__(self, root):
        self.root = root
        self.root.title("阅读书源自动生成器")
        self.root.geometry("900x850")
        self.root.minsize(900, 850)

        self.debug_dir = 'debug_yuedu_source'
        os.makedirs(self.debug_dir, exist_ok=True)

        self.log_file = 'debug_yuedu.log'
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write('')

        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        for i in range(10):
            self.main_frame.rowconfigure(i, weight=1 if i == 7 else 0)

        self._create_ui()
        self.generated_source = None

    def _create_ui(self):
        """创建用户界面"""
        input_frame = ttk.LabelFrame(self.main_frame, text="输入参数", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="网站URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(input_frame, textvariable=self.url_var, foreground='gray')
        self.url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        self.url_entry.insert(0, "输入网站首页URL")
        
        def on_url_entry_click(event):
            if self.url_var.get() == "输入网站首页URL":
                self.url_var.set("")
                self.url_entry.config(foreground='black')
        
        def on_url_entry_leave(event):
            if not self.url_var.get():
                self.url_var.set("输入网站首页URL")
                self.url_entry.config(foreground='gray')
        
        self.url_entry.bind("<FocusIn>", on_url_entry_click)
        self.url_entry.bind("<FocusOut>", on_url_entry_leave)

        ttk.Label(input_frame, text="搜索关键词:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.keyword_var = tk.StringVar(value="我的")
        self.keyword_entry = ttk.Entry(input_frame, textvariable=self.keyword_var)
        self.keyword_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)

        self.start_btn = ttk.Button(button_frame, text="开始生成", command=self.start_generate, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(button_frame, text="清空日志", command=self.clear_log, width=15)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = ttk.Button(button_frame, text="保存书源", command=self.save_source, width=15, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var, font=('Arial', 10, 'bold'))
        self.status_label.grid(row=2, column=0, columnspan=2, pady=5)

        log_frame = ttk.LabelFrame(self.main_frame, text="运行日志", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        result_frame = ttk.LabelFrame(self.main_frame, text="生成的阅读书源JSON", padding="5")
        result_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        self.result_text = scrolledtext.ScrolledText(result_frame, height=12, wrap=tk.WORD)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def log(self, message, step=None):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{step}] " if step else ""
        log_line = f"[{timestamp}] [YueduSource] {prefix}{message}\n"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)

        self.log_text.insert(tk.END, log_line)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def log_params(self, title, params):
        """记录参数"""
        self.log(f"{'='*20} {title} {'='*20}")
        for key, value in params.items():
            self.log(f"  {key}: {value}")

    def step(self, step_name):
        """记录步骤"""
        self.log("")
        self.log("=" * 50)
        self.log(f"步骤: {step_name}")
        self.log("=" * 50)

    def save_html(self, filename, content):
        """保存HTML文件"""
        try:
            filepath = os.path.join(self.debug_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log(f"已保存网页内容到: {filename}")
        except Exception as e:
            self.log(f"保存文件失败 {filename}: {e}")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write('')

    def get_headers(self, url=None):
        """获取请求头"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        if url:
            parsed = urlparse(url)
            headers['Host'] = parsed.netloc
        return headers

    def _check_js_redirect(self, html, base_url):
        """检测JavaScript重定向"""
        if len(html) < 500:
            js_redirect = re.search(r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
            if js_redirect:
                redirect_path = js_redirect.group(1)
                if redirect_path.startswith('http'):
                    return redirect_path
                elif redirect_path.startswith('/'):
                    parsed = urlparse(base_url)
                    return f"{parsed.scheme}://{parsed.netloc}{redirect_path}"
                else:
                    return base_url.rstrip('/') + '/' + redirect_path
        return None

    def fetch_page(self, url, charset=None, max_retries=3):
        """获取页面"""
        try:
            session = requests.Session()
            retry_count = 0
            
            while retry_count < max_retries:
                response = session.get(url, headers=self.get_headers(url), timeout=15, allow_redirects=True)

                if charset:
                    response.encoding = charset
                else:
                    if response.apparent_encoding:
                        response.encoding = response.apparent_encoding
                    else:
                        response.encoding = 'utf-8'

                html = response.text
                
                js_redirect_url = self._check_js_redirect(html, url)
                if js_redirect_url:
                    self.log(f"检测到JavaScript重定向: {url} -> {js_redirect_url}")
                    url = js_redirect_url
                    retry_count += 1
                    continue
                
                if len(html) < 500:
                    self.log(f"HTML长度异常({len(html)}字符)，正在重试...")
                    retry_count += 1
                    continue
                
                return {
                    'success': True,
                    'html': html,
                    'charset': response.encoding,
                    'url': response.url
                }
            
            return {'success': False, 'error': '重试次数过多'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_page(self, url, data, charset='UTF-8'):
        """POST请求"""
        try:
            session = requests.Session()
            headers = self.get_headers(url)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            headers['Origin'] = urlparse(url).scheme + '://' + urlparse(url).netloc
            headers['Referer'] = url

            if charset.upper() in ['GBK', 'GB2312']:
                encoded_data = urlencode(data, encoding=charset)
                response = session.post(url, data=encoded_data, headers=headers, timeout=15)
            else:
                response = session.post(url, data=data, headers=headers, timeout=15)

            response.encoding = charset if charset else 'utf-8'

            return {
                'success': True,
                'html': response.text,
                'charset': response.encoding,
                'url': response.url
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def extract_site_name(self, html, url):
        """提取网站名称"""
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            for sep in ['-', '_', '|', '—']:
                if sep in title:
                    return title.split(sep)[0].strip()
            return title

        parsed = urlparse(url)
        domain = parsed.netloc
        return domain.replace('www.', '').replace('m.', '')

    def detect_charset(self, html, headers):
        """检测编码"""
        detected_charset = None
        
        content_type = headers.get('Content-Type', '')
        charset_match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
        if charset_match:
            detected_charset = charset_match.group(1).strip().lower()
        
        if detected_charset is None:
            charset_match = re.search(r'<meta[^>]+charset=["\']?([^"\' >\s]+)', html, re.IGNORECASE)
            if charset_match:
                detected_charset = charset_match.group(1).strip().lower()
        
        if detected_charset and ('gbk' in detected_charset or 'gb2312' in detected_charset):
            return 'GB2312'
        else:
            return 'UTF-8'

    def analyze_search_function(self, base_url, keyword='我的'):
        """分析搜索功能 - 生成阅读书源格式的搜索URL"""
        self.step("分析首页搜索功能")
        self.status_var.set("正在分析搜索功能...")

        result = self.fetch_page(base_url)
        if not result['success']:
            return {'success': False, 'error': f"获取首页失败: {result['error']}"}

        html = result['html']
        charset = self.detect_charset(html, {})

        self.save_html('01_首页.txt', html)
        self.log(f"首页HTML长度: {len(html)} 字符")

        from html.parser import HTMLParser
        
        class FormFinder(HTMLParser):
            def __init__(self):
                super().__init__()
                self.forms = []
                self.current_form = None
                self.in_form = False
                
            def handle_starttag(self, tag, attrs):
                attrs_dict = {k.lower(): v for k, v in attrs}
                
                if tag == 'form':
                    self.in_form = True
                    self.current_form = {
                        'action': attrs_dict.get('action', ''),
                        'method': attrs_dict.get('method', 'GET').upper(),
                        'inputs': [],
                        'hidden_params': {}
                    }
                elif tag == 'input' and self.in_form:
                    input_type = attrs_dict.get('type', 'text').lower()
                    input_name = attrs_dict.get('name', '')
                    input_value = attrs_dict.get('value', '')
                    
                    if input_type == 'hidden' and input_name:
                        self.current_form['hidden_params'][input_name] = input_value
                    
                    if input_type == 'text' and any(x in input_name.lower() for x in ['search', 'key', 'q', 'keyword', 'searchkey', 'searchword', 'wd']):
                        self.current_form['input_name'] = input_name
                        self.current_form['has_search_input'] = True
            
            def handle_endtag(self, tag):
                if tag == 'form':
                    if self.current_form and self.current_form.get('has_search_input'):
                        self.forms.append(self.current_form)
                    self.in_form = False
                    self.current_form = None
        
        parser = FormFinder()
        parser.feed(html)
        
        search_form = None
        for form in parser.forms:
            if form.get('has_search_input'):
                search_form = form
                break
        
        if search_form is None:
            return {'success': False, 'error': '未找到搜索表单'}
        
        form_action = search_form.get('action', '')
        form_method = search_form.get('method', 'GET').upper()
        param_name = search_form.get('input_name', 'keyword')
        hidden_params = search_form.get('hidden_params', {})
        
        if form_action.startswith('http'):
            search_url_base = form_action
        elif form_action.startswith('/'):
            parsed = urlparse(base_url)
            search_url_base = f"{parsed.scheme}://{parsed.netloc}{form_action}"
        else:
            search_url_base = base_url
        
        search_url = self._build_yuedu_search_url(search_url_base, param_name, form_method, hidden_params, charset)
        
        site_name = self.extract_site_name(html, base_url)
        
        self.log_params("搜索功能分析结果", {
            '网站名称': site_name,
            '编码': charset,
            '搜索URL': search_url,
            '搜索类型': form_method,
            '参数名': param_name,
            '隐藏参数': hidden_params,
        })

        return {
            'success': True,
            'site_name': site_name,
            'charset': charset,
            'search_url': search_url,
            'method': form_method,
            'param_name': param_name,
            'hidden_params': hidden_params,
            'full_html': html
        }

    def _build_yuedu_search_url(self, base_url, param_name, method, hidden_params, charset):
        """构建阅读书源格式的搜索URL"""
        if method == 'POST':
            body_parts = [f"{param_name}=" + "{{key}}"]
            for key, value in hidden_params.items():
                body_parts.append(f"{key}={value}")
            
            body_str = '&'.join(body_parts)
            
            config = {
                "method": "POST",
                "body": body_str
            }
            
            if charset and charset.upper() in ['GBK', 'GB2312']:
                config["charset"] = "gbk"
            
            return f"{base_url},{json.dumps(config, ensure_ascii=False)}"
        else:
            params = [f"{param_name}=" + "{{key}}"]
            for key, value in hidden_params.items():
                params.append(f"{key}={value}")
            
            param_str = '&'.join(params)
            
            if '?' in base_url:
                return f"{base_url}&{param_str}"
            else:
                return f"{base_url}?{param_str}"

    def fetch_search_results(self, search_url, param_name, method='GET', charset=None, keyword='我的', hidden_params=None):
        """获取搜索结果"""
        self.step("获取搜索结果并提取第一本书")
        self.status_var.set("正在获取搜索结果...")

        actual_url = search_url
        if ',' in search_url:
            parts = search_url.split(',', 1)
            actual_url = parts[0]
            try:
                config = json.loads(parts[1])
                param_name = re.search(r'(\w+)=\{\{key\}\}', config.get('body', '')).group(1) if 'body' in config else param_name
            except:
                pass

        if method == 'POST':
            post_body = {param_name: keyword}
            if hidden_params:
                post_body.update(hidden_params)
            result = self.post_page(actual_url, post_body, charset)
        else:
            params = [(param_name, keyword)]
            if hidden_params:
                for h_name, h_value in hidden_params.items():
                    params.append((h_name, h_value))
            
            param_str = '&'.join([f"{k}={v}" for k, v in params])
            if '?' in actual_url:
                url = f"{actual_url}&{param_str}"
            else:
                url = f"{actual_url}?{param_str}"
            result = self.fetch_page(url, charset)

        if not result['success']:
            return {'success': False, 'error': f"搜索请求失败: {result['error']}"}

        html = result['html']

        self.save_html('02_搜索页.txt', html)
        self.log(f"搜索页HTML长度: {len(html)} 字符")

        from html.parser import HTMLParser

        class ALinkExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                self.current_link_href = None
                self.current_link_text = ''
                self.in_link = False
                self.link_depth = 0

            def handle_starttag(self, tag, attrs):
                attrs_dict = {k.lower(): v for k, v in attrs}
                if tag == 'a':
                    self.in_link = True
                    self.link_depth = 0
                    self.current_link_href = attrs_dict.get('href', '')
                    self.current_link_text = ''
                elif self.in_link:
                    self.link_depth += 1

            def handle_endtag(self, tag):
                if tag == 'a' and self.in_link:
                    if self.link_depth == 0:
                        self.links.append({
                            'href': self.current_link_href,
                            'text': self.current_link_text.strip()
                        })
                    self.in_link = False
                    self.current_link_href = None
                    self.current_link_text = ''
                    self.link_depth = 0
                elif self.in_link:
                    self.link_depth -= 1

            def handle_data(self, data):
                if self.in_link:
                    self.current_link_text += data

        parser = ALinkExtractor()
        parser.feed(html)
        links = parser.links

        self.log(f"找到 {len(links)} 个链接")

        for link in links:
            href = link['href'].rstrip(',')
            text_clean = link['text']

            if keyword in text_clean:
                if any(x in text_clean for x in ['书架', 'bookcase', '首页', '搜索', '排行', '最新', '书库', '求书']):
                    continue

                if href and 'javascript' not in href.lower():
                    detail_url = self._to_absolute_url(href, result.get('url', actual_url))

                    self.log_params("搜索结果分析", {
                        '书名': text_clean,
                        '详情页URL': detail_url,
                    })

                    return {
                        'success': True,
                        'book_name': text_clean,
                        'book_url': detail_url,
                        'detail_url': detail_url,
                        'html': html
                    }

        for link in links:
            href = link['href'].rstrip(',')
            text_clean = link['text']

            if len(text_clean) > 2 and \
               not any(x in text_clean for x in ['首页', '搜索', '排行', '最新', '书库', '求书', '书架', '登录', '注册']) and \
               href and 'javascript' not in href.lower() and 'bookcase' not in href.lower():
                detail_url = self._to_absolute_url(href, result.get('url', actual_url))

                self.log_params("搜索结果分析（备用）", {
                    '书名': text_clean,
                    '详情页URL': detail_url,
                })

                return {
                    'success': True,
                    'book_name': text_clean,
                    'book_url': detail_url,
                    'detail_url': detail_url,
                    'html': html
                }

        return {'success': False, 'error': '未找到书籍链接'}

    def _to_absolute_url(self, url, base_url):
        """URL转绝对路径"""
        if url.startswith('http'):
            return url
        
        try:
            parsed = urlparse(base_url)
            if url.startswith('/'):
                return f"{parsed.scheme}://{parsed.netloc}{url}"
            else:
                path_parts = [p for p in parsed.path.split('/') if p]
                if path_parts:
                    path_parts = path_parts[:-1]
                path = '/'.join(path_parts)
                if path:
                    return f"{parsed.scheme}://{parsed.netloc}/{path}/{url}"
                else:
                    return f"{parsed.scheme}://{parsed.netloc}/{url}"
        except:
            return url

    def fetch_toc_page(self, base_url, detail_url, charset):
        """获取目录页"""
        self.step("获取详情页/目录页")
        self.status_var.set("正在分析详情页/目录页...")

        self.log(f"获取详情页: {detail_url}")
        result = self.fetch_page(detail_url, charset)
        if not result['success']:
            return {'success': False, 'error': f"获取详情页失败: {result['error']}"}

        html = result['html']

        self.save_html('03_详情页.txt', html)
        self.log(f"详情页HTML已保存，长度: {len(html)} 字符")

        try:
            toc_url = None
            
            a_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
            matches = re.findall(a_pattern, html, re.IGNORECASE | re.DOTALL)
            
            for href, text in matches:
                text_clean = re.sub(r'<[^>]+>', '', text).strip()
                
                if '查看完整目录' in text_clean or \
                   '完整目录' in text_clean or \
                   '全部目录' in text_clean or \
                   '章节目录' in text_clean or \
                   ('目录' in text_clean and len(text_clean) < 10) or \
                   '点击阅读' in text_clean or \
                   '开始阅读' in text_clean:
                    if href and 'javascript' not in href.lower():
                        toc_url = href
                        self.log(f"找到目录链接: \"{text_clean}\" -> {href}")
                        break
            
            if toc_url is None:
                has_pagination = any(x in html for x in [
                    'class="pagination"', 'class="page-link"', 'class="page"',
                    'aria-label="Next"', 'class="next"'
                ])
                
                chapter_count = 0
                for href, text in matches:
                    text_clean = re.sub(r'<[^>]+>', '', text).strip()
                    if '章' in text_clean or '第' in text_clean or '话' in text_clean:
                        chapter_count += 1
                
                self.log_params("分页目录页检测", {
                    '有分页导航': has_pagination,
                    '章节链接数': chapter_count,
                })
                
                if has_pagination or chapter_count > 10:
                    self.log("判断当前页为目录页，无需跳转")
                    return {
                        'success': True,
                        'html': html,
                        'toc_url': detail_url,
                        'charset': result.get('charset', charset)
                    }
            
            if toc_url is not None:
                if toc_url.startswith('http'):
                    full_url = toc_url
                elif toc_url.startswith('/'):
                    parsed = urlparse(base_url)
                    full_url = f"{parsed.scheme}://{parsed.netloc}{toc_url}"
                else:
                    base = detail_url[:detail_url.rfind('/') + 1]
                    full_url = f"{base}{toc_url}"
                
                self.log(f"从详情页跳转获取目录页: {full_url}")
                
                toc_result = self.fetch_page(full_url, charset)
                if toc_result['success']:
                    self.log(f"目录页获取成功，HTML长度: {len(toc_result['html'])}")
                    
                    self.save_html('04_目录页.txt', toc_result['html'])
                    
                    return {
                        'success': True,
                        'html': toc_result['html'],
                        'toc_url': full_url,
                        'charset': toc_result.get('charset', charset)
                    }
            
            return {'success': False, 'error': '未找到目录页'}
        except Exception as e:
            return {'success': False, 'error': f'获取目录页失败：{e}'}

    def fetch_content_page(self, base_url, toc_html, toc_url, charset):
        """获取正文页"""
        self.step("获取正文页（第一章）")
        self.status_var.set("正在获取第一章...")

        try:
            a_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
            matches = re.findall(a_pattern, toc_html, re.IGNORECASE | re.DOTALL)

            for href, text in matches:
                text_clean = re.sub(r'<[^>]+>', '', text).strip()
                
                if '第' in text_clean and ('章' in text_clean or len(text_clean) < 30):
                    if href and 'javascript' not in href.lower():
                        chapter_url = self._to_absolute_url(href, toc_url)
                        
                        self.log_params("正文页获取结果", {
                            '章节名': text_clean,
                            '正文页URL': chapter_url,
                        })

                        result = self.fetch_page(chapter_url, charset)
                        if result['success']:
                            self.save_html('05_正文页.txt', result['html'])
                            self.log(f"正文页HTML长度: {len(result['html'])} 字符")

                            return {
                                'success': True,
                                'chapter_name': text_clean,
                                'content_url': chapter_url,
                                'first_chapter_url': chapter_url,
                                'html': result['html']
                            }

            return {'success': False, 'error': '未找到章节列表'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def generate_source(self, site_name, base_url, charset, search_url, search_rules, book_info_rules, toc_rules, content_rules):
        """生成阅读书源JSON"""
        self.step("生成阅读书源JSON")

        source = {
            "bookSourceComment": "",
            "bookSourceGroup": "",
            "bookSourceName": site_name,
            "bookSourceType": 0,
            "bookSourceUrl": base_url,
            "customOrder": 0,
            "enabled": True,
            "enabledCookieJar": True,
            "enabledExplore": False,
            "exploreUrl": "",
            "respondTime": 180000,
            "ruleBookInfo": book_info_rules,
            "ruleContent": content_rules,
            "ruleExplore": {
                "bookList": ""
            },
            "ruleSearch": search_rules,
            "ruleToc": toc_rules,
            "searchUrl": search_url,
            "weight": 0
        }

        return json.dumps(source, ensure_ascii=False, indent=2)

    def start_generate(self):
        """开始生成"""
        url = self.url_var.get().strip()
        keyword = self.keyword_var.get().strip() or '我的'

        if not url:
            messagebox.showerror("错误", "请输入网站URL")
            return

        self.clear_log()
        self.result_text.delete(1.0, tk.END)
        self.save_btn.config(state=tk.DISABLED)

        self.log("=" * 50)
        self.log("开始阅读书源自动生成任务")
        self.log_params("输入参数", {
            '网站URL': url,
            '搜索关键词': keyword,
        })

        try:
            self.status_var.set("正在分析搜索功能...")
            search_result = self.analyze_search_function(url, keyword)
            if not search_result['success']:
                self.status_var.set(f"搜索分析失败: {search_result['error']}")
                return

            site_name = search_result['site_name']
            charset = search_result['charset']
            search_url = search_result['search_url']
            search_method = search_result['method']
            hidden_params = search_result.get('hidden_params', {})

            self.status_var.set("✓ 搜索功能分析完成，正在获取搜索结果...")

            self.status_var.set("正在从搜索结果获取第一本书...")
            detail_result = self.fetch_search_results(
                search_url, search_result['param_name'],
                method=search_method, charset=charset, keyword=keyword, hidden_params=hidden_params
            )

            if not detail_result['success']:
                self.status_var.set(f"获取详情页失败: {detail_result['error']}")
                self._generate_partial_source(site_name, url, charset, search_url, search_method, detail_result.get('html', ''))
                return

            detail_url = detail_result['book_url']
            search_html = detail_result['html']
            self.status_var.set(f"✓ 找到书籍: {detail_result['book_name']}，正在分析详情页...")

            self.status_var.set("正在判断详情页/目录页并获取目录...")
            toc_result = self.fetch_toc_page(url, detail_url, charset)

            if not toc_result['success']:
                self.status_var.set(f"获取目录页失败: {toc_result['error']}")
                self._generate_partial_source(site_name, url, charset, search_url, search_method, search_html, detail_result['html'])
                return

            toc_url = toc_result['toc_url']
            toc_html = toc_result['html']
            self.status_var.set("✓ 目录页获取完成，正在获取第一章...")

            self.status_var.set("正在从目录获取第一章...")
            content_result = self.fetch_content_page(url, toc_result['html'], toc_url, charset)

            if not content_result['success']:
                self.status_var.set(f"获取正文页失败: {content_result['error']}")
                self._generate_partial_source(site_name, url, charset, search_url, search_method, search_html, detail_result['html'], toc_html)
                return

            content_url = content_result['content_url']
            content_html = content_result['html']
            self.status_var.set(f"✓ 正文页获取完成: {content_result['chapter_name']}，正在分析规则...")

            self.step("分析各页面规则")
            
            search_extractor = JSOUPRuleExtractor(search_html, url)
            search_rules = search_extractor.extract_search_rules()
            self.log(f"搜索页规则: {json.dumps(search_rules, ensure_ascii=False)}")

            detail_extractor = JSOUPRuleExtractor(detail_result.get('html', toc_html), url)
            book_info_rules = detail_extractor.extract_book_info_rules()
            self.log(f"详情页规则: {json.dumps(book_info_rules, ensure_ascii=False)}")

            toc_extractor = JSOUPRuleExtractor(toc_html, url)
            toc_rules, is_reverse = toc_extractor.extract_toc_rules()
            self.log(f"目录页规则: {json.dumps(toc_rules, ensure_ascii=False)}")
            self.log(f"章节顺序: {'倒序' if is_reverse else '正序'}")

            content_extractor = JSOUPRuleExtractor(content_html, url)
            content_rules = content_extractor.extract_content_rules()
            self.log(f"正文页规则: {json.dumps(content_rules, ensure_ascii=False)}")

            self.status_var.set("✓ 规则分析完成，正在生成书源...")

            source = self.generate_source(
                site_name=site_name,
                base_url=url,
                charset=charset,
                search_url=search_url,
                search_rules=search_rules,
                book_info_rules=book_info_rules,
                toc_rules=toc_rules,
                content_rules=content_rules
            )

            self.status_var.set("✓ 书源生成完成！")
            self.generated_source = source
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, source)
            self.save_btn.config(state=tk.NORMAL)

            site_name_clean = re.sub(r'[\\/:*?"<>|]', '', site_name)
            output_file = os.path.join(self.debug_dir, f"{site_name_clean}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(source)
            self.log(f"书源已保存: {output_file}")

            self.log("")
            self.log("=" * 50)
            self.log("阅读书源自动生成任务完成！")
            self.log(f"调试文件保存在: {os.path.abspath(self.debug_dir)}")
            self.log("=" * 50)

        except Exception as e:
            self.log(f"发生错误: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.status_var.set(f"发生错误: {e}")

    def _generate_partial_source(self, site_name, base_url, charset, search_url, search_method, search_html='', detail_html='', toc_html=''):
        """生成部分书源"""
        if search_url and site_name:
            search_rules = {}
            book_info_rules = {'init': '', 'name': '', 'author': '', 'coverUrl': '', 'intro': '', 'kind': '', 'lastChapter': '', 'wordCount': '', 'tocUrl': ''}
            toc_rules = {'chapterList': '', 'chapterName': '', 'chapterUrl': '', 'nextTocUrl': '', 'preUpdateJs': ''}
            content_rules = {'content': '', 'nextContentUrl': '', 'replaceRegex': '', 'webJs': '', 'sourceRegex': ''}
            
            if search_html:
                search_extractor = JSOUPRuleExtractor(search_html, base_url)
                search_rules = search_extractor.extract_search_rules()
            
            if detail_html:
                detail_extractor = JSOUPRuleExtractor(detail_html, base_url)
                book_info_rules = detail_extractor.extract_book_info_rules()
            
            if toc_html:
                toc_extractor = JSOUPRuleExtractor(toc_html, base_url)
                toc_rules, _ = toc_extractor.extract_toc_rules()
            
            source = self.generate_source(
                site_name=site_name,
                base_url=base_url,
                charset=charset,
                search_url=search_url,
                search_rules=search_rules,
                book_info_rules=book_info_rules,
                toc_rules=toc_rules,
                content_rules=content_rules
            )
            
            self.generated_source = source
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, source)
            self.save_btn.config(state=tk.NORMAL)

    def save_source(self):
        """保存书源"""
        if not self.generated_source:
            return

        try:
            source_data = json.loads(self.generated_source)
            site_name = source_data.get('bookSourceName', 'booksource')
        except:
            site_name = "booksource"

        site_name = re.sub(r'[\\/:*?"<>|]', '', site_name)

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialfile=f"{site_name}.json"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.generated_source)
                self.status_var.set(f"已保存: {filename}")
                messagebox.showinfo("成功", f"书源已保存到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")


def main():
    root = tk.Tk()
    app = AutoSourceGenerator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
