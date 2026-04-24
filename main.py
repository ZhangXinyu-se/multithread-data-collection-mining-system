import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

is_running = False
stop_event = threading.Event()

# 模拟浏览器的会话状态
cookies = {
    'aQQ_ajkguid': '真实cookie',
    'sessid': '',
    'ajk-appVersion': '',
    'id58': '',
    'xxzlclientid': '',
    'xxzlxxid': '',
    '58tj_uuid': '',
    'new_uv': '',
    'ctid': '',
    'cmctid': '',
    'twe': '',
    'fzq_h': '',
    'lps': '',
    'fzq_js_anjuke_ershoufang_pc': '',
    'obtain_by': '',
    'xxzlbbid': '',
}

# 构造合法请求头，伪装浏览器访问
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pt-BR;q=0.5,pt;q=0.4',
    'cache-control': 'no-cache',
    'dnt': '1',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://shenzhen.anjuke.com/sale/?from=HomePage_TopBar',
    'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
}

# 定义原始数据文件
CSV_FILE = '深圳二手房.csv'
# 清洗过的数据文件
CLEANED_FILE = '深圳二手房_cleaned.csv'
# CSV文件的表头结构
CSV_HEADERS = ['标题', '户型', '面积', '朝向', '楼层', '建造年份', '小区名称', '区域', '商圈', '地址', '标签',
               '总价(万)', '单价(元/㎡)']


