<div align="center">
<h1>B站魔力赏市集爬虫 - 个人版</h1>

一个功能完整的B站魔力赏市集商品信息爬取工具，提供现代化的图形界面和实时数据展示功能。

<img width="1402" height="932" alt="7e5a0dd31dd8a617b93b8cec9040dbf" src="https://github.com/user-attachments/assets/943e35da-da25-49c5-b1c7-9195f5453053" />
<img width="1402" height="932" alt="21edd93676d290b17abd25da6b83f60" src="https://github.com/user-attachments/assets/e94c0817-f415-4dc2-b518-897e38a27595" />
</div>


## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- Edge 或 Chrome 浏览器（用于获取 Cookie）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python main.py
```

## 📦 依赖包

创建 `requirements.txt` 文件：

```
customtkinter>=5.2.0
Pillow>=10.0.0
requests>=2.31.0
```

##  配置 Cookie

1. 打开 B站魔力赏市集网站
2. 使用 Edge 或 Chrome 浏览器登录
3. 按 F12 打开开发者工具
4. 在 Application/存储 → Cookies 中复制 Cookie 值
5. 在程序的「🔑 Cookie」页面粘贴并保存

## ⚠️ 注意事项

1. **Cookie 有效性**：请确保使用的 Cookie 来自 Edge 或 Chrome 浏览器且未过期
2. **采集限制**：每日采集数据建议不超过 20,000 条，避免触发限制
3. **请求频率**：程序已内置 3 秒请求间隔，请勿修改以避免被封禁
4. **数据保存**：程序配置和 Cookie 会自动保存到 `config.json` 文件

### 导出的 CSV 格式

```csv
name,price,link
商品名称,价格,商品链接
```

## 🛠️ 技术栈

- **GUI框架**：CustomTkinter（现代化的 Tkinter 扩展）
- **网络请求**：Requests
- **图像处理**：Pillow
- **数据格式**：JSON、CSV
- **多线程**：Threading（异步爬取）



## 🔍 常见问题

### Q: 爬虫无法正常工作？
A: 请检查以下几点：
- Cookie 是否正确配置且未过期
- 网络连接是否正常
- 是否触发了频率限制（重新登录或等待后重试）

### Q: 如何获取更多数据？
A: 
- 默认情况下会爬取最多 20,000 条数据
- 使用关键词搜索时限制为 200 条
- 可以通过多次运行、不同筛选条件来获取更多数据

## ⚖️ 免责声明

本工具仅供学习和研究使用，使用者应遵守以下规定：

1. 遵守 B站的用户协议和服务条款
2. 不得将爬取的数据用于商业用途
3. 不得对 B站服务器造成过大负担
4. 使用本工具产生的任何后果由使用者自行承担

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件至：[kickningmeri1971@gmail.com]

## 🙏 致谢

感谢所有为本项目提供帮助和建议的朋友们！

---

**⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！**
