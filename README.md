# 🚂 Railway SOCKS5 Backend for EdgeTunnel

<div align="center">

**یک سرور SOCKS5 امن و احراز هویت‌دار برای دیپلوی روی Railway**
<br>
**به عنوان بک‌اند IP ثابت برای پروژه cmliu/edgetunnel**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Railway](https://img.shields.io/badge/Deploy-Railway-purple.svg)](https://railway.app)

</div>

---

## 📋 فهرست مطالب

- [این پروژه چیست؟](#-این-پروژه-چیست)
- [چرا Railway؟](#-چرا-railway)
- [ویژگی‌ها](#-ویژگیها)
- [پیش‌نیازها](#-پیشنیازها)
- [آموزش دیپلوی روی Railway](#-آموزش-دیپلوی-روی-railway)
- [تنظیمات EdgeTunnel](#-تنظیمات-edgetunnel)
- [تست و بررسی](#-تست-و-بررسی)
- [استفاده محلی](#-استفاده-محلی)
- [سوالات متداول](#-سوالات-متداول)
- [امنیت](#-امنیت)
- [لایسنس](#-لایسنس)

---

## 🤔 این پروژه چیست؟

وقتی از **Cloudflare Workers** (مثل پروژه EdgeTunnel) استفاده می‌کنید، IP خروجی شما IPهای کلودفلر است که مدام تغییر می‌کند. بعضی سرویس‌ها این IPها را بلاک می‌کنند.

این پروژه یک **سرور SOCKS5 با احراز هویت** است که روی **Railway** دیپلوی می‌شود و به عنوان **بک‌اند** برای EdgeTunnel عمل می‌کند. نتیجه:

```
شما → Cloudflare Worker → Railway (IP ثابت) → اینترنت
```

✅ IP خروجی همیشه IP سرور Railway خواهد بود — ثابت و پایدار.

---

## 🚀 چرا Railway؟

| ویژگی | توضیح |
|--------|--------|
| 🆓 پلن رایگان | $5 اعتبار ماهانه بدون نیاز به کارت اعتباری |
| ⚡ دیپلوی سریع | اتصال مستقیم به گیت‌هاب |
| 🌐 TCP Support | پشتیبانی از پورت‌های TCP عمومی |
| 📊 مانیتورینگ | لاگ و مانیتورینگ داخلی |
| 🔄 Auto Deploy | با هر پوش، خودکار دیپلوی می‌شود |

---

## ✨ ویژگی‌ها

- 🔐 **احراز هویت اجباری** — Username/Password طبق RFC 1929
- ⚡ **Async I/O** — عملکرد بالا با `asyncio`
- 🛡️ **Rate Limiting** — محدودیت اتصال بر اساس IP
- 🌍 **پشتیبانی کامل** — IPv4، IPv6 و Domain Name
- 🏥 **Health Check** — اندپوینت HTTP برای Railway
- 🔒 **اعتبارسنجی رمز عبور** — حداقل ۱۶ کاراکتر اجباری
- 🚫 **جلوگیری از credential پیش‌فرض** — admin/password قبول نمی‌شود
- 📦 **سبک** — فقط ۲ وابستگی خارجی

---

## 📦 پیش‌نیازها

1. یک اکانت **GitHub** — [github.com](https://github.com)
2. یک اکانت **Railway** — [railway.app](https://railway.app)
3. پروژه **EdgeTunnel** دیپلوی شده روی Cloudflare Workers
4. آشنایی اولیه با خط فرمان (ترمینال)

---

## 🚀 آموزش دیپلوی روی Railway

### مرحله ۱: فورک ریپازیتوری

1. وارد این ریپازیتوری در گیت‌هاب شوید
2. دکمه **Fork** را بزنید
3. نام ریپازیتوری را انتخاب کنید (مثلاً `my-socks5-backend`)
4. **Create Fork** را بزنید

### مرحله ۲: ایجاد پروژه در Railway

1. وارد [railway.app](https://railway.app) شوید
2. **New Project** → **Deploy from GitHub Repo** را انتخاب کنید
3. ریپازیتوری فورک شده را انتخاب کنید
4. صبر کنید تا دیپلوی اولیه انجام شود (هنوز تنظیم نشده)

### مرحله ۳: تنظیم متغیرهای محیطی

در داشبورد Railway، به تب **Variables** بروید و این مقادیر را اضافه کنید:

| Variable | مقدار نمونه | توضیح |
|----------|-------------|-------|
| `SOCKS_USER` | `myuser2026` | نام کاربری دلخواه |
| `SOCKS_PASS` | `Xk9#mP2$vL7nQ4wR8tY1bN6jH3cF` | رمز عبور (حداقل ۱۶ کاراکتر) |
| `SOCKS_PORT` | `443` | پورت SOCKS5 (حتماً 443 باشد) |
| `HEALTH_PORT` | `8080` | پورت Health Check |
| `RATE_LIMIT_MAX` | `50` | حداکثر اتصال در دقیقه per IP |
| `RATE_LIMIT_WINDOW` | `60` | پنجره زمانی rate limit (ثانیه) |
| `CONNECT_TIMEOUT` | `15` | تایم‌اوت اتصال (ثانیه) |

> ⚠️ **خیلی مهم:** `SOCKS_PORT` حتماً باید `443` باشد چون Cloudflare Workers فقط به پورت‌های استاندارد متصل می‌شود.

> ⚠️ **خیلی مهم:** هرگز از رمز عبور ساده استفاده نکنید. یک رمز تصادفی ۲۴+ کاراکتری تولید کنید:
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(24))"
> ```

### مرحله ۴: تنظیم Networking

1. به تب **Settings** → بخش **Networking** بروید
2. روی **Generate Domain** کلیک کنید (برای Health Check HTTP)
3. روی **Add TCP Port** کلیک کنید و پورت `443` را وارد کنید
4. Railway یک آدرس TCP عمومی مثل `roundhouse.proxy.rlwy.net:12345` به شما می‌دهد
5. **این آدرس را یادداشت کنید!**

### مرحله ۵: دیپلوی مجدد

1. به تب **Deployments** بروید
2. اگر دیپلوی قبلی ناموفق بوده، روی **Redeploy** کلیک کنید
3. صبر کنید تا وضعیت به 🟢 **Success** تغییر کند

### مرحله ۶: بررسی سلامت

آدرس دامنه HTTP را در مرورگر باز کنید:
```
https://your-app.up.railway.app/healthz
```

باید این پاسخ را ببینید:
```json
{
  "status": "healthy",
  "service": "socks5-backend",
  "uptime": "0h 5m 23s",
  "uptime_seconds": 323
}
```

✅ تبریک! سرور SOCKS5 شما آماده است.

---

## 🔗 تنظیمات EdgeTunnel

حالا باید EdgeTunnel را طوری تنظیم کنید که از سرور Railway شما به عنوان بک‌اند استفاده کند.

### روش PATH-based (توصیه شده)

طبق داکیومنت cmliu/edgetunnel، URL را به این فرمت بسازید:

```
https://your-worker.workers.dev/socks5=USERNAME:PASSWORD@TCP_HOST:TCP_PORT
```

#### مثال واقعی:

فرض کنید:
- Worker شما: `my-edge.username.workers.dev`
- نام کاربری Railway: `myuser2026`
- رمز عبور Railway: `Xk9mP2vL7nQ4wR8tY1bN6jH3cF`
- آدرس TCP Railway: `roundhouse.proxy.rlwy.net:12345`

URL نهایی:
```
https://my-edge.username.workers.dev/socks5=myuser2026:Xk9mP2vL7nQ4wR8tY1bN6jH3cF@roundhouse.proxy.rlwy.net:12345
```

#### اگر رمز عبور کاراکتر خاص دارد:

کاراکترهای `#`, `$`, `@`, `:`, `/` باید URL Encode شوند:

| کاراکتر | کد |
|---------|-----|
| `#` | `%23` |
| `$` | `%24` |
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `+` | `%2B` |
| `=` | `%3D` |

> 💡 **توصیه:** برای جلوگیری از مشکل، رمز عبوری انتخاب کنید که فقط شامل حروف، اعداد و `_` یا `-` باشد.

### روش Base64

اگر EdgeTunnel از فرمت Base64 پشتیبانی می‌کند:

```bash
# اول credentials را base64 کنید
echo -n "myuser2026:Xk9mP2vL7nQ4wR8tY1bN6jH3cF" | base64
# خروجی: bXl1c2VyMjAyNjpYazltUDJ2TDduUTR3Ujh0WTFiTjZqSDNjRg==
```

سپس URL:
```
https://my-edge.username.workers.dev/socks5://bXl1c2VyMjAyNjpYazltUDJ2TDduUTR3Ujh0WTFiTjZqSDNjRg==@roundhouse.proxy.rlwy.net:12345
```

### فعال‌سازی در EdgeTunnel

1. URL ساخته شده را در مرورگر باز کنید
2. EdgeTunnel کانفیگ‌ها را با IP ثابت Railway تولید می‌کند
3. لینک سابسکریپشن را در کلاینت خود (v2rayN, Clash, NekoBox, etc.) وارد کنید

---

## 🧪 تست و بررسی

### تست ۱: بررسی Health Check
```bash
curl https://your-app.up.railway.app/healthz
```

### تست ۲: بررسی IP خروجی

بعد از اتصال کلاینت به پروکسی:
```bash
curl https://api.ipify.org
```
باید IP سرور Railway را نشان دهد.

### تست ۳: بررسی ثبات IP

چند بار پشت سر هم چک کنید:
```bash
for i in 1 2 3 4 5; do curl -s https://api.ipify.org; echo ""; sleep 2; done
```
همه باید یک IP یکسان برگردانند ✅

### تست ۴: تست مستقیم SOCKS5 (با curl)
```bash
curl --proxy socks5h://myuser2026:Xk9mP2vL7nQ4wR8tY1bN6jH3cF@roundhouse.proxy.rlwy.net:12345 https://api.ipify.org
```

---

## 💻 استفاده محلی

برای تست روی کامپیوتر خودتان:

```bash
# 1. کلون کنید
git clone https://github.com/YOUR_USERNAME/railway-socks5-backend.git
cd railway-socks5-backend

# 2. محیط مجازی بسازید
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. وابستگی‌ها را نصب کنید
pip install -r requirements.txt

# 4. فایل env بسازید
cp .env.example .env

# 5. مقادیر .env را ویرایش کنید
nano .env

# 6. اجرا کنید
python server.py
```

تست محلی:
```bash
curl --proxy socks5h://myuser:mypass@127.0.0.1:443 https://api.ipify.org
```

---

## ❓ سوالات متداول

### IP Railway واقعاً ثابت است؟
در پلن رایگان، Railway IP اختصاصی تضمین نمی‌دهد اما در عمل IP بسیار پایدارتر از Cloudflare Workers است. برای IP ثابت مطلق، پلن Pro Railway یا VPS اختصاصی نیاز دارید.

### چرا پورت 443؟
Cloudflare Workers فقط به پورت‌های استاندارد HTTP/HTTPS (80, 443, 2053, 2083, 2087, 2096, 8443) اجازه اتصال خروجی می‌دهند. پورت 443 مطمئن‌ترین گزینه است.

### آیا بدون احراز هویت می‌توانم اجرا کنم؟
**خیر.** سرور بدون تنظیم `SOCKS_USER` و `SOCKS_PASS` اجرا نمی‌شود. این یک تصمیم عمدی امنیتی است.

### Rate Limit چطور کار می‌کند؟
هر IP می‌تواند حداکثر `RATE_LIMIT_MAX` اتصال در `RATE_LIMIT_WINDOW` ثانیه داشته باشد. اتصالات اضافی رد می‌شوند.

### چطور لاگ‌ها را ببینم؟
در داشبورد Railway → تب **Logs** تمام اتصالات و خطاها قابل مشاهده است.

### آیا این پروژه رایگان است؟
بله، Railway $5 اعتبار ماهانه رایگان می‌دهد. برای استفاده سبک شخصی کافی است. ترافیک سنگین ممکن است اعتبار را زود تمام کند.

---

## 🔒 امنیت

### اقدامات امنیتی پیاده‌سازی شده

| اقدام | توضیح |
|-------|-------|
| احراز هویت اجباری | بدون credential اجرا نمی‌شود |
| حداقل طول رمز | ۱۶ کاراکتر اجباری |
| بلاک credential پیش‌فرض | admin/password رد می‌شود |
| Rate Limiting | جلوگیری از abuse |
| Timeout | جلوگیری از hanging connections |
| لاگ بدون حساسیت | رمز عبور هرگز لاگ نمی‌شود |

### توصیه‌های امنیتی

1. **هرگز** credential ها را در گیت‌هاب کامیت نکنید
2. از رمز عبور تصادفی ۲۴+ کاراکتری استفاده کنید
3. به صورت دوره‌ای رمز عبور را عوض کنید
4. لاگ‌های Railway را مانیتور کنید
5. از `.env` فقط برای توسعه محلی استفاده کنید، نه در production

---

## 📄 لایسنس

این پروژه تحت مجوز [MIT](LICENSE) منتشر شده است.

---

<div align="center">

**ساخته شده با ❤️ برای جامعه فارسی‌زبان**

</div>