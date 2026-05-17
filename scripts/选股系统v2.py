#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股系统 v2 — 三池并行 + CANSLIM + 竞价分析
架构：Phase 1A(3并行) → Phase 1B(N×20) → Phase 2(N×20×3ch×3ret) → Phase 3(三池并行) → 推送
推送时间：09:28
"""

import os, sys, re, json, time, datetime, sqlite3, logging, pandas as pd, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

# ========== 配置 ==========
WORKDIR = Path("/root/.openclaw/workspace")
DATA_DIR = WORKDIR / "data"
REPORT_DIR = WORKDIR / "每日选股"
SCRIPTS_DIR = WORKDIR / "scripts"
DB_PATH = DATA_DIR / "stock_pool.db"

def is_trading_day(date=None):
    """判断指定日期是否为交易日（不含周末+节假日）"""
    if date is None:
        date = datetime.date.today()
    
    # 1. 周末不是交易日
    if date.weekday() >= 5:
        return False
    
    # 2. 用akshare获取交易日历
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        trading_dates = set(pd.to_datetime(df['trade_date']).dt.date.tolist())
        return date in trading_dates
    except:
        # 网络失败时保守处理：认为是交易日
        return True

def get_last_trading_date():
    """获取最近一个交易日（可能为今天或昨天）"""
    today = datetime.date.today()
    if is_trading_day(today):
        return today
    for i in range(1, 7):
        d = today - datetime.timedelta(days=i)
        if is_trading_day(d):
            return d
    return today

# 运行时日期（每天09:25使用今日，16:00复盘用昨日）
YESTERDAY_FMT = (datetime.date.today() - timedelta(days=1)).strftime("%Y%m%d")
TODAY_FMT = datetime.date.today().strftime("%Y%m%d")
PUSH_TIME = "09:28"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(REPORT_DIR / f"选股v2-{TODAY_FMT}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("选股v2")


# ============================================================
# 工具函数
# ============================================================

def get_market(code):
    c = str(code).zfill(6)
    if c.startswith('688') or c.startswith('600') or c.startswith('601') or c.startswith('603'):
        return 'sh'
    elif c.startswith('8') or c.startswith('9'):
        return 'hk'
    else:
        return 'sz'

def nmc_to_yi(nmc):
    try:
        return float(nmc) / 10000 if nmc else 0
    except:
        return 0

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def requests_get(url, timeout=8):
    import requests
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://finance.sina.com.cn/'}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.encoding = 'utf-8'
    return resp

def get_kline_sina(code, market=None, datalen=250):
    if market is None:
        market = get_market(code)
    url = (f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           f'CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=5&datalen={datalen}')
    try:
        r = requests_get(url, timeout=8)
        data = r.json() if r.text and r.text != 'null' else []
        return data or []
    except:
        return []


# ============================================================
# Phase 1A: 板块分析（3任务并行）
# ============================================================

def task_sector_fund_flow():
    """板块资金流（周日API不可用时，用涨停股行业分布代替）"""
    try:
        import akshare as ak
        try:
            df = ak.stock_sector_fund_flow_rank(indicator='今日', sector_type='行业资金流')
        except:
            df = None
        
        if df is None or df is not None and (df.empty or len(df) == 0):
            # 备用：用涨停股行业分布
            zt_df = ak.stock_zt_pool_em(date=YESTERDAY_FMT)
            if zt_df is not None and len(zt_df) > 0:
                sector_counts = zt_df.groupby('所属行业').size().sort_values(ascending=False)
                result = {sector: float(count) for sector, count in sector_counts.head(15).items()}
                log.info(f"[Phase1A-FUND] 备用涨停行业分布: {len(result)} 个板块")
                return result
            return {}
        
        if df is not None:
            cols = [c for c in df.columns if '主力净流入' in c or '净流入' in c]
            if not cols:
                cols = [c for c in df.columns if '金额' in c or '流入' in c]
            flow_col = cols[0] if cols else df.columns[2]
            sector_col = [c for c in df.columns if '名称' in c or '板块' in c][0] if [c for c in df.columns if '名称' in c or '板块' in c] else df.columns[0]
            df_sorted = df.sort_values(flow_col, ascending=False).head(20)
            result = {}
            for _, row in df_sorted.iterrows():
                name = str(row.get(sector_col, '')).strip()
                val_str = str(row.get(flow_col, 0))
                val = safe_float(val_str.replace(',', '').replace('亿', '').replace('万', ''))
                if '万' in val_str:
                    val /= 10000
                result[name] = val
            log.info(f"[Phase1A-FUND] 资金流板块数: {len(result)}")
            return result
        return {}
    except Exception as e:
        log.error(f"[Phase1A-FUND] 失败: {e}")
        return {}

def task_yesterday_zt_pool():
    try:
        import akshare as ak
        df = ak.stock_zt_pool_em(date=YESTERDAY_FMT)
        if df is None or df.empty:
            return {}, []
        board_col = None
        for c in df.columns:
            if '行业' in c or '所属' in c:
                board_col = c
                break
        board_stats = {}
        zt_list = []
        if board_col:
            for _, row in df.iterrows():
                board = str(row.get(board_col, '')).strip()
                if board:
                    board_stats[board] = board_stats.get(board, 0) + 1
                zt_list.append(row)
        log.info(f"[Phase1A-ZT] 昨日涨停: {len(df)}只, 板块覆盖: {len(board_stats)}")
        return board_stats, zt_list
    except Exception as e:
        log.error(f"[Phase1A-ZT] 失败: {e}")
        return {}, []

def task_news_catalyst():
    catalysts = {}
    try:
        news_dir = DATA_DIR / "news"
        today_str = datetime.date.today().strftime("%Y%m%d")
        if news_dir.exists():
            for f in list(news_dir.glob(f"*{today_str}*"))[:20]:
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    sector_keywords = ['AI', '芯片', '半导体', '新能源', '汽车', '军工', '医药', '消费',
                                       '银行', '证券', '房地产', '化工', '光伏', '储能', '锂电', '机器人',
                                       '无人驾驶', '卫星', '算力', 'AI PC', '固态电池', '商业航天']
                    for kw in sector_keywords:
                        if kw in content:
                            catalysts.setdefault(kw, []).append(content[:150])
                except:
                    pass
    except Exception as e:
        log.error(f"[Phase1A-NEWS] 失败: {e}")
    if not catalysts:
        catalysts = {'AI': ['人工智能政策催化'], '芯片': ['半导体国产替代'], '新能源': ['新能源政策支持']}
    log.info(f"[Phase1A-NEWS] 催化剂板块: {list(catalysts.keys())}")
    return catalysts

def score_sectors(fund_flow, board_stats, catalysts):
    sector_scores = {}
    all_sectors = set(fund_flow.keys()) | set(board_stats.keys()) | set(catalysts.keys())
    for sector in all_sectors:
        fund = fund_flow.get(sector, 0)
        zt_count = board_stats.get(sector, 0)
        cat_score = len(catalysts.get(sector, [])) * 10
        score = fund / 10000 * 0.3 + zt_count * 15 + cat_score
        sector_scores[sector] = score
    sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    log.info(f"[Phase1A] Top板块: {sorted_sectors}")
    return [s for s, _ in sorted_sectors]


# ============================================================
# Phase 1B: CANSLIM打分（N×20线程）
# ============================================================

def check_market_bull():
    try:
        kline_url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=5&datalen=60'
        r = requests_get(kline_url)
        kdata = r.json() if r.text and r.text != 'null' else []
        if kdata and len(kdata) >= 25:
            closes = [float(d['close']) for d in kdata]
            ma20 = sum(closes[-20:]) / 20
            ma20_prev = sum(closes[-25:-5]) / 20
            cur = closes[-1]
            return cur > ma20 and ma20 > ma20_prev
        return check_market_bull_fallback()
    except:
        return check_market_bull_fallback()

def check_market_bull_fallback():
    try:
        kdata = get_kline_sina('000001', 'sh', 60)
        if kdata and len(kdata) >= 25:
            closes = [float(d['close']) for d in kdata]
            ma20 = sum(closes[-20:]) / 20
            ma20_prev = sum(closes[-25:-5]) / 20
            cur = closes[-1]
            return cur > ma20 and ma20 > ma20_prev
    except:
        pass
    return True

def get_market_cap_tencent(code):
    try:
        import requests
        url = f'https://qt.gtimg.cn/q={str(code).zfill(6)}'
        r = requests.get(url, headers={'Referer': 'https://gu.qq.com'}, timeout=4)
        text = r.text
        m = re.search(r'"nmc"="([^"]+)"', text)
        if m:
            return nmc_to_yi(safe_float(m.group(1)))
    except:
        pass
    return 0

def canslim_hard_filter(code, name, market, kline_data):
    """CAN SLIM 硬过滤：C/A/N/S/L/I/M"""
    fails = []
    code = str(code).zfill(6)
    if len(kline_data) < 120:
        return False, ['数据不足120日']
    try:
        closes = [float(d['close']) for d in kdata]
        volumes = [int(d['volume']) for d in kdata]
        cur = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sum(closes[-30:]) / 30
        high60 = max(closes[-60:])
        vol5 = sum(volumes[-5:]) / 5
        vol20 = sum(volumes[-20:]) / 20
        annual_1y = (closes[-1] / closes[-252] - 1) * 100 if len(closes) >= 252 else 0
        annual_2y = (closes[-1] / closes[-504] - 1) * 100 if len(closes) >= 504 else annual_1y
    except Exception as e:
        return False, [f'数据解析失败: {e}']

    # M: 沪深300牛市开关（关键修复：不是上证50）
    if not check_market_bull():
        return False, ['M-沪深300熊市']
    # S: 市值30-800亿（关键修复）
    try:
        nmc = safe_float(kline_data[-1].get('nmc', 0))
        mkt_yi = nmc_to_yi(nmc)
        if mkt_yi == 0:
            mkt_yi = get_market_cap_tencent(code)
        if mkt_yi > 0:
            if mkt_yi < 30:
                fails.append(f'S-市值{mkt_yi:.0f}亿(<30亿偏小)')
            elif mkt_yi > 800:
                fails.append(f'S-市值{mkt_yi:.0f}亿(>800亿偏滞)')
    except:
        pass
    # A: 年度增长
    if annual_2y < -40:
        fails.append(f'A-年度{annual_2y:.0f}%<下滑40%')
    elif annual_1y < -30:
        fails.append(f'A-年度{annual_1y:.0f}%<下滑30%')
    # N: 新高
    if high60 < cur * 1.02:
        fails.append(f'N-无新高(60日高点溢价<2%)')
    # L: 相对强弱
    if annual_1y < 20:
        fails.append(f'L-RS{annual_1y:.0f}%<涨幅20%')
    # I: 量价异常
    abnormal_vol_days = sum(1 for i in range(-10, 0) if volumes[i] > vol5 * 3.5)
    if abnormal_vol_days >= 3:
        fails.append(f'I-量异常{abnormal_vol_days}日爆量>3.5x')
    # C: 业绩
    new_low_count = sum(1 for i in range(-20, -3) if closes[i] < min(closes[max(0, i-5):i]))
    if new_low_count >= 5:
        fails.append(f'C-业绩{new_low_count}日创新低')
    # 均线空头
    ma50_prev = sum(closes[-55:-5]) / 50 if len(closes) >= 55 else ma50
    if cur < ma50 and ma50 < ma50_prev:
        fails.append('趋势-中期空头')
    return len(fails) == 0, fails

def detect_cup_handle(closes):
    if len(closes) < 120:
        return False
    c = closes[-120:]
    mid = 60
    left, right = c[:mid], c[mid:]
    left_peak = max(left)
    right_peak = max(right)
    left_peak_idx = left.index(left_peak)
    right_peak_idx = mid + right.index(right_peak)
    left_bottom = min(c[left_peak_idx:mid])
    right_bottom = min(c[mid:right_peak_idx])
    cup_depth = (left_peak - min(left_bottom, right_bottom)) / left_peak if left_peak > 0 else 0
    if cup_depth < 0.35 and right_bottom >= left_bottom * 0.9:
        return True
    mid_low = min(c[mid-10:mid+10])
    if mid_low > left_peak * 0.75 and mid_low > right_peak * 0.75:
        return True
    return False

def detect_flag(closes, volumes):
    if len(closes) < 30:
        return False
    recent = closes[-20:]
    amp = max(recent) - min(recent)
    avg_price = sum(recent) / len(recent)
    rel_amp = amp / avg_price if avg_price > 0 else 1
    if len(closes) >= 40:
        flag_pole = (closes[-20] - closes[-40]) / closes[-40] if closes[-40] > 0 else 0
        if flag_pole > 0.15 and rel_amp < 0.08:
            return True
    return False

def score_dimensions(kline_data, closes, volumes, sector_zt_count, sector_catalyst):
    """四维打分：位置25+均线20+量价20+催化20 + Shape bonus"""
    cur = closes[-1]
    high60 = max(closes[-60:])
    vol5 = sum(volumes[-5:]) / 5
    vol20 = sum(volumes[-20:]) / 20

    # 位置 25pts
    dist60 = (high60 - cur) / high60 * 100 if high60 > 0 else 100
    pos_score = 25 if 40 <= dist60 <= 75 else (20 if 25 <= dist60 < 40 else (12 if 75 < dist60 <= 90 else (18 if 15 <= dist60 < 25 else 5)))

    # 均线 20pts
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sum(closes[-30:]) / 30
    ma20_prev = sum(closes[-25:-5]) / 20
    ma50_prev = sum(closes[-55:-5]) / 50 if len(closes) >= 55 else ma20
    above_ma20 = cur > ma20
    above_ma50 = cur > ma50
    ma20_up = ma20 > ma20_prev
    ma50_up = ma50 > ma50_prev
    if above_ma20 and above_ma50 and ma20_up and ma50_up:
        ma_score = 20
    elif above_ma20 and above_ma50:
        ma_score = 16
    elif above_ma20 and ma20_up:
        ma_score = 13
    elif above_ma20:
        ma_score = 9
    else:
        ma_score = 3

    # 量价 20pts
    vol_ratio = vol5 / vol20 if vol20 > 0 else 0
    healthy_days = 0
    for i in range(-10, 0):
        o = float(kline_data[i]['open'])
        c = closes[i]
        v = volumes[i]
        if c > o and v > vol5 * 1.4:
            healthy_days += 1
        elif c < o and v < vol5 * 0.7:
            healthy_days += 1
    if 0.6 <= vol_ratio <= 1.3 and healthy_days >= 6:
        vol_score = 20
    elif healthy_days >= 5:
        vol_score = 15
    elif vol_ratio > 2.5:
        vol_score = 5
    elif vol_ratio < 0.35:
        vol_score = 6
    else:
        vol_score = 10

    # 催化 20pts
    cat_score = min(20, sector_zt_count * 3 + sector_catalyst * 5)
    dim_score = pos_score + ma_score + vol_score + cat_score

    # Shape Bonus
    shape_bonus = 0
    shape_names = []
    if len(closes) >= 60:
        amp_recent = max(closes[-20:]) - min(closes[-20:])
        amp_prev = max(closes[-40:-20]) - min(closes[-40:-20])
        if amp_recent < amp_prev * 0.8:
            shape_bonus += 10
            shape_names.append('振幅收敛')
    if len(closes) >= 80:
        avg_vol_60 = sum(volumes[-60:]) / 60
        recent_vol = sum(volumes[-5:]) / 5
        if recent_vol > avg_vol_60 * 2.5 and vol_ratio > 1.5:
            shape_bonus += 10
            shape_names.append('瞌睡醒来')
    if above_ma20 and above_ma50 and ma20_up and ma50_up:
        shape_bonus += 5
        shape_names.append('均线健康')
    if detect_cup_handle(closes):
        shape_bonus += 15
        shape_names.append('Cup+Handle')
    if detect_flag(closes, volumes):
        shape_bonus += 10
        shape_names.append('旗形')

    return dim_score + shape_bonus, {
        'position': pos_score, 'ma': ma_score, 'volume': vol_score,
        'catalysis': cat_score, 'shape_bonus': shape_bonus,
        'shape_names': shape_names, 'dim_score': dim_score
    }

def score_single_stock(args):
    code, name, source, board_stats, catalysts, top_sectors = args
    code = str(code).zfill(6)
    market = get_market(code)
    try:
        kdata = get_kline_sina(code, market, 250)
        if not kdata or len(kdata) < 120:
            return None
        closes = [float(d['close']) for d in kdata]
        volumes = [int(d['volume']) for d in kdata]
        cur = closes[-1]
        high60 = max(closes[-60:])
        passed, fails = canslim_hard_filter(code, name, market, kdata)
        if not passed:
            return {'code': code, 'name': name, 'source': source, 'passed': False, 'fails': fails}
        sector_key = None
        for s in top_sectors:
            if s in name:
                sector_key = s
                break
        zt_count = board_stats.get(sector_key, 0) if sector_key else 0
        cat_score = len(catalysts.get(sector_key, [])) * 5
        total_score, dims = score_dimensions(kdata, closes, volumes, zt_count, cat_score)
        return {
            'code': code, 'name': name, 'source': source, 'passed': True,
            'total_score': total_score, 'dims': dims,
            'position_60d': round((high60 - cur) / high60 * 100, 1) if high60 > 0 else 100,
            'cur_price': cur, 'sector': sector_key or '其他', 'fails': [],
        }
    except Exception as e:
        return {'code': code, 'name': name, 'source': source, 'passed': False, 'fails': [str(e)]}


# ============================================================
# Phase 2: 竞价数据（多通道×重试）
# ============================================================

class DataSource:
    """多通道竞价数据源（EM/Sina/Tencent）"""

    def __init__(self, code):
        self.code = str(code).zfill(6)
        self.market = get_market(code)
        self.results = {}

    def fetch_em(self, retry=3):
        for attempt in range(retry):
            try:
                import akshare as ak
                df = ak.stock_zt_pool_em(date=YESTERDAY_FMT)
                if df is not None and not df.empty:
                    mask = df['代码'].astype(str).str.zfill(6) == self.code
                    if mask.any():
                        row = df[mask].iloc[0]
                        self.results['em'] = {
                            'fb_time': str(row.get('封板时间', '09:30')),
                            'lianban': int(row.get('连板数', 1)),
                            'fb_money': safe_float(str(row.get('封板资金', '0')).replace('亿', '').replace('万', '')),
                        }
                        return self.results['em']
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"[EM] {self.code} 第{attempt+1}次失败: {e}")
                time.sleep(0.5)
        return None

    def fetch_sina(self, retry=3):
        for attempt in range(retry):
            try:
                import requests
                url = f'https://hq.sinajs.cn/list={self.market}{self.code}'
                r = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}, timeout=5)
                text = r.text
                m = re.search(r'"([^"]+)"', text)
                if m:
                    fields = m.group(1).split(',')
                    if len(fields) >= 32:
                        self.results['sina'] = {'price': safe_float(fields[3]), 'yest_close': safe_float(fields[2]), 'open': safe_float(fields[1]), 'vol': safe_float(fields[8]) * 100}
                        return self.results['sina']
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"[SINA] {self.code} 第{attempt+1}次失败: {e}")
                time.sleep(0.5)
        return None

    def fetch_tencent(self, retry=3):
        for attempt in range(retry):
            try:
                import requests
                url = f'https://qt.gtimg.cn/q={self.code}'
                r = requests.get(url, headers={'Referer': 'https://gu.qq.com'}, timeout=5)
                text = r.text
                m = re.search(r'="([^"]+)"', text)
                if m:
                    fields = m.group(1).split('~')
                    if len(fields) >= 40:
                        self.results['tencent'] = {'price': safe_float(fields[3]), 'yest_close': safe_float(fields[4]), 'open': safe_float(fields[5]), 'vol': safe_float(fields[6]) * 100}
                        return self.results['tencent']
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"[TENCENT] {self.code} 第{attempt+1}次失败: {e}")
                time.sleep(0.5)
        return None

    def fetch_all(self):
        with ThreadPoolExecutor(max_workers=3) as ex:
            f1 = ex.submit(self.fetch_em)
            f2 = ex.submit(self.fetch_sina)
            f3 = ex.submit(self.fetch_tencent)
            f1.result(); f2.result(); f3.result()
        return self.results

    def get_auction_info(self):
        em = self.results.get('em')
        if em:
            return {'source': 'em', 'auction_price': 0, 'auction_change': 0, 'lianban': em['lianban'], 'fb_time': em['fb_time'], 'fb_money': em['fb_money'], 'auction_score': self.calc_auction_score(em['fb_time'], em['lianban'], em['fb_money'])}
        sina = self.results.get('sina')
        if sina:
            price, yest = sina['price'], sina['yest_close']
            return {'source': 'sina', 'auction_price': price, 'auction_change': (price / yest - 1) * 100 if yest > 0 else 0, 'lianban': 1, 'fb_time': '09:30', 'fb_money': 0, 'auction_score': 5}
        tencent = self.results.get('tencent')
        if tencent:
            price, yest = tencent['price'], tencent['yest_close']
            return {'source': 'tencent', 'auction_price': price, 'auction_change': (price / yest - 1) * 100 if yest > 0 else 0, 'lianban': 1, 'fb_time': '09:30', 'fb_money': 0, 'auction_score': 5}
        return {'source': 'none', 'auction_price': 0, 'auction_change': 0, 'lianban': 1, 'fb_time': '09:31', 'fb_money': 0, 'auction_score': 0}

    @staticmethod
    def calc_auction_score(fb_time, lianban, fb_money):
        score = 0
        try:
            t = str(fb_time).strip()
            h, m = t.split(':')
            minute = int(h) * 60 + int(m)
        except:
            minute = 570
        if minute <= 565: score += 10
        elif minute <= 570: score += 6
        elif minute <= 575: score += 4
        elif minute <= 580: score += 1
        lb = lianban if lianban else 1
        if lb == 1: score += 3
        elif lb == 2: score += 7
        elif lb == 3: score += 8
        elif lb >= 4: score += 9
        return score

def fetch_auction_for_stock(code):
    ds = DataSource(code)
    ds.fetch_all()
    return ds.get_auction_info()

def fetch_auction_parallel(stock_codes):
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_auction_for_stock, c): c for c in stock_codes}
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                results[code] = fut.result()
            except Exception as e:
                log.error(f"[AUCTION] {code} 失败: {e}")
                results[code] = {'source': 'error', 'auction_score': 0}
    return results


# ============================================================
# Phase 3: 三池过滤
# ============================================================

def build_three_pools(candidates, auction_data):
    """生菜池/熟菜池/消息股池"""
    shengcai, shucai, xiaoxi = [], [], []
    for c in candidates:
        if not c.get('passed'):
            continue
        code = c['code']
        auc = auction_data.get(code, {})
        pos_60d = c.get('position_60d', 100)

        # 生菜池
        if pos_60d < 60:
            change_est = abs(auc.get('auction_change', 0))
            if change_est < 3:
                c['pool_type'] = '生菜池'
                c['pool_reason'] = f'低位{pos_60d:.0f}%+滞涨{change_est:.1f}%'
                shengcai.append(c)

        # 熟菜池（关键修复：封板资金>1亿）
        fb_time = auc.get('fb_time', '09:31')
        lianban = auc.get('lianban', 1)
        fb_money = auc.get('fb_money', 0)
        try:
            t = str(fb_time)
            h, m = t.split(':')
            minute = int(h) * 60 + int(m)
        except:
            minute = 571
        if minute <= 565 and lianban in (2, 4) and fb_money > 1:
            c['pool_type'] = '熟菜池'
            c['pool_reason'] = f'封板{fb_time}连板{lianban}封板资金{fb_money:.1f}亿'
            shucai.append(c)

        # 消息股池
        if c['dims'].get('shape_bonus', 0) >= 15:
            c['pool_type'] = '消息股池'
            c['pool_reason'] = f'Shape催化(+{c["dims"]["shape_bonus"]}pts)'
            xiaoxi.append(c)

    shengcai.sort(key=lambda x: x['total_score'], reverse=True)
    shucai.sort(key=lambda x: x['total_score'], reverse=True)
    xiaoxi.sort(key=lambda x: x['total_score'], reverse=True)
    return shengcai, shucai, xiaoxi


def merge_final_output(shengcai, shucai, xiaoxi, auction_data):
    """稳健×5 + 强势×5"""
    results = []
    for item in shengcai[:5]:
        auc = auction_data.get(item['code'], {})
        results.append({
            'stock_code': item['code'], 'stock_name': item['name'],
            'sector': item.get('sector', '其他'), 'pool_type': item.get('pool_type', '生菜池'),
            'position_60d': item.get('position_60d', 100),
            'catalysis': '+'.join(item['dims'].get('shape_names', [])) if item.get('dims') else '',
            'auction_price': auc.get('auction_price', 0),
            'auction_change': round(auc.get('auction_change', 0), 2),
            'auction_score': auc.get('auction_score', 0),
            'dimension_score': item['dims']['dim_score'] if item.get('dims') else 0,
            'total_score': item['total_score'], 'mode': '稳健',
            'push_time': PUSH_TIME, 'push_date': TODAY_FMT,
        })
    strong_all = sorted(shucai + xiaoxi, key=lambda x: x['total_score'], reverse=True)[:5]
    for item in strong_all:
        auc = auction_data.get(item['code'], {})
        results.append({
            'stock_code': item['code'], 'stock_name': item['name'],
            'sector': item.get('sector', '其他'), 'pool_type': item.get('pool_type', '强势'),
            'position_60d': item.get('position_60d', 100),
            'catalysis': '+'.join(item['dims'].get('shape_names', [])) if item.get('dims') else '',
            'auction_price': auc.get('auction_price', 0),
            'auction_change': round(auc.get('auction_change', 0), 2),
            'auction_score': auc.get('auction_score', 0),
            'dimension_score': item['dims']['dim_score'] if item.get('dims') else 0,
            'total_score': item['total_score'], 'mode': '强势',
            'push_time': PUSH_TIME, 'push_date': TODAY_FMT,
        })
    return results


# ============================================================
# 数据库写入
# ============================================================

def save_to_db(results, date_str):
    """保存选股结果到数据库（不包含signal字段）"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS stock_selection_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            select_date TEXT, mode TEXT, rank INTEGER,
            stock_code TEXT, stock_name TEXT, sector TEXT, pool_type TEXT,
            position_60d REAL, catalysis TEXT,
            auction_price REAL, auction_change REAL, auction_score REAL,
            dimension_score REAL, total_score REAL,
            push_time TEXT, push_date TEXT,
            UNIQUE(select_date, mode, rank))""")

        stable_results = [r for r in results if r["mode"] == "稳健"]
        strong_results = [r for r in results if r["mode"] == "强势"]

        for i, r in enumerate(stable_results, 1):
            cur.execute("""INSERT OR REPLACE INTO stock_selection_v2
                (select_date, mode, rank, stock_code, stock_name, sector, pool_type,
                 position_60d, catalysis, auction_price, auction_change, auction_score,
                 dimension_score, total_score, push_time, push_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date_str, r["mode"], i, r["stock_code"], r["stock_name"], r["sector"], r["pool_type"],
                 r["position_60d"], r["catalysis"], r["auction_price"], r["auction_change"], r["auction_score"],
                 r["dimension_score"], r["total_score"], r["push_time"], r["push_date"]))

        for i, r in enumerate(strong_results, 1):
            cur.execute("""INSERT OR REPLACE INTO stock_selection_v2
                (select_date, mode, rank, stock_code, stock_name, sector, pool_type,
                 position_60d, catalysis, auction_price, auction_change, auction_score,
                 dimension_score, total_score, push_time, push_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date_str, r["mode"], i, r["stock_code"], r["stock_name"], r["sector"], r["pool_type"],
                 r["position_60d"], r["catalysis"], r["auction_price"], r["auction_change"], r["auction_score"],
                 r["dimension_score"], r["total_score"], r["push_time"], r["push_date"]))

        conn.commit()
        conn.close()
        log.info(f"[DB] saved {len(results)} records")
    except Exception as e:
        log.error(f"[DB] fail: {e}")


def push_wechat(results):
    """微信推送"""
    try:
        sys.path.insert(0, str(WORKDIR / "scripts"))
        from stock_pool_push import push_selection_v2
        push_selection_v2(results)
        log.info("[PUSH] WeChat sent")
    except Exception as e:
        log.error(f"[PUSH] fail: {e}")


def build_text_report(results, top_sectors):
    stable = [r for r in results if r["mode"] == "稳健"]
    strong = [r for r in results if r["mode"] == "强势"]
    lines = [
        f"选股系统v2 | {datetime.date.today()} {PUSH_TIME}",
        f"强势板块: {", ".join(top_sectors[:3])}",
        "---",
        "稳健模式 TOP5（生菜池）",
    ]
    for i, r in enumerate(stable, 1):
        shape = r["catalysis"] or "基础形态"
        lines.append(f"{i}. {r['stock_name']}({r['stock_code']}) | {r['pool_type']} | 位置:{r['position_60d']}% | {shape} | 总分:{r['total_score']}")
    lines.extend(["---", "强势模式 TOP5（熟菜池+消息股池）"])
    for i, r in enumerate(strong, 1):
        lines.append(f"{i}. {r['stock_name']}({r['stock_code']}) | {r['pool_type']} | 竞价分:{r['auction_score']} | 总分:{r['total_score']}")
    return "\n".join(lines)



# ============================================================
# 主流程
# ============================================================

def main():
    """主选股流程（每天09:25运行）"""
    log.info("=== 选股系统v2 启动 ===")

    # 检查是否为交易日
    if not is_trading_day():
        log.info("今日非交易日，跳过选股")
        return []

    # Phase 1A: 3任务并行
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(task_sector_fund_flow)
        f2 = ex.submit(task_yesterday_zt_pool)
        f3 = ex.submit(task_news_catalyst)
        fund_flow = f1.result()
        board_stats, zt_list = f2.result()
        catalysts = f3.result()

    top_sectors = score_sectors(fund_flow, board_stats, catalysts)
    log.info(f"[Phase1A] top5: {top_sectors}")

    # 候选股
    candidates = []
    for _, row in (zt_list if zt_list else []):
        try:
            code = str(row.get("代码", "")).zfill(6)
            name = str(row.get("名称", ""))
            if code and name and "ST" not in name and not name.startswith("N"):
                candidates.append((code, name, "涨停池"))
        except: pass

    # 启动股补充
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=40&sort=changepercent&asc=0&node=hs_a"
        r = requests_get(url)
        for d in r.json():
            pct = safe_float(d.get("changepercent", 0))
            if not (3 <= pct < 9.9): continue
            name = d.get("name", "")
            if "ST" in name or name.startswith("N"): continue
            code = str(d.get("code", "")).zfill(6)
            price = safe_float(d.get("trade", 0))
            nmc = safe_float(d.get("nmc", 0))
            mkt_yi = nmc_to_yi(nmc)
            if price < 3 or price > 150: continue
            if mkt_yi > 0 and (mkt_yi < 5 or mkt_yi > 500): continue
            candidates.append((code, name, "启动股"))
    except Exception as e:
        log.error(f"[CANDIDATE] fail: {e}")

    log.info(f"[Phase1A] 候选股: {len(candidates)}只")

    # Phase 1B: N×20并行
    args_list = [(code, name, src, board_stats, catalysts, top_sectors) for code, name, src, *_ in candidates]
    scored = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(score_single_stock, args) for args in args_list]
        for fut in as_completed(futures):
            try:
                result = fut.result()
                if result and result.get("passed"):
                    scored.append(result)
            except Exception as e:
                log.error(f"[Phase1B] fail: {e}")

    scored.sort(key=lambda x: x["total_score"], reverse=True)
    log.info(f"[Phase1B] 通过CANSLIM: {len(scored)}只")

    # Phase 2: 竞价数据
    passed_codes = [c["code"] for c in scored]
    auction_data = fetch_auction_parallel(passed_codes)
    log.info(f"[Phase2] 竞价获取完成: {len(auction_data)}")

    # Phase 3: 三池过滤
    shengcai, shucai, xiaoxi = build_three_pools(scored, auction_data)
    log.info(f"[Phase3] 生菜:{len(shengcai)} 熟菜:{len(shucai)} 消息股:{len(xiaoxi)}")

    # 合并输出
    results = merge_final_output(shengcai, shucai, xiaoxi, auction_data)
    log.info(f"[MERGE] 最终输出: {len(results)}只")

    # 保存报告
    report_text = build_text_report(results, top_sectors)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"综合选股v2-{TODAY_FMT}.md"
    report_file.write_text(report_text, encoding="utf-8")
    log.info(f"[REPORT] {report_file}")

    # 保存数据库
    save_to_db(results, TODAY_FMT)

    # 推送微信
    push_wechat(results)

    log.info("=== 选股系统v2 完成 ===")
    return results


def daily_review():
    """每日复盘模块（T+1日 16:00运行）
    读取昨日选股，对比今日收盘，计算信号胜率"""
    log.info("=== 每日复盘开始 ===")
    
    if not is_trading_day():
        log.info("今日非交易日，跳过复盘")
        return
    
    # 获取昨日日期
    select_date = get_last_trading_date()
    if select_date == datetime.date.today():
        log.info("今日为选股日，复盘需等明日")
        return
    
    select_date_str = select_date.strftime("%Y%m%d")
    log.info(f"复盘日期: {select_date_str}")
    
    # 读取昨日选股结果
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""SELECT stock_code, stock_name, pool_type, signals, total_score 
                       FROM stock_selection_v2 WHERE select_date=?""", (select_date_str,))
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        log.error(f"读取选股结果失败: {e}")
        return
    
    if not rows:
        log.info("无选股记录，跳过复盘")
        return
    
    log.info(f"昨日选股 {len(rows)} 只，开始复盘...")
    
    # 初始化信号统计
    signal_stats = {}  # {signal_name: {total, wins, total_gain}}
    
    review_details = []
    
    for code, name, pool_type, signals_json, total_score in rows:
        try:
            # 获取今日开盘价和收盘价
            market = 'sh' if code.startswith(('6','5')) else 'sz'
            url = f"https://qt.gtimg.cn/q={market}{code}"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            parts = r.text.split('~')
            if len(parts) < 33:
                continue
            
            today_open = float(parts[27])   # 开盘价
            today_close = float(parts[3])    # 当前价/收盘价
            yesterday_close = float(parts[4])  # 昨收
            
            # 今日涨幅（从开盘买入计算）
            if today_open > 0:
                change_pct = (today_close - today_open) / today_open * 100
            else:
                change_pct = (today_close - yesterday_close) / yesterday_close * 100
            
            # 标记结果
            if change_pct > 9.5:
                result_tag = "涨停 ✅"
            elif change_pct > 5:
                result_tag = "大赚 ✅"
            elif change_pct > 0:
                result_tag = "小赚 ✓"
            elif change_pct > -3:
                result_tag = "微亏 ⚠"
            else:
                result_tag = "亏损 ❌"
            
            review_details.append({
                'code': code, 'name': name, 'pool': pool_type,
                'score': total_score, 'change': change_pct, 'result': result_tag
            })
            
            # 解析信号并统计
            if signals_json:
                try:
                    signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
                except:
                    signals = []
            else:
                signals = []
            
            for sig in signals:
                if sig not in signal_stats:
                    signal_stats[sig] = {'total': 0, 'wins': 0, 'total_gain': 0}
                signal_stats[sig]['total'] += 1
                signal_stats[sig]['total_gain'] += change_pct
                if change_pct > 0:
                    signal_stats[sig]['wins'] += 1
            
        except Exception as e:
            log.error(f"复盘 {code} 失败: {e}")
            continue
    
    # 写入复盘报告
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    review_file = REPORT_DIR / f"复盘-{select_date_str}.md"
    
    lines = [f"# 每日复盘 {select_date_str}\n", f"复盘时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"]
    
    # 信号胜率统计
    lines.append("## 信号胜率统计\n")
    lines.append("| 信号 | 次数 | 胜率 | 平均涨幅 |\n")
    lines.append("|------|------|------|------|\n")
    
    sorted_signals = sorted(signal_stats.items(), key=lambda x: x[1]['wins']/max(x[1]['total'],1), reverse=True)
    for sig, stat in sorted_signals:
        win_rate = stat['wins'] / max(stat['total'], 1) * 100
        avg_gain = stat['total_gain'] / max(stat['total'], 1)
        lines.append(f"| {sig} | {stat['total']} | {win_rate:.1f}% | {avg_gain:+.2f}% |\n")
    
    # 股票复盘明细
    lines.append("\n## 选股复盘明细\n")
    lines.append("| # | 股票 | 代码 | 来源 | 评分 | 涨幅 | 结果 |\n")
    lines.append("|---|------|------|------|------|------|------|\n")
    
    for i, r in enumerate(sorted(review_details, key=lambda x: x['change'], reverse=True), 1):
        lines.append(f"| {i} | {r['name']} | {r['code']} | {r['pool']} | {r['score']:.0f} | {r['change']:+.2f}% | {r['result']} |\n")
    
    review_file.write_text(''.join(lines), encoding='utf-8')
    log.info(f"[复盘] 报告已保存: {review_file}")
    
    # 更新信号胜率表
    update_signal_win_rate(signal_stats, select_date_str)
    
    log.info("=== 每日复盘完成 ===")


def update_signal_win_rate(signal_stats, date_str):
    """更新信号胜率表"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS signal_win_rate (
            signal_name TEXT PRIMARY KEY,
            total_count INTEGER,
            win_count INTEGER,
            avg_gain REAL,
            win_rate REAL,
            last_updated TEXT
        )""")
        
        for sig, stat in signal_stats.items():
            win_rate = stat['wins'] / max(stat['total'], 1) * 100
            avg_gain = stat['total_gain'] / max(stat['total'], 1)
            cur.execute("""INSERT OR REPLACE INTO signal_win_rate 
                (signal_name, total_count, win_count, avg_gain, win_rate, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (sig, stat['total'], stat['wins'], avg_gain, win_rate, date_str))
        
        conn.commit()
        conn.close()
        log.info(f"[信号胜率] 更新 {len(signal_stats)} 个信号")
    except Exception as e:
        log.error(f"更新信号胜率失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "复盘":
        daily_review()
    else:
        results = main()
        print(f"完成，共推送 {len(results)} 只股票")
