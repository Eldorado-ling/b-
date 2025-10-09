import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import json
import os
from typing import List, Dict
import threading
import requests
import time
import csv

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

session = requests.session()


def parse_cookie_string(cookie_str):
    cookies = {}
    if not cookie_str:
        return cookies
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def requet1(cookie_dict):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'priority': 'u=1, i',
        'referer': 'https://mall.bilibili.com/neul-next/index.html?page=magic-market_index',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    }
    try:
        response = session.get(
            'https://mall.bilibili.com/mall-magic-c/internet/c2c/items/queryHeadInfo',
            headers=headers,
            cookies=cookie_dict,
            timeout=10
        )
        print(f"登录状态: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"登录失败: {e}")
        return False


class SpiderCrawler:
    type_map = {'3C': '2273', '周边': '2331', '模型': '2066', '手办': '2312', '默认': ''}
    sort_map = {'升序': 'PRICE_ASC', '降序': 'PRICE_DESC', '综合': 'TIME_DESC'}
    price_map = {
        '0-20': ["0-2000"],
        '20-30': ["2000-3000"],
        '30-50': ["3000-5000"],
        '50-100': ["5000-10000"],
        '100-200': ["10000-20000"],
        '200以上': ["20000-0"],
        '默认': [""]
    }

    def __init__(self, cookie_str, gui_callback=None):
        self.cookie_str = cookie_str
        self.cookie_dict = parse_cookie_string(cookie_str)
        self.gui_callback = gui_callback
        self.offset = 0
        self.data = {}
        self.is_running = True

    def spider(self, category, sort_order, price_range, keyword=None):
        self.data = {
            "nextId": None,
            "sortType": self.sort_map.get(sort_order, "TIME_DESC")
        }
        price_filter = self.price_map.get(price_range, [""])
        if price_filter != [""]:
            self.data["priceFilters"] = price_filter
        category_filter = self.type_map.get(category, "")
        if category_filter:
            self.data["categoryFilter"] = category_filter
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://mall.bilibili.com',
            'priority': 'u=1, i',
            'referer': 'https://mall.bilibili.com/neul-next/index.html?page=magic-market_index',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        }
        print(f"开始爬取 - 类别:{category}, 排序:{sort_order}, 价格:{price_range}, 关键词:{keyword}")
        print(f"发送数据: {self.data}")
        if not requet1(self.cookie_dict):
            raise Exception("登录失败，请检查Cookie是否有效")
        max_offset = 200 if keyword else 20000
        crawl_count = 0
        while self.offset < max_offset and self.is_running:
            interval = 3
            time.sleep(interval)
            try:
                start_time = time.time()
                response = session.post(
                    'https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list',
                    headers=headers,
                    cookies=self.cookie_dict,
                    json=self.data,
                    timeout=15
                )
                if response.status_code != 200:
                    print(f"请求失败，状态码: {response.status_code}")
                    continue
                response_dict = response.json()
                if response_dict.get('code') != 0:
                    error_code = response_dict.get('code')
                    error_msg = response_dict.get('message', '未知错误')
                    if error_code == 429:
                        print("触发频率限制，重新登录...")
                        requet1(self.cookie_dict)
                        continue
                    else:
                        print(f"API错误: {error_code} - {error_msg}")
                        continue
                data_obj = response_dict.get('data', {})
                items = data_obj.get('data', [])
                next_id = data_obj.get('nextId')
                if not items:
                    print("没有更多数据")
                    break
                self.data["nextId"] = next_id
                self.offset += len(items)
                elapsed_time = time.time() - start_time
                for item in items:
                    if not self.is_running:
                        break
                    item_name = item.get('c2cItemsName', '')
                    if keyword and keyword not in item_name:
                        continue
                    try:
                        price = float(item.get('showPrice', '0'))
                    except (ValueError, TypeError):
                        price = 0.0
                    item_id = item.get('c2cItemsId', '')
                    link = f"https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId={item_id}&from=market_index"
                    product = {
                        'name': item_name,
                        'price': price,
                        'link': link
                    }
                    crawl_count += 1
                    if self.gui_callback:
                        self.gui_callback(product, self.offset, elapsed_time, interval)
                    yield product
                print(f"已爬取 {crawl_count} 条，offset: {self.offset}")
                if next_id is None:
                    print("已到达最后一页")
                    break
            except json.JSONDecodeError as e:
                error = str(e)
                print(f"JSON解析错误: {error}")
                continue
            except requests.exceptions.Timeout as e:
                error = str(e)
                print(f"请求超时: {error}")
                continue
            except requests.exceptions.RequestException as e:
                error = str(e)
                print(f"网络请求错误: {error}")
                continue
            except Exception as e:
                error = str(e)
                print(f"爬取错误: {error}")
                continue

    def stop(self):
        self.is_running = False


class CrawlerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("魔力赏个人版")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.products_data = []
        self.config_file = "config.json"
        self.background_image_path = None
        self.is_crawling = False
        self.crawler_thread = None
        self.crawler_instance = None
        self.crawl_start_time = None
        self.filter_name_enabled = False
        self.filter_price_enabled = False
        self.filter_name_value = ""
        self.filter_price_value = 0.0
        self.load_config()
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.create_sidebar()
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.pages = {}
        self.create_home_page()
        self.create_display_page()
        self.create_cookie_page()
        self.create_settings_page()
        self.show_page("home")

    def start_crawl(self):
        if self.is_crawling:
            messagebox.showwarning("警告", "爬虫正在运行中")
            return
        cookie = self.get_cookie()
        if not cookie:
            result = messagebox.askyesno("警告", "未配置Cookie，爬虫可能无法正常工作\n是否继续？")
            if not result:
                return
        category = self.category_combo.get()
        sort_order = self.sort_combo.get()
        price_range = self.price_combo.get()
        if self.products_data:
            if messagebox.askyesno("确认", "是否清空之前的数据并开始新的爬取？"):
                self.products_data = []
                self.update_display()
        self.is_crawling = True
        self.crawl_start_time = time.time()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.update_status("● 爬虫运行中...", "green")
        self.crawl_count_var.set("0")
        self.crawl_time_var.set("0秒")
        self.crawl_interval_var.set("0秒")
        self.crawler_thread = threading.Thread(
            target=self._crawl_thread,
            args=(None, category, sort_order, price_range, cookie),
            daemon=True
        )
        self.crawler_thread.start()

    def stop_crawl(self):
        if not self.is_crawling:
            return
        self.is_crawling = False
        if self.crawler_instance:
            self.crawler_instance.stop()
        self.update_status("● 正在停止...", "orange")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("● 已停止", "red")
        messagebox.showinfo("提示", f"爬虫已停止\n共爬取 {len(self.products_data)} 条数据")

    def _crawl_thread(self, keyword, category, sort_order, price_range, cookie):
        try:
            self.crawler_instance = SpiderCrawler(
                cookie_str=cookie,
                gui_callback=self._on_product_crawled
            )
            spider_gen = self.crawler_instance.spider(category, sort_order, price_range, keyword)
            for product in spider_gen:
                if not self.is_crawling:
                    break
            if self.is_crawling:
                self.after(0, lambda: self.crawl_complete(len(self.products_data)))
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.crawl_error(error_msg))

    def _on_product_crawled(self, product, offset, elapsed_time, interval):
        def update_ui():
            self.add_product_realtime(product)
            crawl_count = len(self.products_data)
            total_time = int(time.time() - self.crawl_start_time) if self.crawl_start_time else 0
            self.crawl_count_var.set(str(crawl_count))
            self.crawl_time_var.set(f"{total_time}秒")
            self.crawl_interval_var.set(f"{elapsed_time:.2f}秒")
        self.after(0, update_ui)

    def crawl_complete(self, count):
        self.is_crawling = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("● 完成", "green")
        messagebox.showinfo("完成", f"成功爬取 {count} 条数据")

    def crawl_error(self, error_msg):
        self.is_crawling = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("● 错误", "red")
        messagebox.showerror("错误", f"爬虫运行出错:\n{error_msg}")

    def clear_all_data(self):
        if not self.products_data:
            messagebox.showinfo("提示", "当前没有数据")
            return
        if messagebox.askyesno("确认", f"确定要清空所有 {len(self.products_data)} 条数据吗？"):
            self.products_data = []
            self.update_display()
            self.crawl_count_var.set("0")
            messagebox.showinfo("成功", "数据已清空")

    def update_status(self, text, color="gray60"):
        self.status_label.configure(text=text, text_color=color)

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)
        logo_label = ctk.CTkLabel(
            self.sidebar,
            text="🛒 个人版",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        logo_label.grid(row=0, column=0, padx=20, pady=30)
        self.nav_buttons = {}
        nav_items = [
            ("home", "🏠 主页", 1),
            ("display", "📊 数据展示", 2),
            ("cookie", "🔑 Cookie", 3),
            ("settings", "⚙️ 设置", 4)
        ]
        for key, text, row in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=lambda k=key: self.show_page(k),
                font=ctk.CTkFont(size=14),
                height=40,
                corner_radius=8
            )
            btn.grid(row=row, column=0, padx=20, pady=10, sticky="ew")
            self.nav_buttons[key] = btn
        info_label = ctk.CTkLabel(
            self.sidebar,
            text="v1.0.0\n© 2025",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        info_label.grid(row=6, column=0, padx=20, pady=20)

    def toggle_filter_name(self):
        self.filter_name_enabled = self.filter_name_switch.get()
        if self.filter_name_enabled:
            self.filter_name_entry.configure(state="normal")
        else:
            self.filter_name_entry.configure(state="disabled")
        self.update_display()

    def toggle_filter_price(self):
        self.filter_price_enabled = self.filter_price_switch.get()
        if self.filter_price_enabled:
            self.filter_price_entry.configure(state="normal")
        else:
            self.filter_price_entry.configure(state="disabled")
        self.update_display()

    def on_filter_name_change(self, *args):
        self.filter_name_value = self.filter_name_entry.get().strip()
        self.update_display()

    def on_filter_price_change(self, *args):
        try:
            price_str = self.filter_price_entry.get().strip()
            self.filter_price_value = float(price_str) if price_str else 0.0
        except ValueError:
            self.filter_price_value = 0.0
        self.update_display()

    def create_home_page(self):
        page = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.pages["home"] = page
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_columnconfigure(2, weight=1)
        title = ctk.CTkLabel(
            page,
            text="魔力赏个人版",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=3, pady=(0, 30), sticky="w")
        category_frame = ctk.CTkFrame(page, corner_radius=15)
        category_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        category_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(category_frame, text="类别", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.category_combo = ctk.CTkComboBox(category_frame, values=["默认", "3C", "周边", "手办", "模型"], height=35)
        self.category_combo.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.category_combo.set("默认")
        sort_frame = ctk.CTkFrame(page, corner_radius=15)
        sort_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        sort_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sort_frame, text="排序", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.sort_combo = ctk.CTkComboBox(sort_frame, values=["综合", "升序", "降序"], height=35)
        self.sort_combo.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.sort_combo.set("综合")
        price_frame = ctk.CTkFrame(page, corner_radius=15)
        price_frame.grid(row=1, column=2, padx=10, pady=10, sticky="nsew")
        price_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(price_frame, text="价格", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.price_combo = ctk.CTkComboBox(price_frame, values=["默认", "0-20", "20-30", "30-50", "50-100", "100-200", "200以上"], height=35)
        self.price_combo.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.price_combo.set("默认")
        filter_section = ctk.CTkFrame(page, corner_radius=15)
        filter_section.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        filter_section.grid_columnconfigure(0, weight=1)
        filter_section.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_section, text="🔍 查询过滤", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="w")
        name_filter_frame = ctk.CTkFrame(filter_section, corner_radius=10)
        name_filter_frame.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="nsew")
        name_filter_frame.grid_columnconfigure(1, weight=1)
        filter_name_header = ctk.CTkFrame(name_filter_frame, fg_color="transparent")
        filter_name_header.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 5), sticky="ew")
        ctk.CTkLabel(filter_name_header, text="商品名称", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.filter_name_switch = ctk.CTkSwitch(filter_name_header, text="", command=self.toggle_filter_name, width=50)
        self.filter_name_switch.pack(side="right")
        self.filter_name_entry = ctk.CTkEntry(name_filter_frame, placeholder_text="输入商品名称关键词", height=35, state="disabled")
        self.filter_name_entry.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")
        self.filter_name_entry.bind("<KeyRelease>", self.on_filter_name_change)
        price_filter_frame = ctk.CTkFrame(filter_section, corner_radius=10)
        price_filter_frame.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="nsew")
        price_filter_frame.grid_columnconfigure(1, weight=1)
        filter_price_header = ctk.CTkFrame(price_filter_frame, fg_color="transparent")
        filter_price_header.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 5), sticky="ew")
        ctk.CTkLabel(filter_price_header, text="价格上限（≤）", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.filter_price_switch = ctk.CTkSwitch(filter_price_header, text="", command=self.toggle_filter_price, width=50)
        self.filter_price_switch.pack(side="right")
        self.filter_price_entry = ctk.CTkEntry(price_filter_frame, placeholder_text="输入价格上限（元）", height=35, state="disabled")
        self.filter_price_entry.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 5), sticky="ew")
        self.filter_price_entry.bind("<KeyRelease>", self.on_filter_price_change)
        ctk.CTkLabel(price_filter_frame, text="仅显示价格小于等于此值的商品", font=ctk.CTkFont(size=11), text_color="gray60").grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="w")
        control_section = ctk.CTkFrame(page, corner_radius=15)
        control_section.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        control_section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(control_section, text='开始', font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, padx=20, pady=15, sticky="w")
        btn_frame = ctk.CTkFrame(control_section, fg_color="transparent")
        btn_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=10)
        self.start_btn = ctk.CTkButton(btn_frame, text="🚀 启动", command=self.start_crawl, height=50, width=200, fg_color="#2ecc71", hover_color="#27ae60", font=ctk.CTkFont(size=16, weight="bold"))
        self.start_btn.pack(side="left", padx=10)
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹️ 停止", command=self.stop_crawl, height=50, width=200, fg_color="#e74c3c", hover_color="#c0392b", font=ctk.CTkFont(size=16, weight="bold"), state="disabled")
        self.stop_btn.pack(side="left", padx=10)
        self.clear_btn = ctk.CTkButton(btn_frame, text="🗑️ 清空数据", command=self.clear_all_data, height=50, width=150, fg_color="gray40", hover_color="gray50", font=ctk.CTkFont(size=14))
        self.clear_btn.pack(side="left", padx=10)
        status_frame = ctk.CTkFrame(control_section, fg_color="transparent")
        status_frame.grid(row=2, column=0, columnspan=3, padx=20, pady=(0, 15), sticky="ew")
        self.status_label = ctk.CTkLabel(status_frame, text="● 就绪", font=ctk.CTkFont(size=14), text_color="gray60")
        self.status_label.pack(side="left")
        stats_section = ctk.CTkFrame(page, corner_radius=15)
        stats_section.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        stats_section.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(stats_section, text="📊 实时统计", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, padx=20, pady=(15, 10), sticky="w")
        self.crawl_count_var = ctk.StringVar(value="0")
        count_frame = ctk.CTkFrame(stats_section, corner_radius=10)
        count_frame.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="nsew")
        ctk.CTkLabel(count_frame, text="爬取数量", font=ctk.CTkFont(size=12), text_color="gray70").pack(pady=(10, 5))
        ctk.CTkLabel(count_frame, textvariable=self.crawl_count_var, font=ctk.CTkFont(size=24, weight="bold"), text_color="lightgreen").pack(pady=(0, 10))
        self.crawl_time_var = ctk.StringVar(value="0秒")
        time_frame = ctk.CTkFrame(stats_section, corner_radius=10)
        time_frame.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="nsew")
        ctk.CTkLabel(time_frame, text="累计时间", font=ctk.CTkFont(size=12), text_color="gray70").pack(pady=(10, 5))
        ctk.CTkLabel(time_frame, textvariable=self.crawl_time_var, font=ctk.CTkFont(size=24, weight="bold"), text_color="lightblue").pack(pady=(0, 10))
        self.crawl_interval_var = ctk.StringVar(value="0秒")
        interval_frame = ctk.CTkFrame(stats_section, corner_radius=10)
        interval_frame.grid(row=1, column=2, padx=10, pady=(0, 15), sticky="nsew")
        ctk.CTkLabel(interval_frame, text="请求耗时", font=ctk.CTkFont(size=12), text_color="gray70").pack(pady=(10, 5))
        ctk.CTkLabel(interval_frame, textvariable=self.crawl_interval_var, font=ctk.CTkFont(size=24, weight="bold"), text_color="orange").pack(pady=(0, 10))
        tips_frame = ctk.CTkFrame(page, corner_radius=15)
        tips_frame.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        tips_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tips_frame, text="📌 使用提示", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")
        tips = [
            "1. 请确认使用的是edge或google浏览器的cookie",
            "2. 请确认选项是否正确",
            "3. 请确认您今天采集数据没有超过2w条",
            "4. 查询过滤功能：开启后仅在数据展示页面显示符合条件的商品",
            "5. 商品名称过滤：匹配商品名称中包含关键词的商品",
            "6. 价格过滤：仅显示价格小于等于设定值的商品"
        ]
        for i, tip in enumerate(tips, start=1):
            ctk.CTkLabel(tips_frame, text=tip, font=ctk.CTkFont(size=13), text_color="gray70").grid(row=i, column=0, padx=20, pady=3, sticky="w")

    def create_display_page(self):
        page = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.pages["display"] = page
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        title_frame = ctk.CTkFrame(page, fg_color="transparent", height=60)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="📊 数据展示", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        query_frame = ctk.CTkFrame(page, corner_radius=10, height=80)
        query_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        query_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(query_frame, text="🔍 搜索已爬取商品", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        self.query_entry = ctk.CTkEntry(query_frame, placeholder_text="在已爬取的数据中搜索商品名称", height=40)
        self.query_entry.grid(row=0, column=1, padx=10, pady=15, sticky="ew")
        self.query_btn = ctk.CTkButton(query_frame, text="搜索", command=self.search_in_data, height=40, width=100)
        self.query_btn.grid(row=0, column=2, padx=10, pady=15)
        self.reset_btn = ctk.CTkButton(query_frame, text="重置", command=self.reset_search, height=40, width=80, fg_color="gray40", hover_color="gray50")
        self.reset_btn.grid(row=0, column=3, padx=10, pady=15)
        sort_frame = ctk.CTkFrame(query_frame, fg_color="transparent")
        sort_frame.grid(row=0, column=4, padx=(0, 20), pady=15)
        ctk.CTkLabel(sort_frame, text="排序:", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 10))
        self.sort_var = ctk.StringVar(value="默认")
        sort_options = ["默认", "价格从低到高", "价格从高到低"]
        self.sort_combo_display = ctk.CTkComboBox(sort_frame, values=sort_options, variable=self.sort_var, command=self.sort_products, width=150)
        self.sort_combo_display.pack(side="left")
        self.display_scroll = ctk.CTkScrollableFrame(page, corner_radius=10)
        self.display_scroll.grid(row=2, column=0, sticky="nsew")
        self.display_scroll.grid_columnconfigure(0, weight=1)
        self.table_frame = ctk.CTkFrame(self.display_scroll, fg_color="transparent")
        self.table_frame.grid(row=0, column=0, sticky="nsew")
        self.table_frame.grid_columnconfigure(0, weight=5)
        self.table_frame.grid_columnconfigure(1, weight=1)
        self.table_frame.grid_columnconfigure(2, weight=1)
        header_frame = ctk.CTkFrame(self.table_frame, fg_color="gray25", height=50, corner_radius=8)
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        header_frame.grid_columnconfigure(0, weight=5)
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(header_frame, text="商品名称", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, padx=20, pady=12, sticky="w")
        ctk.CTkLabel(header_frame, text="价格", font=ctk.CTkFont(size=14, weight="bold"), anchor="center").grid(row=0, column=1, padx=10, pady=12, sticky="ew")
        ctk.CTkLabel(header_frame, text="链接", font=ctk.CTkFont(size=14, weight="bold"), anchor="center").grid(row=0, column=2, padx=20, pady=12, sticky="ew")
        self.no_data_label = ctk.CTkLabel(self.table_frame, text="暂无数据\n请在主页启动爬虫采集数据", font=ctk.CTkFont(size=16), text_color="gray50")
        self.no_data_label.grid(row=1, column=0, columnspan=3, pady=50)
        self.search_keyword = ""

    def search_in_data(self):
        keyword = self.query_entry.get().strip()
        self.search_keyword = keyword
        self.update_display()
        if keyword:
            messagebox.showinfo("搜索", f"正在显示包含 '{keyword}' 的商品")

    def reset_search(self):
        self.search_keyword = ""
        self.query_entry.delete(0, 'end')
        self.update_display()

    def create_cookie_page(self):
        page = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.pages["cookie"] = page
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        title_frame = ctk.CTkFrame(page, fg_color="transparent", height=60)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        ctk.CTkLabel(title_frame, text="🔑 Cookie 配置", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        input_frame = ctk.CTkFrame(page, corner_radius=15)
        input_frame.grid(row=1, column=0, sticky="nsew")
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_rowconfigure(1, weight=1)
        info_frame = ctk.CTkFrame(input_frame, fg_color="gray20", corner_radius=10)
        info_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        ctk.CTkLabel(info_frame, text="ℹ️ 请输入您的B站浏览器Cookie，支持Edge和Chrome浏览器", font=ctk.CTkFont(size=13), text_color="lightblue").pack(padx=15, pady=12)
        self.cookie_text = ctk.CTkTextbox(input_frame, corner_radius=10, font=ctk.CTkFont(size=12))
        self.cookie_text.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        if hasattr(self, 'saved_cookie') and self.saved_cookie:
            self.cookie_text.insert("1.0", self.saved_cookie)
        button_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        ctk.CTkButton(button_frame, text="💾 保存Cookie", command=self.save_cookie, height=40, font=ctk.CTkFont(size=14, weight="bold"), corner_radius=8).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="🗑️ 清空Cookie", command=self.clear_cookie, height=40, font=ctk.CTkFont(size=14), corner_radius=8, fg_color="gray30", hover_color="gray40").pack(side="left")

    def create_settings_page(self):
        page = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.pages["settings"] = page
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text="⚙️ 设置", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))
        appearance_frame = ctk.CTkFrame(page, corner_radius=15)
        appearance_frame.grid(row=1, column=0, sticky="ew", pady=10)
        appearance_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(appearance_frame, text="🎨 外观模式", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        self.appearance_var = ctk.StringVar(value="Dark")
        appearance_menu = ctk.CTkOptionMenu(appearance_frame, values=["Light", "Dark", "System"], variable=self.appearance_var, command=self.change_appearance, width=150)
        appearance_menu.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        data_frame = ctk.CTkFrame(page, corner_radius=15)
        data_frame.grid(row=2, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(data_frame, text="📁 数据管理", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        ctk.CTkButton(data_frame, text="导出为CSV", command=self.export_data, width=120).grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

    def show_page(self, page_name):
        for page in self.pages.values():
            page.grid_forget()
        if page_name in self.pages:
            self.pages[page_name].grid(row=0, column=0, sticky="nsew")
        for key, btn in self.nav_buttons.items():
            if key == page_name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color=("gray70", "gray30"))

    def add_product_realtime(self, product_dict):
        self.products_data.append(product_dict)
        self.update_display()

    def get_filtered_products(self):
        filtered = self.products_data.copy()
        if self.filter_name_enabled and self.filter_name_value:
            filtered = [p for p in filtered if self.filter_name_value in p['name']]
        if self.filter_price_enabled and self.filter_price_value > 0:
            filtered = [p for p in filtered if p['price'] <= self.filter_price_value]
        if self.search_keyword:
            filtered = [p for p in filtered if self.search_keyword in p['name']]
        return filtered

    def update_display(self):
        for widget in self.table_frame.winfo_children():
            grid_info = widget.grid_info()
            if grid_info and grid_info.get('row', 0) > 0:
                widget.destroy()
        if hasattr(self, 'no_data_label') and self.no_data_label.winfo_exists():
            self.no_data_label.destroy()
        filtered_products = self.get_filtered_products()
        if not filtered_products:
            if not self.products_data:
                message = "暂无数据\n请在主页启动爬虫采集数据"
            else:
                message = "未找到符合条件的商品\n请调整过滤条件或搜索关键词"
            self.no_data_label = ctk.CTkLabel(self.table_frame, text=message, font=ctk.CTkFont(size=16), text_color="gray50")
            self.no_data_label.grid(row=1, column=0, columnspan=3, pady=50)
            return
        for i, product in enumerate(filtered_products, start=1):
            row_color = "gray20" if i % 2 == 0 else "gray25"
            name_cell = ctk.CTkFrame(self.table_frame, fg_color=row_color, corner_radius=0)
            name_cell.grid(row=i, column=0, sticky="ew", pady=1)
            ctk.CTkLabel(name_cell, text=product["name"], font=ctk.CTkFont(size=13), wraplength=600, anchor="w", justify="left").pack(padx=20, pady=12, fill="x")
            price_cell = ctk.CTkFrame(self.table_frame, fg_color=row_color, corner_radius=0)
            price_cell.grid(row=i, column=1, sticky="ew", pady=1)
            ctk.CTkLabel(price_cell, text=f"¥{product['price']:.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="lightgreen", anchor="center").pack(padx=10, pady=12, fill="x")
            link_cell = ctk.CTkFrame(self.table_frame, fg_color=row_color, corner_radius=0)
            link_cell.grid(row=i, column=2, sticky="ew", pady=1)
            ctk.CTkButton(link_cell, text="🔗 查看链接", command=lambda url=product['link']: self.open_link(url), width=110, height=30).pack(padx=20, pady=12)

    def sort_products(self, choice):
        if choice == "价格从低到高":
            self.products_data.sort(key=lambda x: x['price'])
        elif choice == "价格从高到低":
            self.products_data.sort(key=lambda x: x['price'], reverse=True)
        self.update_display()

    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def save_cookie(self):
        cookie = self.cookie_text.get("1.0", "end-1c")
        if cookie.strip():
            self.saved_cookie = cookie
            self.save_config()
            messagebox.showinfo("成功", "Cookie已保存")
        else:
            messagebox.showwarning("警告", "Cookie不能为空")

    def clear_cookie(self):
        self.cookie_text.delete("1.0", "end")
        self.saved_cookie = ""
        self.save_config()
        messagebox.showinfo("提示", "Cookie已清空")

    def change_appearance(self, mode):
        ctk.set_appearance_mode(mode)
        self.save_config()

    def export_data(self):
        if not self.products_data:
            messagebox.showwarning("警告", "没有数据可导出")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")])
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.products_data, f, ensure_ascii=False, indent=2)
                else:
                    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['name', 'price', 'link'])
                        writer.writeheader()
                        writer.writerows(self.products_data)
                messagebox.showinfo("成功", f"数据已导出到:\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败:\n{str(e)}")

    def save_config(self):
        config = {
            "cookie": getattr(self, 'saved_cookie', ""),
            "appearance": self.appearance_var.get()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.saved_cookie = config.get("cookie", "")
                    appearance = config.get("appearance", "Dark")
                    ctk.set_appearance_mode(appearance)
            else:
                self.saved_cookie = ""
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.saved_cookie = ""

    def get_cookie(self):
        return self.saved_cookie


if __name__ == "__main__":
    app = CrawlerGUI()
    app.mainloop()