# 检查深圳二手房.csv是否存在，如果不存在则创建文件，并写入表头（CSV_HEADERS），保证后续追加数据时格式统一。
def init_csv():
    """初始化CSV文件，写入表头"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def save_to_csv(data_list):
    """追加数据到CSV文件"""
    with open(CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        for data in data_list:
            writer.writerow(data)
    return len(data_list)


def parse_page(html):
    """解析页面HTML，提取房产数据"""
    soup = BeautifulSoup(html, 'html.parser')
    properties = soup.select('div.property[tongji_tag="fcpc_ersflist_gzcount"]')
    results = []

    for prop in properties:
        try:
           # # 提取标题 匹配class为property-content-title-name的h3标签 找title
            title_elem = prop.select_one('h3.property-content-title-name')
            title = title_elem.get('title', '').strip() if title_elem else ''

            # 户型 p标签 class为property-content-info-attribute
            attr_elem = prop.select_one('p.property-content-info-attribute')
            layout = ''
            if attr_elem:
                # 父标签内所有的span子标签
                spans = attr_elem.select('span')
                # 拼接span标签
                layout = ''.join([s.text for s in spans])

            # 面积、朝向、楼层、建造年份
            info_texts = prop.select('div.property-content-info:first-of-type p.property-content-info-text')
            area = ''
            orientation = ''
            floor = ''
            build_year = ''

            for info in info_texts:
                text = info.text.strip()
                if '㎡' in text:
                    area = text
                elif '层' in text:
                    floor = text
                elif '年建造' in text:
                    build_year = text
                elif text in ['南', '北', '东', '西', '南北', '东西', '东南', '东北', '西南', '西北']:
                    orientation = text
            # 小区名称的p标签
            comm_name = prop.select_one('p.property-content-info-comm-name')
            community = comm_name.text.strip() if comm_name else ''
            # 详细地址 区域 商圈 地址
            addr_spans = prop.select('p.property-content-info-comm-address span')
            district = addr_spans[0].text.strip() if len(addr_spans) > 0 else ''
            business_area = addr_spans[1].text.strip() if len(addr_spans) > 1 else ''
            address = addr_spans[2].text.strip() if len(addr_spans) > 2 else ''
            # 房源标签
            tags = prop.select('span.property-content-info-tag')
            tag_str = ','.join([t.text.strip() for t in tags])
            # 总价
            total_price = prop.select_one('span.property-price-total-num')
            price_total = total_price.text.strip() if total_price else ''
            # 单价
            avg_price = prop.select_one('p.property-price-average')
            price_avg = avg_price.text.strip() if avg_price else ''

            if title:
                results.append([title, layout, area, orientation, floor, build_year,
                                community, district, business_area, address, tag_str, price_total, price_avg])
        except Exception:
            continue

    return results


def clean_data():
    """清洗爬取的数据"""
    if not os.path.exists(CSV_FILE):
        return None, "未找到数据文件"
    # 读取csv文件
    df = pd.read_csv(CSV_FILE, encoding='utf-8-sig')

    # 去除重复数据
    # 清洗前的总行数
    original_count = len(df)
    #按「标题+小区名称」组合去重
    df = df.drop_duplicates(subset=['标题', '小区名称'], keep='first')
    #清洗面积列 提取数值 89㎡->89.0
    df['面积_数值'] = df['面积'].str.extract(r'(\d+\.?\d*)').astype(float)
    #清洗总价 转换为数值
    df['总价_数值'] = pd.to_numeric(df['总价(万)'], errors='coerce')
    #清洗单价 提取数值
    df['单价_数值'] = df['单价(元/㎡)'].str.extract(r'(\d+)').astype(float)
    # 清洗建造年份 提取年份
    df['建造年份_数值'] = df['建造年份'].str.extract(r'(\d{4})').astype(float)
    # 从户型中提取房间数
    df['房间数'] = df['户型'].str.extract(r'(\d+)室').astype(float)

    #删除缺失关键数据的行
    df = df.dropna(subset=['总价_数值', '面积_数值'])
    # 保存清洗后的数据到CSV文件
    df.to_csv(CLEANED_FILE, index=False, encoding='utf-8-sig')
    # 清洗后的有效行数
    cleaned_count = len(df)
    # 被删除的行数
    removed = original_count - cleaned_count

    return df, f"清洗完成: {original_count} -> {cleaned_count} (删除 {removed} 条)"


class CrawlerApp:
    def __init__(self, root):
        # 初始化窗口标题 尺寸...
        self.root = root
        self.root.title("深圳二手房数据爬取")
        self.root.geometry("900x700")
        # 记录当前是否正在执行爬取任务 防止重复开始
        self.is_running = False
        # 线程停止信号（优雅停止）
        self.stop_event = threading.Event()
        # 保存爬取线程对象
        self.crawl_thread = None
        # 调用setupui构建界面
        self.setup_ui()

    def setup_ui(self):
        # 在父容器root上添加控制面板
        control_frame = ttk.LabelFrame(self.root, text="控制面板", padding=10)
        # 控制面板放在界面上
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # 页码范围输入--起始页 默认为1
        ttk.Label(control_frame, text="起始页:").grid(row=0, column=0, padx=5)
           # 创建字符串变量，用于绑定输入框内容，默认值为"1"
        self.start_page_var = tk.StringVar(value="1")
          # 创建起始页输入框
        ttk.Entry(control_frame, textvariable=self.start_page_var, width=8).grid(row=0, column=1, padx=5)


        # 页码范围输入--结束页 默认为10
        ttk.Label(control_frame, text="结束页:").grid(row=0, column=2, padx=5)
        self.end_page_var = tk.StringVar(value="10")
        ttk.Entry(control_frame, textvariable=self.end_page_var, width=8).grid(row=0, column=3, padx=5)

        # 按钮
        # 绑定start_craw方法 开始按钮 绑定爬取数据
        self.start_btn = ttk.Button(control_frame, text="开始", command=self.start_crawl)
        self.start_btn.grid(row=0, column=4, padx=10)

        # 创建"停止"按钮，父容器是control_frame，点击触发self.stop_crawl方法
        self.stop_btn = ttk.Button(control_frame, text="停止", command=self.stop_crawl, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=5, padx=5)

        # 创建"数据清洗"按钮，父容器是control_frame，点击触发self.clean_data方法
        self.clean_btn = ttk.Button(control_frame, text="数据清洗", command=self.clean_data)
        self.clean_btn.grid(row=0, column=6, padx=5)
        # 创建"可视化"按钮，父容器是control_frame，点击触发self.show_visualization方法
        self.viz_btn = ttk.Button(control_frame, text="可视化", command=self.show_visualization)
        self.viz_btn.grid(row=0, column=7, padx=5)

        # 进度条
        # 用于绑定进度条的进度值
        self.progress_var = tk.DoubleVar()
        # 设置进度条ui
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100)
        self.progress.grid(row=1, column=0, columnspan=8, sticky='ew', pady=10)

        # 状态标签
        # 创建字符串变量，用于绑定状态标签内容，默认值为"就绪
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=2, column=0, columnspan=8)

        # 日志区域
        # 日志框架
        log_frame = ttk.LabelFrame(self.root, text="日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        #创建带滚动条的文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 可视化区域
        self.viz_frame = ttk.LabelFrame(self.root, text="数据可视化", padding=10)
        self.viz_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)


    def log(self, message):
        """记录日志信息"""
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def start_crawl(self):
        """开始爬取 准备工作"""
        # 如果有进程在执行 直接返回
        if self.is_running:
            return

        try:
            # 绑定起始框中的内容
            start_page = int(self.start_page_var.get())
            # 绑定结束框中的内容
            end_page = int(self.end_page_var.get())

            if start_page < 1 or end_page < start_page:
                messagebox.showerror("错误", "页码范围无效")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的页码")
            return

        # 表示当前有进程在运行
        self.is_running = True
        # 清除停止信号
        self.stop_event.clear()
        # 设置显示进度条下方的状态
        self.status_var.set("爬取中...")
        # 禁用开始和结束按钮
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # 创建爬取线程对象
        self.crawl_thread = threading.Thread(target=self.crawl_worker, args=(start_page, end_page))
        # 设置线程为守护线程，确保程序退出时线程能随主程序一起终止
        self.crawl_thread.daemon = True
        # 启动线程，开始执行self.crawl_worker()方法中的爬取逻辑
        self.crawl_thread.start()



    def crawl_worker(self, start_page, end_page):
        """爬取工作线程"""
        # 初始化 不存在则创建+写表头
        init_csv()
        # 计算总爬取页数（如1-10页共10页）
        total_pages = end_page - start_page + 1
        # 初始化总保存记录数，用于最终汇总
        total_saved = 0

        # 循环爬取每一页
        for page in range(start_page, end_page + 1):
            # 子步骤1：检查停止信号，实现优雅终止
            if self.stop_event.is_set():
                # 线程安全记录日志：用户主动停止爬取
                self.root.after(0, lambda: self.log("用户停止爬取"))
                break

            progress = ((page - start_page) / total_pages) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            # 记录日志
            self.root.after(0, lambda pg=page: self.log(f"正在爬取第 {pg} 页..."))

            if page == 1:
                url = 'https://shenzhen.anjuke.com/sale/'
            else:
                url = f'https://shenzhen.anjuke.com/sale/p{page}/'

            # 爬取网页
            # 携带cookie和headers伪装浏览器
            try:
                response = requests.get(url, params={'from': 'HomePage_TopBar'},
                                        cookies=cookies, headers=headers, timeout=10)
                # 检查是否成功
                response.raise_for_status()
                # 解析网页源码：调用parse_page()提取二手房数据，返回数据列表
                data_list = parse_page(response.text)
                # 如果解析到数据
                if data_list:
                     # 保存数据到CSV：调用save_to_csv()，返回当前页保存的记录数
                    count = save_to_csv(data_list)
                    total_saved += count

                    self.root.after(0, lambda c=count: self.log(f"  已保存 {c} 条记录"))
                # 如果未解析到数据
                else:
                    self.root.after(0, lambda: self.log("  未找到数据，可能已到最后一页"))
                    break

                time.sleep(2)

            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log(f"  错误: {err}"))
                continue
        # 爬取结束
        # 线程安全更新进度条到100%（无论是否爬完，都拉满进度）
        self.root.after(0, lambda: self.progress_var.set(100))
        # 线程安全记录总结果：共保存多少条记录
        self.root.after(0, lambda t=total_saved: self.log(f"爬取完成，共保存 {t} 条记录"))
        # 爬取完成回调，重置
        self.root.after(0, self.crawl_finished)

    def crawl_finished(self):
        """爬取完成回调"""
        # 重置爬取状态标记，允许再次启动爬取
        self.is_running = False
        # 启用「开始」按钮，恢复可点击状态
        self.start_btn.config(state=tk.NORMAL)
        #禁用「停止」按钮，恢复初始状态
        self.stop_btn.config(state=tk.DISABLED)
        # 更新状态标签，告知用户爬取任务结束
        self.status_var.set("已完成")

    def stop_crawl(self):
        """停止爬取"""
        self.stop_event.set()
        self.status_var.set("正在停止...")
        self.log("已发送停止信号，等待当前页面完成...")

    def clean_data(self):
        """清洗数据"""
        self.log("正在清洗数据...")
        # 调用全局 clean_data() 函数，执行实际清洗逻辑
        df, message = clean_data()
        # 清洗操作成功完成
        if df is not None:
            self.log(message)
            self.log(f"清洗后数据已保存到 {CLEANED_FILE}")
            messagebox.showinfo("成功", message)
        else:
            self.log(message)
            messagebox.showerror("错误", message)


    def show_visualization(self):

        # 清除之前的可视化 重置展示区域
        for widget in self.viz_frame.winfo_children():
            widget.destroy()

        # 优先使用清洗后的数据文件
        data_file = CLEANED_FILE if os.path.exists(CLEANED_FILE) else CSV_FILE
        # 未找到
        if not os.path.exists(data_file):
            messagebox.showerror("错误", "未找到数据文件，请先爬取数据")
            return

        try:
            # 读取数据并统一预处理
            df = pd.read_csv(data_file, encoding='utf-8-sig')
            if len(df) == 0:
                messagebox.showerror("错误", "数据文件为空")
                return

            # 统一数据预处理（确保字段格式一致） 无论读取的是【原始数据】还是【清洗后数据】，都统一生成绘图所需的「纯数值字段」，保证数据格式一致
            df['总价_数值'] = pd.to_numeric(df['总价(万)'], errors='coerce') if '总价_数值' not in df.columns else df[
                '总价_数值']
            df['面积_数值'] = df['面积'].str.extract(r'(\d+\.?\d*)').astype(float) if '面积_数值' not in df.columns else \
            df['面积_数值']
            df['单价_数值'] = df['单价(元/㎡)'].str.extract(r'(\d+)').astype(float) if '单价_数值' not in df.columns else \
            df['单价_数值']
            df['房间数'] = df['户型'].str.extract(r'(\d+)室').astype(float) if '房间数' not in df.columns else df[
                '房间数']

            self.log(f"正在加载可视化，数据来源: {data_file} ({len(df)} 条记录)")

            # 创建画布 初始化画布
            plt.figure(figsize=(12, 10))
            # 调整子图的布局间距
            plt.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.08, hspace=0.35, wspace=0.3)

            # 1. 各区域平均房价（第一个子图 2行2列第1个位置）
            plt.subplot(2, 2, 1)
            # 按「区域」分组，计算每个区域的房源平均总价 按均价从高到低排序 取前十
            district_price = df.groupby('区域')['总价_数值'].mean().sort_values(ascending=False).head(10)
            # 绘制横向柱状图
            plt.barh(district_price.index, district_price.values, color='steelblue')
            # x轴标签
            plt.xlabel('平均价格 (万)', fontsize=10)
            plt.title('各区域平均房价', fontsize=12, pad=7)
            plt.tick_params(axis='y', labelsize=9)

            # 2. 户型分布（第二个子图2行2列第2个位置）
            plt.subplot(2, 2, 2)
            # 每个房间数对应的房源数量（如3室有120套、2室有80套），返回 Series
            # 房间数「从小到大」排序 过滤掉「房间数为空」的无效数据
            room_counts = df['房间数'].value_counts().sort_index().dropna()
            plt.bar(room_counts.index.astype(str), room_counts.values, color='coral')
            plt.xlabel('房间数', fontsize=10)
            plt.ylabel('数量', fontsize=10)
            plt.title('户型分布', fontsize=12, pad=7)

            # 3. 价格与面积散点图（第三个子图 2行2列第3个位置）
            plt.subplot(2, 2, 3)
            # 删除「面积或总价为空」的房源 数据量 > 500 条：随机采样 500 条
            sample_df = df.dropna(subset=['面积_数值', '总价_数值']).sample(min(500, len(df)))
            # 设置xy轴
            plt.scatter(sample_df['面积_数值'], sample_df['总价_数值'], alpha=0.5, s=10)
            plt.xlabel('面积 (㎡)', fontsize=10)
            plt.ylabel('总价 (万)', fontsize=10)
            plt.title('价格与面积关系', fontsize=12, pad=7)

            # 4. 单价分布（第四个子图 2行2列第4个位置）
            plt.subplot(2, 2, 4)
            # DataFrame 中提取「单价_数值」列，并通过.dropna()删除所有空值（NaN），得到纯数值的 Series
            price_data = df['单价_数值'].dropna()
            # 清洗后的单价数值 价数值分成「30 个等宽区间」
            plt.hist(price_data, bins=30, color='green', alpha=0.7, edgecolor='black')
            plt.xlabel('单价 (元/㎡)', fontsize=10)
            plt.ylabel('数量', fontsize=10)
            plt.title('单价分布', fontsize=12, pad=7)

            # 获取当前figure并嵌入到tkinter
            fig = plt.gcf()  # 获取当前的figure对象
            canvas = FigureCanvasTkAgg(fig, master=self.viz_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            self.log("可视化生成成功")

        except Exception as e:
            self.log(f"可视化错误: {str(e)}")
            messagebox.showerror("错误", f"生成可视化失败: {str(e)}")


def main():
    # 根窗口对象root
    root = tk.Tk()
    app = CrawlerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()