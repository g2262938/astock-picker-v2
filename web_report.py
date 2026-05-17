#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日选股/复盘 公开展示页面
密码: Djyqlcfzy@123
"""
import os, re, glob
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.urandom(32)

REPORT_DIR = "/root/.openclaw/workspace/每日选股"
PASSWORD = "Djyqlcfzy@123"

def stock_url(code):
    """生成腾讯财经股票链接"""
    c = str(code).strip()
    # 港股: 5位数字以0开头，或以8/9开头
    if (len(c) == 5 and c[0] == '0') or c.startswith('8') or c.startswith('9'):
        return f'https://gu.qq.com/hk{c}'
    elif c.startswith('688'):
        return f'https://gu.qq.com/sh{c}'
    elif c.startswith('300') or c.startswith('001') or c.startswith('002'):
        return f'https://gu.qq.com/sz{c}'
    elif c.startswith('600') or c.startswith('601') or c.startswith('603'):
        return f'https://gu.qq.com/sh{c}'
    else:
        return f'https://gu.qq.com/sz{c}' 

LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 - 每日选股系统</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f8; color: #1a1a2a; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .login-box { background: #ffffff; padding: 44px 40px; border-radius: 14px; width: 380px; box-shadow: 0 8px 32px rgba(26,42,74,0.10); border: 1px solid #e0e4f0; }
  h2 { text-align: center; color: #1a2a4a; font-size: 22px; margin-bottom: 32px; letter-spacing: 1px; }
  input { width: 100%; padding: 13px 14px; margin: 10px 0; border: 1.5px solid #d0d4e8; border-radius: 8px; box-sizing: border-box; background: #f5f6fa; color: #1a1a2a; font-size: 14px; transition: border-color 0.2s; outline: none; }
  input:focus { border-color: #1a2a4a; background: #fff; }
  button { width: 100%; padding: 13px; background: #1a2a4a; border: none; border-radius: 8px; color: #fff; font-size: 15px; cursor: pointer; margin-top: 18px; font-weight: 500; letter-spacing: 1px; transition: background 0.2s; }
  button:hover { background: #2a3a6a; }
  .error { color: #c0392b; text-align: center; margin-top: 12px; font-size: 13px; }
</style>
</head>
<body>
<div class="login-box">
  <h2>📊 每日选股系统</h2>
  <form method="post">
    <input type="password" name="password" placeholder="请输入访问密码" required>
    <button type="submit">进入</button>
  </form>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>
</body>
</html>
'''

SYSTEMS_PAGE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>系统设计文档 - 每日选股系统</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f8; color: #1a1a2a; min-height: 100vh; }
  header { background: #ffffff; padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #1a2a4a; box-shadow: 0 1px 8px rgba(26,42,74,0.07); }
  header h1 { color: #1a2a4a; font-size: 20px; font-weight: 600; }
  header a { background: #1a2a4a; color: #fff; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; text-decoration: none; }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
  .intro { background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(26,42,74,0.07); border: 1px solid #e8eaf6; }
  .intro h2 { color: #1a2a4a; font-size: 16px; margin-bottom: 10px; }
  .intro p { color: #555; font-size: 14px; line-height: 1.6; }
  .systems-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .sys-card { background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(26,42,74,0.07); border: 1px solid #e8eaf6; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; text-decoration: none; color: inherit; display: block; }
  .sys-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(26,42,74,0.12); }
  .sys-card .icon { font-size: 32px; margin-bottom: 12px; }
  .sys-card h3 { color: #1a2a4a; font-size: 16px; margin-bottom: 8px; }
  .sys-card p { color: #888; font-size: 12px; line-height: 1.5; }
  .sys-card .tag { display: inline-block; background: #eef1f8; padding: 3px 8px; border-radius: 4px; font-size: 11px; color: #555; margin-top: 8px; }
  .doc-section { background: #ffffff; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(26,42,74,0.07); border: 1px solid #e8eaf6; }
  .doc-section h2 { color: #1a2a4a; font-size: 18px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1.5px solid #1a2a4a; }
  .doc-section h3 { color: #1a2a4a; font-size: 14px; margin: 16px 0 8px; padding-left: 12px; border-left: 3px solid #00d4ff; }
  .doc-section p { color: #444; font-size: 13px; line-height: 1.7; margin-bottom: 8px; }
  .doc-section ul { margin: 8px 0 12px 20px; }
  .doc-section li { color: #444; font-size: 13px; line-height: 1.8; }
  .doc-section table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 10px 0; }
  .doc-section th { background: #1a2a4a; color: #ffffff; padding: 8px; text-align: left; }
  .doc-section td { padding: 7px 8px; border-bottom: 1px solid #e8eaf6; color: #1a1a2a; }
  .doc-section tr:hover td { background: #f5f6fa; }
  .toc { background: #eef1f8; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
  .toc h3 { margin-bottom: 10px; color: #1a2a4a; }
  .toc a { display: block; padding: 4px 0; color: #0066cc; font-size: 13px; text-decoration: none; }
  .toc a:hover { text-decoration: underline; }
  .building { text-align: center; padding: 40px; color: #aaa; font-size: 14px; }
  .building .spinner { font-size: 24px; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }
  .doc-section h3 { font-size: 15px; color: #1a2a4a; margin-top: 28px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #e8ecf4; }
  .doc-section h4 { font-size: 14px; color: #2a3a5a; margin-top: 18px; margin-bottom: 8px; font-weight: 600; }
  .doc-section { line-height: 1.75; font-size: 14px; color: #444; background: #fff; border-radius: 10px; padding: 24px 28px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(26,42,74,0.06); }
  .doc-section p { margin: 10px 0; line-height: 1.85; color: #444; }
  .doc-section table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 13px; border-radius: 8px; overflow: hidden; border: 1px solid #dde2ee; }
  .doc-section table th { background: #f0f2f8; padding: 9px 14px; text-align: left; border-bottom: 2px solid #d0d8ec; font-weight: 650; color: #1a2a4a; }
  .doc-section table td { padding: 8px 14px; border-bottom: 1px solid #eef0f6; color: #555; }
  .doc-section table tr:last-child td { border-bottom: none; }
  .doc-section table tr:hover td { background: #f8f9fd; }
  .doc-section pre { background: #1a2a4a; border-radius: 8px; padding: 16px; overflow-x: auto; font-size: 12px; line-height: 1.6; margin: 14px 0; color: #e0e8f0; }
  .doc-section code { background: #f0f2f8; padding: 1px 5px; border-radius: 3px; font-size: 12px; color: #c0392b; font-family: 'Courier New', monospace; }
  .doc-section pre code { background: none; padding: 0; color: inherit; font-size: 12px; }
  .doc-section ul, .doc-section ol { padding-left: 22px; margin: 10px 0; }
  .doc-section li { margin: 5px 0; line-height: 1.7; color: #444; }
  .doc-section strong { color: #1a2a4a; font-weight: 650; }
  .doc-section hr { border: none; border-top: 1px solid #e8ecf4; margin: 24px 0; }
  .doc-section blockquote { border-left: 4px solid #4a6fa5; padding: 8px 16px; margin: 12px 0; background: #f0f5ff; border-radius: 0 6px 6px 0; color: #555; }
  .version-bar { background: #eef1f8; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .version-bar .label { font-size: 13px; color: #555; font-weight: 500; }
  .version-btn { padding: 5px 12px; border-radius: 6px; font-size: 12px; text-decoration: none; border: 1px solid #d0d4e8; color: #555; background: #fff; cursor: pointer; }
  .version-btn:hover { background: #f5f6fa; }
  .version-btn.active { background: #1a2a4a; color: #fff; border-color: #1a2a4a; }
  .version-btn.latest { border-color: #2e7d32; color: #2e7d32; font-weight: 600; }
  .version-btn.latest.active { background: #2e7d32; color: #fff; font-weight: 600; }
  footer { text-align: center; padding: 24px; color: #bbb; font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>📊 每日选股 & 复盘系统</h1>
  <div style="display:flex;align-items:center;gap:10px">
    <a href="/" style="background:#e94560;color:#fff;border:none;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">🏠 首页</a>
    <a href="/systems" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">📚 系统文档</a>
    <a href="/download/docs" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">📥 下载文档</a>
    <a href="/download/code" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">💾 下载代码</a>
  </div>
</header>
<div class="container">
  <div class="intro">
    <h2>关于本文档</h2>
    <p>本文档记录选股系统、复盘系统、量化资讯系统的设计思路、策略逻辑、运行机制和版本历史。每个系统独立演进，方便理解底层逻辑和持续迭代优化。</p>
  </div>

  <div class="toc">
    <h3>导航</h3>
    <a href="#stock">📊 选股系统</a>
    <a href="#review">📋 复盘系统</a>
    <a href="#news">📰 量化资讯</a>
  </div>

  {% for sys in systems %}
  <div class="doc-section" id="{{ sys.id }}">
    <h2>{{ sys.icon }} {{ sys.name }}</h2>
    {% if sys.desc %}<p style="color:#666;margin-bottom:16px">{{ sys.desc }}</p>{% endif %}
    {% if sys.versions %}
    <div class="version-bar">
      <span class="label">📌 版本切换：</span>{% for v in sys.versions %} <a href="{{ v.url }}" class="version-btn {{ 'active' if v.current else '' }} {{ 'latest' if v.latest else '' }}" target="_self">{{ v.label }}{% if v.latest and not v.current %}（最新版）{% endif %}{% if v.current %}（当前）{% endif %}</a>{% endfor %}
    </div>
    {% endif %}
    <div class="toc">
      <h3>目录</h3>
      {% for sec in sys.sections %}
      <a href="#{{ sys.id }}-{{ loop.index }}">{{ sec.title }}</a>
      {% endfor %}
    </div>
    {% for sec in sys.sections %}
    <h3 id="{{ sys.id }}-{{ loop.index }}">{{ sec.title }}</h3>
    {{ sec.content | safe }}
    {% endfor %}
  </div>
  {% endfor %}

  <div class="doc-section">
    <h2>🗂️ 相关文件</h2>
    <table>
      <tr><th>系统</th><th>文件</th><th>说明</th></tr>
      {% for f in files %}
      <tr><td>{{ f.sys }}</td><td>{{ f.name }}</td><td>{{ f.note }}</td></tr>
      {% endfor %}
    </table>
  </div>
</div>
<footer>每日选股系统 · 仅供参考，不构成投资建议</footer>
</body>
</html>
'''

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日选股系统</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f8; color: #1a1a2a; min-height: 100vh; }
  header { background: #ffffff; padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #1a2a4a; box-shadow: 0 1px 8px rgba(26,42,74,0.07); }
  header h1 { color: #1a2a4a; font-size: 20px; font-weight: 600; }
  header .meta { color: #888; font-size: 13px; }
  .logout { background: #1a2a4a; color: #fff; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
  .section { background: #ffffff; border-radius: 12px; padding: 22px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(26,42,74,0.07); border: 1px solid #e8eaf6; }
  .section h2 { color: #1a2a4a; font-size: 16px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1.5px solid #1a2a4a; }
  .mood-bar { background: #eef1f8; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; font-size: 14px; border-left: 3px solid #1a2a4a; }
  .hot-sectors { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
  .hot-sectors span { background: #f5f6fa; padding: 4px 10px; border-radius: 4px; font-size: 13px; color: #e65100; border: 1px solid #d0d4e8; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
  th { background: #1a2a4a; color: #ffffff; padding: 9px 8px; text-align: left; font-weight: 500; }
  td { padding: 8px 6px; border-bottom: 1px solid #e8eaf6; color: #1a1a2a; }
  tr:hover td { background: #f5f6fa; }
  tr:last-child td { border-bottom: none; }
  .score { font-weight: bold; }
  .score-high { color: #2e7d32; }
  .score-mid { color: #e65100; }
  .score-low { color: #c0392b; }
  .notice { background: #fff8e1; border-left: 3px solid #e65100; padding: 10px 14px; border-radius: 4px; font-size: 13px; margin-top: 10px; color: #3d2600; }
  .date-tabs { margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
  .date-tabs a { padding: 6px 14px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500; }
  .date-tabs a.active { background: #1a2a4a; color: #fff; }
  .date-tabs a.inactive { background: #ffffff; color: #888; border: 1px solid #d0d4e8; }
  .no-data { text-align: center; padding: 40px; color: #aaa; font-size: 14px; }
  .sub-label { background: #f5f6fa; border-radius: 6px; padding: 8px 12px; margin: 10px 0; font-size: 12px; color: #555; }
  .idx-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0; }
  .idx-item { background: #eef1f8; border-radius: 8px; padding: 10px 14px; text-align: center; }
  .idx-item .val { font-size: 16px; font-weight: 600; color: #1a2a4a; }
  .idx-item .lab { font-size: 11px; color: #888; margin-top: 2px; }
  .tag-sector { background: #f0f2f8; padding: 2px 8px; border-radius: 3px; margin-right: 4px; font-size: 12px; color: #555; border: 1px solid #d0d4e8; }
  footer { text-align: center; padding: 24px; color: #bbb; font-size: 12px; }
  .us-monitor { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 10px 0; }
  .us-card { background: #eef1f8; border-radius: 8px; padding: 12px 14px; text-align: center; }
  .us-card .ticker { font-size: 15px; font-weight: bold; color: #1a2a4a; }
  .us-card .price { font-size: 18px; font-weight: bold; margin: 4px 0; }
  .us-card .change { font-size: 12px; padding: 2px 8px; border-radius: 4px; display: inline-block; }
  .us-card .pos { color: #4ade80; background: #1b4332; }
  .us-card .neg { color: #f87171; background: #4a1511; }
  .us-alert { padding: 10px 14px; border-radius: 6px; margin-top: 8px; font-size: 13px; }
  .us-alert-ok { background: #1b4332; border-left: 3px solid #4ade80; color: #4ade80; }
  .us-alert-warn { background: #2d2006; border-left: 3px solid #fbbf24; color: #fbbf24; }
  .us-alert-danger { background: #4a1511; border-left: 3px solid #f87171; color: #f87171; }
</style>
</head>
<body>
<header>
  <h1>📊 每日选股 & 复盘系统</h1>
  <div style="display:flex;align-items:center;gap:10px">
    <a href="/" style="background:#e94560;color:#fff;border:none;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">🏠 首页</a>
    <a href="/systems" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">📚 系统文档</a>
    <a href="/download/docs" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">📥 下载文档</a>
    <a href="/download/code" style="background:#f5f6fa;color:#1a2a4a;border:1px solid #d0d4e8;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500">💾 下载代码</a>
    <span class="meta">{{ update_time }}</span>
    <button class="logout" onclick="location.href='/logout'">退出</button>
  </div>
</header>
<div class="container">
  <div class="date-tabs">
    {% for tab_date, tab_label in date_tabs %}
      <a href="/?date={{ tab_date }}" class="{{ 'active' if tab_date == current_date else 'inactive' }}">{{ tab_label }}</a>
    {% endfor %}
  </div>

  {% if page_data %}
    {% if page_data.phase %}
    <div class="section">
      <h2>🌡️ 情绪日历</h2>
      <div class="mood-bar">📊 阶段：{{ page_data.phase }} · 建议仓位：{{ page_data.仓位 }} · 综合打分：{{ page_data.score }}分</div>
      {% if page_data.indexes %}
      <div class="idx-grid">
        {% for idx in page_data.indexes %}
        <div class="idx-item"><div class="val">{{ idx.val }}</div><div class="lab">{{ idx.name }} {{ idx.pct }}</div></div>
        {% endfor %}
      </div>
      {% endif %}
      {% if page_data.advice %}
      <div class="sub-label">💡 操作建议：{{ page_data.advice }}</div>
      {% endif %}
    </div>
    {% endif %}

    {% if page_data.sectors %}
    <div class="section">
      <h2>🔥 板块热度</h2>
      <table>
        <tr><th>#</th><th>板块</th><th>热度</th></tr>
        {% for row in page_data.sectors %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{% for tag in row.tags %}<span class="tag-sector">{{ tag }}</span>{% endfor %}</td>
          <td>{{ row.heat }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    {% if page_data.stable %}
    <div class="section">
      <h2>🟢 稳健模式</h2>
      <div class="sub-label">三路并行 · 09:28推送</div>
      <table>
        <tr><th>#</th><th>名称</th><th>代码</th><th>竞价价</th><th>竞价涨幅</th><th>竞价分</th><th>四维分</th><th>总分</th><th>60日位置</th><th>板块</th><th>来源</th><th>催化</th></tr>
        {% for row in page_data.stable %}
        <tr>
          <td>{{ row.rank }}</td>
          <td><a href="{{ row.url }}" target="_blank" style="color:#0066cc;text-decoration:none">{{ row.name }}</a></td>
          <td>{{ row.code }}</td>
          <td>{{ row.auction_price }}</td>
          <td>{{ row.auction_change }}</td>
          <td>{{ row.auction_score }}</td>
          <td>{{ row.dimension_score }}</td>
          <td class="score score-high">{{ row.total_score }}</td>
          <td>{{ row.pos }}</td>
          <td>{{ row.sector }}</td>
          <td>{{ row.pool_type }}</td>
          <td>{{ row.catalysis }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    {% if page_data.strong %}
    <div class="section">
      <h2>🟠 强势模式</h2>
      <div class="sub-label">三路并行 · 09:28推送</div>
      <table>
        <tr><th>#</th><th>名称</th><th>代码</th><th>竞价价</th><th>竞价涨幅</th><th>竞价分</th><th>四维分</th><th>总分</th><th>60日位置</th><th>板块</th><th>来源</th><th>催化</th></tr>
        {% for row in page_data.strong %}
        <tr>
          <td>{{ row.rank }}</td>
          <td><a href="{{ row.url }}" target="_blank" style="color:#0066cc;text-decoration:none">{{ row.name }}</a></td>
          <td>{{ row.code }}</td>
          <td>{{ row.auction_price }}</td>
          <td>{{ row.auction_change }}</td>
          <td>{{ row.auction_score }}</td>
          <td>{{ row.dimension_score }}</td>
          <td class="score score-high">{{ row.total_score }}</td>
          <td>{{ row.pos }}</td>
          <td>{{ row.sector }}</td>
          <td>{{ row.pool_type }}</td>
          <td>{{ row.catalysis }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    {% if page_data.canslim %}
    <div class="section">
      <h2>🌟 CAN SLIM融合选股TOP10</h2>
      <div class="sub-label">基于昨日涨停池（强势股短线策略）</div>
      <table>
        <tr><th>#</th><th>名称</th><th>代码</th><th>评分</th><th>建议</th><th>位置</th><th>均线</th><th>量价</th><th>板块</th></tr>
        {% for row in page_data.canslim %}
        <tr>
          <td>{{ row.rank }}</td>
          <td><a href="{{ row.url }}" target="_blank" style="color:#0066cc;text-decoration:none">{{ row.name }}</a></td>
          <td>{{ row.code }}</td>
          <td class="score {{ row.score_class }}">{{ row.score }}</td>
          <td>{{ row.action }}</td>
          <td>{{ row.pos }}</td>
          <td>{{ row.ma }}</td>
          <td>{{ row.vol }}</td>
          <td>{{ row.board }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    {% if page_data.holdings %}
    <div class="section">
      <h2>📋 持仓跟踪</h2>
      <table>
        <tr><th>名称</th><th>代码</th><th>评分</th><th>竞价</th><th>收盘</th><th>涨跌</th><th>状态</th><th>行业</th></tr>
        {% for row in page_data.holdings %}
        <tr>
          <td><a href="{{ row.url }}" target="_blank" style="color:#0066cc;text-decoration:none">{{ row.name }}</a></td>
          <td>{{ row.code }}</td>
          <td class="score {{ row.score_class }}">{{ row.score }}</td>
          <td>{{ row.open }}</td>
          <td>{{ row.close }}</td>
          <td>{{ row.change }}</td>
          <td>{{ row.status }}</td>
          <td>{{ row.board }}</td>
        </tr>
        {% endfor %}
      </table>
      {% if page_data.tomorrow %}
      <div class="notice">📋 明日注意：{{ page_data.tomorrow }}</div>
      {% endif %}
    </div>
    {% endif %}

    {% if page_data.redlines %}
    <div class="section">
      <h2>🔒 红线说明（双模式共用）</h2>
      <table>
        <tr><th>#</th><th>红线条件</th><th>稳健模式</th><th>强势模式</th></tr>
        {% for row in page_data.redlines %}
        <tr>
          <td>{{ row.num }}</td>
          <td>{{ row.cond }}</td>
          <td>{{ row.steady }}</td>
          <td>{{ row.strong }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    <div class="section">
      <h2>🌐 美股监控</h2>
      <div class="us-monitor">
        <div class="us-card"><div class="ticker">SPY</div><div class="price" id="us-spy-price">--</div><div class="change" id="us-spy-pct">--</div></div>
        <div class="us-card"><div class="ticker">QQQ</div><div class="price" id="us-qqq-price">--</div><div class="change" id="us-qqq-pct">--</div></div>
        <div class="us-card"><div class="ticker">DIA</div><div class="price" id="us-dia-price">--</div><div class="change" id="us-dia-pct">--</div></div>
      </div>
      <div class="us-alert us-alert-ok" id="us-alert-box">✅ 正常：市场平稳</div>
    </div>

    <div class="section">
      <h2>📈 A股宽基指数</h2>
      <div class="idx-grid" id="a-index-grid">
        <div class="idx-item"><div class="val" id="a-idx-0-pct">--</div><div class="lab" id="a-idx-0-name">加载中...</div></div>
        <div class="idx-item"><div class="val" id="a-idx-1-pct">--</div><div class="lab" id="a-idx-1-name">--</div></div>
        <div class="idx-item"><div class="val" id="a-idx-2-pct">--</div><div class="lab" id="a-idx-2-name">--</div></div>
      </div>
      <div class="sub-label" style="margin-top:8px" id="a-sentiment">🏭 市场情绪：加载中...</div>
    </div>
  {% else %}
  <div class="section"><div class="no-data">暂无 {{ current_date_label }} 的报告数据</div></div>
  {% endif %}
</div>
<script>
async function refreshIndexes() {
  try {
    const r = await fetch('/api/indexes');
    const d = await r.json();
    // A股
    const aNames = ['上证指数', '创业板指', '科创50'];
    const aFiltered = (d.a || []).filter(x => aNames.includes(x.name));
    aFiltered.slice(0, 3).forEach((item, i) => {
      const pctEl = document.getElementById('a-idx-' + i + '-pct');
      const nameEl = document.getElementById('a-idx-' + i + '-name');
      if (pctEl) { pctEl.textContent = item.pct + '%'; pctEl.className = 'val ' + (item.up ? 'idx-up' : 'idx-down'); }
      if (nameEl) nameEl.textContent = item.name + ' ' + item.val;
    });
    const sentEl = document.getElementById('a-sentiment');
    if (sentEl && d.a_sentiment) sentEl.textContent = '🏭 市场情绪：' + d.a_sentiment;
    // 美股
    const tickers = {'SPY': 'spy', 'QQQ': 'qqq', 'DIA': 'dia'};
    (d.us || []).forEach(item => {
      const key = tickers[item.ticker];
      if (!key) return;
      const priceEl = document.getElementById('us-' + key + '-price');
      const pctEl = document.getElementById('us-' + key + '-pct');
      if (priceEl) priceEl.textContent = item.price;
      if (pctEl) {
        pctEl.textContent = (item.pct >= 0 ? '+' : '') + item.pct.toFixed(2);
        pctEl.className = 'change ' + (item.pct >= 0 ? 'pos' : 'neg');
      }
    });
    const alertEl = document.getElementById('us-alert-box');
    if (alertEl && d.us_alert) {
      alertEl.textContent = d.us_alert;
      alertEl.className = 'us-alert us-alert-' + (d.us_alert_class || 'ok');
    }
  } catch(e) { console.error('Index refresh failed:', e); }
}
refreshIndexes();
setInterval(refreshIndexes, 300000); // 5分钟刷新
</script>
<footer>每日选股系统 · 更新于 {{ update_time }} · 仅供参考，不构成投资建议</footer>
</body>
</html>
'''

# ========== 报告解析 ==========
def load_selections_from_db(date_str, db_path='/root/.openclaw/workspace/data/stock_pool.db'):
    """从数据库加载选股结果 v2"""
    import sqlite3 as _sql
    try:
        conn = _sql.connect(db_path)
        cur = conn.cursor()
        # 尝试新表 stock_selection_v2
        cur.execute(
            "SELECT mode, rank, stock_code, stock_name, sector, pool_type, "
            "       position_60d, catalysis, auction_price, auction_change, "
            "       auction_score, dimension_score, total_score "
            "FROM stock_selection_v2 "
            "WHERE select_date=? ORDER BY mode, rank",
            (date_str,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return None, None
        stable, strong = [], []
        for (mode, rank, code, name, sector, pool_type,
             pos, catalysis, auction_price, auction_change,
             auction_score, dimension_score, total_score) in rows:
            rank_emoji = ['🥇','🥈','🥉','4️⃣','5️⃣'][rank-1] if rank <= 5 else str(rank)
            item = {
                'name': name, 'code': code,
                'sector': sector or '',
                'pool_type': pool_type or '',
                'pos': f'{pos:.0f}%' if pos else '-',
                'catalysis': catalysis or '',
                'auction_price': f'{auction_price:.2f}' if auction_price else '-',
                'auction_change': f'{auction_change:+.2f}%' if auction_change else '-',
                'auction_score': f'{auction_score:.0f}' if auction_score else '-',
                'dimension_score': f'{dimension_score:.0f}' if dimension_score else '-',
                'total_score': f'{total_score:.0f}' if total_score else '-',
                'rank': rank_emoji,
                'url': stock_url(code)}
            if mode == '稳健':
                stable.append(item)
            else:
                strong.append(item)
        return stable, strong
    except:
        return None, None



def parse_comprehensive_report(content):
    """解析综合选股报告"""
    result = {}

    # 情绪
    m = re.search(r'情绪阶段:\s*\*\*([^\*]+)\*\*', content)
    if m: result['phase'] = m.group(1).strip()
    m = re.search(r'建议仓位:\s*\*\*([^\*]+)\*\*', content)
    if m: result['仓位'] = m.group(1).strip()
    m = re.search(r'综合打分:\s*(\d+)分', content)
    if m: result['score'] = m.group(1).strip()
    m = re.search(r'操作建议:\s*([^\n]+)', content)
    if m: result['advice'] = m.group(1).strip()

    # 指标 - from **1️⃣ to **2️⃣
    m1 = content.find('\u20e3\ufe0f')
    m2 = content.find('\u20e3\ufe0f', m1 + 1) if m1 >= 0 else -1
    # Fallback: find by section header text
    if m1 < 0:
        m1 = content.find('\u20e3')
        m2 = content.find('\u20e3', m1 + 1) if m1 >= 0 else -1
    if m1 >= 0 and m2 > m1:
        tbl = content[m1:m2]
        for line in tbl.split('\n'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 3 and re.match(r'\d', cells[0]) and '|' not in cells[0]:
                result.setdefault('indexes', []).append({'name': cells[1], 'val': cells[0], 'pct': cells[2]})
        result['indexes'] = result.get('indexes', [])[:4]

    # 板块
    sec = re.search(r'板块催化剂TOP5:(.*?)(?=---)', content, re.DOTALL)
    if sec:
        rows = []
        for line in sec.group(1).strip().split('\n'):
            em = re.search(r'[\u20e3\ufe0f\u20e3]+\s*(.*?)\s*([\U0001f525\U0001f526]+)', line)
            if em:
                rows.append({'rank': '', 'tags': [em.group(1).strip()], 'heat': em.group(2)})
            else:
                # Try emoji pattern
                for pat in [r'[\u20e3\ufe0f]+\s*(.*?)\s*([\U0001f525]+)', r'([\U0001f525\U0001f526]+)']:
                    em2 = re.search(pat, line)
                    if em2:
                        rows.append({'rank': '', 'tags': [line.split('|')[1].strip() if '|' in line else line.strip()], 'heat': em2.group(1)})
                        break
        result['sectors'] = rows[:5]

    def parse_table(block, code_list=None):
        """解析选股表格，code_list用于批量查询行业"""
        rows = []
        for line in block.split('\n'):
            line = line.strip()
            if not line or '---' in line or '\U0001f4a1' in line or '\U0001f4cc' in line: continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 10 and cells[1] not in ('名称', '#', '') and not cells[0].startswith('-'):
                try:
                    name = cells[1].replace('**', '')
                    code = cells[2]
                    sv = int(re.search(r'\d+', cells[3]).group())
                    rows.append({
                        'name': name, 'code': code, 'score': f'**{sv}**',
                        'score_class': 'score-high' if sv >= 60 else ('score-mid' if sv >= 40 else 'score-low'),
                        'pos': cells[4], 'turnover': cells[5], 'amount': cells[6] + '亿',
                        'ma': cells[7], 'vol': cells[8], 'board': cells[9], 'rank': cells[0]})
                except: pass
        # 行业富化：从EM获取真实行业（MAIN_BUSINESS首句）
        if code_list is not None:
            code_to_industry = _fetch_industry_batch(code_list)
            for r in rows:
                ind = code_to_industry.get(r['code'], '')
                r['board'] = ind if ind else r['board']
        return rows

    def _fetch_industry_batch(codes, db_path='/root/.openclaw/workspace/data/stock_pool.db'):
        """从本地缓存/THS/EM获取个股行业，优先用THS申万行业"""
        if not codes: return {}
        import sqlite3 as _sql, requests as _req
        from datetime import datetime

        _headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://basic.10jqka.com.cn/'}

        # Step 1: 查本地缓存
        conn = _sql.connect(db_path)
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS stock_industry (code TEXT PRIMARY KEY, industry TEXT NOT NULL DEFAULT "", source TEXT NOT NULL DEFAULT "THS", updated_at TEXT NOT NULL)')
        cur.execute('SELECT code, industry FROM stock_industry WHERE code IN ({})'.format(
            ','.join('?' * len(codes))), codes)
        cached = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()

        # Step 2: 找出本地没有的
        missing = [c for c in codes if c not in cached]
        if not missing:
            return cached

        new_results = {}

        # Step 3a: 优先从THS F10页面获取申万行业（简洁精确）
        for c in missing:
            try:
                url = f'https://basic.10jqka.com.cn/{c}/company.html'
                r = _req.get(url, timeout=5, headers=_headers)
                r.encoding = 'gbk'
                m = re.search(r'申万行业[：:]*\s*</strong><span>([^<]+)</span>', r.text)
                if m:
                    ind = m.group(1).strip()
                    if ind:
                        new_results[c] = ind
            except:
                pass

        # Step 3b: 未命中则用EM MAIN_BUSINESS兜底
        for c in missing:
            if c in new_results:
                continue
            try:
                url = (f'https://datacenter.eastmoney.com/api/data/v1/get'
                       f'?reportName=RPT_F10_ORG_BASICINFO'
                       f'&columns=SECURITY_CODE,MAIN_BUSINESS'
                       f'&filter=(SECURITY_CODE=%22{c}%22)')
                r2 = _req.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'})
                d = r2.json()
                if d.get('success') and d['result'] and d['result'].get('data'):
                    mb = d['result']['data'][0].get('MAIN_BUSINESS', '')
                    seg = mb.split('。')[0].split('、')[0].split('，')[0].strip()
                    if seg and len(seg) <= 14:
                        new_results[c] = seg
            except:
                pass

        # Step 4: 写入本地缓存
        if new_results:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn2 = _sql.connect(db_path)
            cur2 = conn2.cursor()
            for c, ind in new_results.items():
                cur2.execute('INSERT OR REPLACE INTO stock_industry (code, industry, source, updated_at) VALUES (?, ?, ?, ?)',
                             (c, ind, 'THS', now))
            conn2.commit()
            conn2.close()

        # 合并结果
        cached.update(new_results)
        return cached

    # 稳健: 稳健模式 start → first 💡
    s_start = content.find('\u7a33\u5065\u6a21\u5f0f')
    s_end = content.find('\U0001f4a1', s_start) if s_start >= 0 else -1
    if s_start >= 0 and s_end > s_start:
        block = content[s_start:s_end]
        # 先提取稳健表格的codes用于行业查询
        stable_codes = re.findall(r'\| ([0-9]{6}) \|', block)
        result['stable'] = parse_table(block, stable_codes)[:5]

    # 强势: **4️⃣ 强势模式 start → first 💡
    ss_start = content.find('\u5f3a\u52bf\u6a21\u5f0f')
    ss_end = content.find('\U0001f4a1', ss_start) if ss_start >= 0 else -1
    if ss_start >= 0 and ss_end > ss_start:
        block = content[ss_start:ss_end]
        strong_codes = re.findall(r'\| ([0-9]{6}) \|', block)
        result['strong'] = parse_table(block, strong_codes)[:5]

    # 红线
    rl_idx = content.find('\U0001f510\U0001f3f9')
    if rl_idx < 0: rl_idx = content.find('红线6条说明')
    if rl_idx < 0: rl_idx = content.find('红线说明')
    if rl_idx > 0:
        rl_end = content.find('\U0001f7e2', rl_idx)
        rows = []
        for line in content[rl_idx:rl_end].split('\n'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 4 and re.match(r'\d', cells[0]) and cells[1]:
                rows.append({'num': cells[0], 'cond': cells[1], 'steady': cells[2], 'strong': cells[3]})
        result['redlines'] = rows[:6]

    return result

def load_holdings_from_db(date_str, db_path='/root/.openclaw/workspace/data/stock_pool.db'):
    """从数据库加载持仓复盘数据，行业使用THS申万行业（stock_industry）"""
    import sqlite3 as _sql
    try:
        conn = _sql.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT h.code, h.name, h.score, h.open_price, h.close_price, h.change_pct, h.status, "
            "       COALESCE(NULLIF(i.industry, ''), '--') as industry "
            "FROM stock_holdings_review h "
            "LEFT JOIN stock_industry i ON h.code=i.code "
            "WHERE h.review_date=? ORDER BY h.score DESC",
            (date_str,))
        rows = cur.fetchall()
        conn.close()
        if not rows: return None
        result = []
        for code, name, score, open_price, close_price, change_pct, status, industry in rows:
            sv = score if score else 0
            result.append({
                'name': name, 'code': code,
                'score': '**%d**' % sv if sv else '**--**',
                'score_class': 'score-high' if sv >= 60 else ('score-mid' if sv >= 40 else 'score-low'),
                'open': '%.2f' % open_price if open_price else '--',
                'close': '%.2f' % close_price if close_price else '--',
                'change': '%+.2f%%' % change_pct if change_pct else '--',
                'status': status or '--',
                'board': industry[:14] if industry and industry != '--' else '--',
                'url': stock_url(code)
            })
        return result
    except: return None



def parse_review_report(content):
    """解析复盘报告"""
    result = {}
    m = re.search(r'\*\*【持仓评分】\*\*.*?(\|.+\|[\s\S]+?)(?=\*\*【|$)', content, re.DOTALL)
    if m:
        rows = []
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if not line.startswith('|') or '---' in line or line == '|': continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 7 and '名称' not in cells[0]:
                try:
                    score_raw = re.sub(r'\*\*', '', cells[2])
                    sv = int(re.search(r'\d+', score_raw).group()) if re.search(r'\d+', score_raw) else 0
                    rows.append({
                        'name': cells[0], 'code': cells[1],
                        'score': score_raw,
                        'score_class': 'score-high' if sv >= 60 else ('score-mid' if sv >= 40 else 'score-low'),
                        'open': cells[3], 'close': cells[4], 'change': cells[5], 'status': cells[6],
                        'url': stock_url(cells[1]),
                    })
                except: pass
        result['holdings'] = rows
    m = re.search(r'\*\*【明日注意】\*\*.*?\n(.+)', content)
    if m: result['tomorrow'] = m.group(1).strip()
    return result

# ========== 路由 ==========
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_PAGE, error='密码错误，请重试')

    current_date = request.args.get('date', datetime.now().strftime('%Y%m%d'))
    all_files = sorted(glob.glob(f"{REPORT_DIR}/综合选股-*.md"), reverse=True)
    if not all_files:
        all_files = sorted(glob.glob(f"{REPORT_DIR}/选股-*.md"), reverse=True)

    date_tabs = []
    found = False
    for f in all_files[:10]:
        m = re.search(r'(\d{8})', os.path.basename(f))
        if m:
            d = m.group(1)
            if d == current_date: found = True
            date_tabs.append((d, f"{d[:4]}-{d[4:6]}-{d[6:8]}"))
    if not found and date_tabs:
        current_date = date_tabs[0][0]
    current_date_label = f"{current_date[:4]}-{current_date[4:6]}-{current_date[6:8]}"

    page_data = {}
    # 优先从数据库加载选股结果
    stable, strong = load_selections_from_db(current_date)
    if stable is not None:
        page_data['stable'] = stable
        page_data['strong'] = strong if strong else []
    else:
        # 兜底：从markdown报告解析
        comp_file = f"{REPORT_DIR}/综合选股-{current_date}.md"
        if os.path.exists(comp_file):
            parsed = parse_comprehensive_report(open(comp_file, encoding='utf-8').read())
            if parsed:
                page_data = parsed

    rev_file = f"{REPORT_DIR}/复盘-{current_date}.md"
    if os.path.exists(rev_file):
        rev = parse_review_report(open(rev_file, encoding='utf-8').read())
        if rev:
            if not page_data: page_data = {}
            # 优先从数据库加载持仓数据
            holdings = load_holdings_from_db(current_date)
            page_data['holdings'] = holdings if holdings else rev.get('holdings', [])
            page_data['tomorrow'] = rev.get('tomorrow', '')

    # 加载美股数据（从 us_stock_monitor.py 缓存文件）
    try:
        import subprocess, json
        result = subprocess.run(
            ['/root/.openclaw/workspace/venv/bin/python3', '/root/.openclaw/workspace/scripts/us_quote.py'],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout
        us_items = []
        for line in output.split('\n'):
            m = re.search(r'(\bSPY\b|\bQQQ\b|\bDIA\b):([\d.]+):([+-]?[\d.]+)', line)
            if m:
                ticker, price, pct = m.group(1), m.group(2), float(m.group(3))
                us_items.append({'ticker': ticker, 'price': price, 'pct': pct, 'pct_str': f'{pct:+.2f}'})
        if len(us_items) >= 1:
            page_data['us_data'] = us_items[:3]
            spy_pct = next((x['pct'] for x in us_items if x['ticker'] == 'SPY'), 0)
            if spy_pct <= -3:
                page_data['us_alert'] = '🔴 严重暴跌！立即关注风险！'
                page_data['us_alert_class'] = 'us-alert-danger'
            elif spy_pct <= -1.5:
                page_data['us_alert'] = '🟠 较大跌幅，注意风险！'
                page_data['us_alert_class'] = 'us-alert-danger'
            elif spy_pct <= -0.5:
                page_data['us_alert'] = '🟡 注意：标普500下跌超过0.5%'
                page_data['us_alert_class'] = 'us-alert-warn'
            else:
                page_data['us_alert'] = '✅ 正常：小幅波动，市场平稳'
                page_data['us_alert_class'] = 'us-alert-ok'
    except Exception:
        pass

    # 加载A股宽基指数数据
    try:
        import subprocess as sub
        result = sub.run(
            ['/root/.openclaw/workspace/venv/bin/python3', '/root/.openclaw/workspace/scripts/指数行情.py'],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        idx_items = []
        sentiment = ''
        # 新接口返回JSON格式
        import json
        try:
            data = json.loads(output.strip())
            for idx in data.get('cn', []):
                pct = idx['pct']
                pct_str = f"{pct:+.2f}"
                idx_items.append({
                    'name': idx['name'],
                    'val': f"{idx['val']:.2f}",
                    'pct': pct_str + '%',
                    'cls': 'idx-up' if pct >= 0 else 'idx-down'
                })
            # 市场情绪判断
            avg_pct = sum(i['pct'] for i in data.get('cn', [])) / max(len(data.get('cn', [])), 1)
            if avg_pct > 1.0: sentiment = '🟢 明显上涨'
            elif avg_pct > 0.5: sentiment = '🟡 小幅上涨'
            elif avg_pct > -0.5: sentiment = '⚪ 震荡整理'
            elif avg_pct > -1.0: sentiment = '🟠 小幅下跌'
            else: sentiment = '🔴 大幅杀跌'
        except Exception:
            pass
    except Exception:
        pass

    # 加载CANSLIM TOP10（从四维选股CANSLIM.py输出）
    canslim = []
    pick_file = '/tmp/daily_pick_result.txt'
    if os.path.exists(pick_file):
        try:
            content = open(pick_file, encoding='utf-8').read()
            # 解析 TOP10 部分
            m = re.search(r'CAN SLIM融合选股TOP10\n=+', content)
            if m:
                top10_text = content[m.end():]
                lines = top10_text.split('\n')
                rank_map = {'🥇': '1', '🥈': '2', '🥉': '3', '4️⃣': '4', '5️⃣': '5',
                            '6️⃣': '6', '7️⃣': '7', '8️⃣': '8', '9️⃣': '9', '🔟': '10'}
                entry = {}
                for line in lines:
                    if not line.strip() or line.startswith('=') or line.startswith('✅'):
                        if entry and 'name' in entry:
                            canslim.append(entry)
                            entry = {}
                        continue
                    rm = re.match(r'^([🥇🥈🥉4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟]+)\s+(.+?)\(([0-9A-Z]+)\)\s*\|.+?\|\s*总分:(\d+)', line)
                    if rm:
                        rank = rank_map.get(rm.group(1), rm.group(1))
                        name, code, score = rm.group(2), rm.group(3), int(rm.group(4))
                        entry = {'name': name, 'code': code, 'score': score,
                                 'rank': rank, 'url': stock_url(code),
                                 'score_class': 'score-high' if score >= 70 else ('score-mid' if score >= 50 else 'score-low'),
                                 'action': '', 'pos': '', 'ma': '', 'vol': '', 'board': ''}
                    elif line.startswith(' ') or '|' in line:
                        if '🟡' in line: entry['action'] = '🟡 稳健买入'
                        elif '⚪' in line: entry['action'] = '⚪ 观察'
                        elif '🔴' in line: entry['action'] = '🔴 规避'
                        pos_m = re.search(r'位置:([^|！]+)', line)
                        if pos_m: entry['pos'] = pos_m.group(1).strip()
                        ma_m = re.search(r'均线:([^|！]+)', line)
                        if ma_m: entry['ma'] = ma_m.group(1).strip()
                        vol_m = re.search(r'量价:([^|！]+)', line)
                        if vol_m: entry['vol'] = vol_m.group(1).strip()
                        board_m = re.search(r'板块:([^|！]+)', line)
                        if board_m: entry['board'] = board_m.group(1).strip()
                if entry and 'name' in entry:
                    canslim.append(entry)
        except Exception:
            pass
    if canslim:
        page_data['canslim'] = canslim

    return render_template_string(DASHBOARD_PAGE,
        update_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
        date_tabs=date_tabs, current_date=current_date,
        current_date_label=current_date_label, page_data=page_data,
    )

@app.route('/systems')
def systems():
    """系统设计文档页面"""
    DOCS_BASE = '/root/.openclaw/workspace/docs'
    import os, glob

    # 支持版本切换参数：?sys=stock&ver=v1.0-20260510.md
    req_sys = request.args.get('sys')
    req_ver = request.args.get('ver')

    systems_data = []
    # 选股系统
    stock_doc = f'{DOCS_BASE}/选股系统/设计文档.md'
    if req_sys == 'stock' and req_ver and os.path.exists(f'{DOCS_BASE}/选股系统/{req_ver}'):
        stock_doc = f'{DOCS_BASE}/选股系统/{req_ver}'
    if os.path.exists(stock_doc):
        content = open(stock_doc, encoding='utf-8').read()
        sections = parse_doc_to_sections(content)
        versions = []
        for f in sorted(glob.glob(f'{DOCS_BASE}/选股系统/v*.md'), reverse=True):
            fname = os.path.basename(f)
            m = re.search(r'v(\d+\.\d+)', fname)
            label = m.group(0).replace('-', ' ') if m else fname
            all_versions = sorted(glob.glob(f'{DOCS_BASE}/选股系统/v*.md'), reverse=True)
            latest_fname = all_versions[0] if all_versions else None
            latest = (os.path.basename(fname) == os.path.basename(latest_fname)) if latest_fname else False
            current = (fname == req_ver) if req_ver else latest  # 默认显示最新版本
            versions.append({'label': label, 'url': f'/systems?sys=stock&ver={fname}', 'current': current, 'latest': latest})
        systems_data.append({'id': 'stock', 'icon': '📊', 'name': '选股系统', 'desc': '四维选股 + 双模式 + 情绪日历', 'sections': sections, 'versions': versions})
    else:
        systems_data.append({'id': 'stock', 'icon': '📊', 'name': '选股系统', 'desc': '文档生成中...', 'sections': [], 'versions': []})

    # 复盘系统
    review_doc = f'{DOCS_BASE}/复盘系统/设计文档.md'
    if req_sys == 'review' and req_ver and os.path.exists(f'{DOCS_BASE}/复盘系统/{req_ver}'):
        review_doc = f'{DOCS_BASE}/复盘系统/{req_ver}'
    if os.path.exists(review_doc):
        content = open(review_doc, encoding='utf-8').read()
        sections = parse_doc_to_sections(content)
        versions = []
        for f in sorted(glob.glob(f'{DOCS_BASE}/复盘系统/v*.md'), reverse=True):
            fname = os.path.basename(f)
            m = re.search(r'v(\d+\.\d+)', fname)
            label = m.group(0).replace('-', ' ') if m else fname
            all_versions = sorted(glob.glob(f'{DOCS_BASE}/复盘系统/v*.md'), reverse=True)
            latest_fname = all_versions[0] if all_versions else None
            latest = (os.path.basename(fname) == os.path.basename(latest_fname)) if latest_fname else False
            current = (fname == req_ver) if req_ver else latest
            versions.append({'label': label, 'url': f'/systems?sys=review&ver={fname}', 'current': current, 'latest': latest})
        systems_data.append({'id': 'review', 'icon': '📋', 'name': '复盘系统', 'desc': '持仓评分 + 明日注意 + 情绪记录', 'sections': sections, 'versions': versions})
    else:
        systems_data.append({'id': 'review', 'icon': '📋', 'name': '复盘系统', 'desc': '文档生成中...', 'sections': [], 'versions': []})

    # 量化资讯
    news_doc = f'{DOCS_BASE}/量化资讯/设计文档.md'
    if req_sys == 'news' and req_ver and os.path.exists(f'{DOCS_BASE}/量化资讯/{req_ver}'):
        news_doc = f'{DOCS_BASE}/量化资讯/{req_ver}'
    if os.path.exists(news_doc):
        content = open(news_doc, encoding='utf-8').read()
        sections = parse_doc_to_sections(content)
        versions = []
        for f in sorted(glob.glob(f'{DOCS_BASE}/量化资讯/v*.md'), reverse=True):
            fname = os.path.basename(f)
            m = re.search(r'v(\d+\.\d+)', fname)
            label = m.group(0).replace('-', ' ') if m else fname
            all_versions = sorted(glob.glob(f'{DOCS_BASE}/量化资讯/v*.md'), reverse=True)
            latest_fname = all_versions[0] if all_versions else None
            latest = (os.path.basename(fname) == os.path.basename(latest_fname)) if latest_fname else False
            current = (fname == req_ver) if req_ver else latest
            versions.append({'label': label, 'url': f'/systems?sys=news&ver={fname}', 'current': current, 'latest': latest})
        systems_data.append({'id': 'news', 'icon': '📰', 'name': '量化资讯', 'desc': '消息面筛选 + 板块热度评级', 'sections': sections, 'versions': versions})
    else:
        systems_data.append({'id': 'news', 'icon': '📰', 'name': '量化资讯', 'desc': '文档生成中...', 'sections': [], 'versions': []})

    # 监控系统
    monitor_doc = f'{DOCS_BASE}/监控系统/v1.0-20260515.md'
    if req_sys == 'monitor' and req_ver and os.path.exists(f'{DOCS_BASE}/监控系统/{req_ver}'):
        monitor_doc = f'{DOCS_BASE}/监控系统/{req_ver}'
    if os.path.exists(monitor_doc):
        content = open(monitor_doc, encoding='utf-8').read()
        sections = parse_doc_to_sections(content)
        versions = []
        for f in sorted(glob.glob(f'{DOCS_BASE}/监控系统/v*.md'), reverse=True):
            fname = os.path.basename(f)
            m = re.search(r'v(\d+\.\d+)', fname)
            label = m.group(0).replace('-', ' ') if m else fname
            all_versions = sorted(glob.glob(f'{DOCS_BASE}/监控系统/v*.md'), reverse=True)
            latest_fname = all_versions[0] if all_versions else None
            latest = (os.path.basename(fname) == os.path.basename(latest_fname)) if latest_fname else False
            current = (fname == req_ver) if req_ver else latest
            versions.append({'label': label, 'url': f'/systems?sys=monitor&ver={fname}', 'current': current, 'latest': latest})
        systems_data.append({'id': 'monitor', 'icon': '🛡️', 'name': '监控系统', 'desc': '守护进程 + Cron定时任务 + 微信推送', 'sections': sections, 'versions': versions})
    else:
        systems_data.append({'id': 'monitor', 'icon': '🛡️', 'name': '监控系统', 'desc': '文档生成中...', 'sections': [], 'versions': []})

    files = [
        {'sys': '选股系统', 'name': '选股系统说明书.md', 'note': '用户使用手册'},
        {'sys': '选股系统', 'name': '选股系统/设计文档.md', 'note': '技术设计文档'},
        {'sys': '复盘系统', 'name': '复盘系统/设计文档.md', 'note': '技术设计文档'},
        {'sys': '量化资讯', 'name': '量化资讯/设计文档.md', 'note': '技术设计文档'},
        {'sys': '监控系统', 'name': '监控系统/v1.0-20260515.md', 'note': '守护进程+Cron架构'},
    ]

    return render_template_string(SYSTEMS_PAGE,
        systems=systems_data,
        files=[f for f in files if os.path.exists(f'{DOCS_BASE}/{f["name"]}')],
    )

def parse_doc_to_sections(content):
    """将markdown文档解析为带标题的section列表，使用markdown库"""
    import re, markdown
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    sections = []
    # 按 ## 分割成大节（顶层标题）
    parts = re.split(r'^##\s+(.+)$', content, flags=re.MULTILINE)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i+1].strip() if i+1 < len(parts) else ''
        html_body = md.convert(body)
        md.reset()
        sections.append({'title': title, 'content': html_body})
    return sections[:20]



@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'): return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_PAGE, error='密码错误，请重试')
    return render_template_string(LOGIN_PAGE)



@app.route('/api/indexes')
def api_indexes():
    """轻量API返回指数数据"""
    import subprocess as sub, json
    result = {'a': [], 'us': [], 'a_sentiment': '', 'us_alert': '', 'us_alert_class': ''}
    try:
        r1 = sub.run(['/root/.openclaw/workspace/venv/bin/python3', '/root/.openclaw/workspace/scripts/指数行情.py'],
                     capture_output=True, text=True, timeout=25)
        data = json.loads(r1.stdout.strip())
        for idx in data.get('cn', []):
            pct = idx['pct']
            result['a'].append({'name': idx['name'], 'val': f"{idx['val']:.2f}", 'pct': f"{pct:+.2f}", 'up': pct >= 0})
        avg = sum(i['pct'] for i in data.get('cn', [])) / max(len(data.get('cn', [])), 1)
        if avg > 2.0: result['a_sentiment'] = '🟢 强势'
        elif avg > 0.5: result['a_sentiment'] = '🟡 小幅'
        elif avg > -0.5: result['a_sentiment'] = '⚪ 震荡'
        elif avg > -1.5: result['a_sentiment'] = '🟠 偏弱'
        else: result['a_sentiment'] = '🔴 大跌'
    except: pass
    try:
        r2 = sub.run(['/root/.openclaw/workspace/venv/bin/python3', '/root/.openclaw/workspace/scripts/us_quote.py'],
                     capture_output=True, text=True, timeout=15)
        data2 = json.loads(r2.stdout.strip())
        for u in data2.get('us', []):
            result['us'].append({'ticker': u['ticker'], 'price': u['price'], 'pct': u['pct']})
        if result['us']:
            spy = next((x['pct'] for x in result['us'] if x['ticker'] == 'SPY'), 0)
            if spy <= -3: result['us_alert'] = '🔴 严重暴跌！'; result['us_alert_class'] = 'danger'
            elif spy <= -1.5: result['us_alert'] = '🟠 较大跌幅'; result['us_alert_class'] = 'danger'
            elif spy <= -0.5: result['us_alert'] = '🟡 注意：标普500下跌>0.5%'; result['us_alert_class'] = 'warn'
            else: result['us_alert'] = '✅ 正常'; result['us_alert_class'] = 'ok'
    except: pass
    return json.dumps(result, ensure_ascii=False)

from flask import send_from_directory

@app.route('/dashboard')
def dashboard():
    """新版统一选股仪表盘"""
    return send_from_directory('/root/.openclaw/workspace/data', 'index.html')


@app.route('/api/stocks')
def api_stocks():
    """返回所有股票数据用于Dashboard"""
    import sqlite3, json
    sector = request.args.get('sector', '')
    sort = request.args.get('sort', 'score_total')
    order = request.args.get('order', 'desc')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    conn = sqlite3.connect('/root/.openclaw/workspace/data/stock_tags.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    where = "WHERE price IS NOT NULL"
    if sector and sector.strip():
        where += f" AND sector='{sector.strip()}'"
    
    valid_sorts = ['price', 'change_pct', 'pe', 'mktcap', 'name', 'score_total', 'revenue_growth']
    if sort not in valid_sorts:
        sort = 'score_total'
    order = 'DESC' if order == 'desc' else 'ASC'
    
    cur.execute(f'SELECT code, name, board, sector, industry, price, change_pct, pe, mktcap, score_total, revenue_growth FROM stocks {where} ORDER BY {sort} {order} LIMIT ? OFFSET ?', (page_size, (page-1)*page_size))
    rows = cur.fetchall()
    
    cur.execute(f'SELECT COUNT(*) FROM stocks {where}')
    total = cur.fetchone()[0]
    
    conn.close()
    
    return json.dumps({
        'stocks': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size
    }, ensure_ascii=False)

from flask import send_from_directory, make_response


@app.route('/test_session')
def test_session():
    return f"logged_in={session.get('logged_in', False)}"

@app.route('/download/docs')
def download_docs():
    import zipfile, io, os
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk('/root/.openclaw/workspace/docs'):
            for fname in files:
                if fname.endswith('.md'):
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, '/root/.openclaw/workspace/docs')
                    zf.write(fpath, arcname)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Type'] = 'application/zip'
    resp.headers['Content-Disposition'] = 'attachment; filename="stock_system_docs_20260517.zip"'
    return resp

@app.route('/download/code')
def download_code():
    import zipfile, io, os
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk('/root/.openclaw/workspace/scripts'):
            for fname in files:
                if fname.endswith('.py'):
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, '/root/.openclaw/workspace/scripts')
                    zf.write(fpath, arcname)
        for fpath in ['/root/.openclaw/workspace/web_report.py']:
            if os.path.exists(fpath):
                zf.write(fpath, os.path.basename(fpath))
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Type'] = 'application/zip'
    resp.headers['Content-Disposition'] = 'attachment; filename="stock_system_code_20260517.zip"'
    return resp

if __name__ == '__main__':
    print("访问地址: http://0.0.0.0:5000")
    print("密码: Djyqlcfzy@123")
    app.run(host='0.0.0.0', port=5000, debug=False)