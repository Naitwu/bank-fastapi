# Email Template 技術規範文件

本文件用於規範專案中所有 email template（如 activation.html、reset_password.html 等）的生成規則。

## 技術規範

### 1. 模板引擎
- 使用 **Jinja2 模板引擎**

### 2. 模板繼承
所有模板必須繼承：
- `backend/app/core/emails/templates/base.html` (HTML 格式)
- `backend/app/core/emails/templates/base.txt` (純文字格式)

### 3. 內容插槽
- **僅允許** `{% block content %}` 插槽放置內容
- **不得重複定義** header/footer

### 4. 樣式規範
- **嚴禁使用外部 CSS/JS**
- 所有樣式應為 **inline style**

### 5. 資訊安全
- **不得輸出**密碼、token、金鑰等敏感資訊
- 所有連結需含**時效資訊**（例：「此連結有效期限為30分鐘」）

### 6. 格式要求
- 需同時產生 **HTML 格式**與**純文字(TXT)格式**

## 語言與風格

### 1. 用語規範
- 採用**台灣常用商業用語**（繁體中文）
- 用字正式、禮貌、可信任
- **不使用**簡體字或口語化詞

### 2. 主旨格式
範例：`[系統通知] 帳號啟用信`

### 3. 信件結尾
需附註：**「此信件由系統自動寄出，請勿直接回覆。」**

## 檔案命名規範

### 1. 命名格式
- 採用 **snake_case** 命名

### 2. 檔案配對
- 每個信件模板須同時存在 **.html** 與 **.txt** 版本
- 範例：
  - `activation.html` + `activation.txt`
  - `reset_password.html` + `reset_password.txt`

### 3. 存放位置
- 放置於 `backend/app/core/emails/templates/`

## 審查清單

在提交新的 email template 前，請確認以下項目：

- ✅ 繼承 base 模板
- ✅ 台灣用語
- ✅ 無敏感資訊
- ✅ 提供連結時效
- ✅ HTML/TXT 雙版本

## 範例

### HTML 模板範例 (activation.html)

```html
{% extends "base.html" %}

{% block title %}帳號啟用{% endblock %}

{% block header %}帳號啟用確認{% endblock %}

{% block content %}
<p>親愛的 {{ user_name }} 您好，</p>

<p>感謝您註冊 {{ site_name }}。請點擊下方連結以啟用您的帳號：</p>

<p style="text-align: center; margin: 30px 0;">
    <a href="{{ activation_link }}" style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">啟用帳號</a>
</p>

<p><strong>此連結有效期限為30分鐘。</strong></p>

<p>如果您未曾註冊本服務，請忽略此信件。</p>

<p>此信件由系統自動寄出，請勿直接回覆。</p>
{% endblock %}
```

### 純文字模板範例 (activation.txt)

```
{% extends "base.txt" %}

{% block header %}帳號啟用確認{% endblock %}

{% block content %}
親愛的 {{ user_name }} 您好，

感謝您註冊 {{ site_name }}。請複製下方連結至瀏覽器以啟用您的帳號：

{{ activation_link }}

此連結有效期限為30分鐘。

如果您未曾註冊本服務，請忽略此信件。

此信件由系統自動寄出，請勿直接回覆。
{% endblock %}
```

## 相關資源

- [Jinja2 官方文件](https://jinja.palletsprojects.com/)
- Base 模板位置：`backend/app/core/emails/templates/base.html`
- Base 模板位置：`backend/app/core/emails/templates/base.txt`
