"""
Trade simulation (English filename copy of 売買シミュレーション.py)

This file is a copy of the original Japanese-named module, kept under an English filename
so it can be imported more easily from other scripts. Functionality is identical.
"""

from datetime import datetime
import pandas as pd
import os
from typing import Optional, Dict, Any


def _parse_date(d):
    if isinstance(d, (pd.Timestamp, datetime)):
        return pd.Timestamp(d).normalize()
    try:
        return pd.to_datetime(d).normalize()
    except Exception:
        raise ValueError(f"日付の解析に失敗しました: {d!r}. 引数の順序を確認してください (ticker buy_date <sell_date|hold_days>)")


def load_prices(path: str = "prices_close_wide.csv") -> pd.DataFrame:
    """価格CSVを読み込み。複数候補を試して親フォルダも探索します。

    優先順:
    1. 引数 `path`
    2. スクリプトの親フォルダにある `../prices_close_wide.csv`
    3. カレントディレクトリの `prices_close_wide.csv`
    """
    candidates = [path]
    here = os.path.dirname(__file__)
    candidates.append(os.path.normpath(os.path.join(here, "..", "prices_close_wide.csv")))
    candidates.append(os.path.join(os.getcwd(), "prices_close_wide.csv"))

    for p in candidates:
        if os.path.exists(p):
            # まずは文字列として読み込む（自動日時解析で誤判定されるのを避ける）
            df = pd.read_csv(p, index_col=0)

            # インデックスが日付かどうか判定する
            idx_parsed = pd.to_datetime(df.index, errors="coerce")
            valid_idx = idx_parsed.notna().sum()
            if valid_idx / max(1, len(df.index)) >= 0.9:
                # 行が日付インデックスになっていると判断
                df.index = idx_parsed.normalize()
                return df

            # そうでなければ、列が日付になっている可能性があるので転置を試す
            cols_parsed = pd.to_datetime(df.columns, errors="coerce")
            valid_cols = cols_parsed.notna().sum()
            if valid_cols / max(1, len(df.columns)) >= 0.9:
                df = df.T
                df.index = cols_parsed.normalize()
                return df

            # 日付形式が見つからない場合はエラー
            raise ValueError(f"CSVのフォーマットが想定外です: 日付列が見つかりません ({p})")

    raise FileNotFoundError(f"価格ファイルが見つかりません。試した場所: {candidates}")


def _get_nearest_date_index(dates, target: pd.Timestamp, direction: str = "next") -> int:
    i = dates.searchsorted(target)
    if direction == "next":
        if i >= len(dates):
            raise IndexError("指定日以降の取引日が存在しません")
        return i
    else:
        if i == 0:
            raise IndexError("指定日以前の取引日が存在しません")
        return i - 1


def dividends_in_period(dividends_df: pd.DataFrame, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    if dividends_df is None:
        return False
    df = dividends_df.copy()
    if "date" in df.columns:
        s = pd.to_datetime(df["date"], errors="coerce")
        # タイムゾーンがある場合はナイーブに変換して正しく比較できるようにする
        try:
            if s.dt.tz is not None:
                s = s.dt.tz_convert(None)
        except Exception:
            # s.dt.tz が存在しない場合は無視
            pass
        df["date"] = s.dt.normalize()
        date_col = "date"
    else:
        df.index = pd.to_datetime(df.index).normalize()
        df = df.reset_index().rename(columns={"index": "date"})
        date_col = "date"

    if "ticker" in df.columns:
        df = df[df["ticker"] == ticker]

    # start/end をナイーブな正規化された Timestamp に揃える
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    try:
        if getattr(start_ts, 'tz', None) is not None:
            start_ts = start_ts.tz_convert(None)
    except Exception:
        pass
    try:
        if getattr(end_ts, 'tz', None) is not None:
            end_ts = end_ts.tz_convert(None)
    except Exception:
        pass
    start_ts = start_ts.normalize()
    end_ts = end_ts.normalize()

    mask = (df[date_col] >= start_ts) & (df[date_col] <= end_ts)
    return mask.any()


def _find_column_for_ticker(df: pd.DataFrame, ticker: str) -> str:
    """与えられたティッカー文字列からDataFrameの列名を柔軟に探索して返す。

    試行順:
    1. 完全一致
    2. '_' <-> '.' の置換
    3. 数字部分のみ（例: '3382' -> '3382.T' のような候補を検索）
    4. 部分一致で最初に見つかったもの
    """
    cols = list(df.columns.astype(str))
    if ticker in cols:
        return ticker

    alt = ticker.replace("_", ".")
    if alt in cols:
        return alt

    alt2 = ticker.replace(".", "_")
    if alt2 in cols:
        return alt2

    # 数字のみを取り出してマッチを試みる
    import re

    m = re.match(r"^(\d{3,6})", ticker)
    code = None
    if m:
        code = m.group(1)
        for c in cols:
            if str(c).startswith(code):
                return c

    # 部分一致の最初の候補
    for c in cols:
        if code and code in str(c):
            return c

    # 失敗するときは候補を一部返して分かりやすくする
    sample = cols[:20]
    raise KeyError(f"ティッカー '{ticker}' に一致する列が見つかりません。候補例: {sample}")


def load_dividends_for_ticker(ticker: str):
    """ローカルの配当CSVを探して読み込む。見つからなければ yfinance で取得を試みる。

    返り値: DataFrame または None
    """
    # 候補ファイル名
    here = os.path.dirname(__file__)
    candidates = []
    base = ticker.replace('.', '_')
    candidates.append(os.path.join(here, f"{base}_dividends_last10y.csv"))
    candidates.append(os.path.join(here, f"{ticker}_dividends_last10y.csv"))
    candidates.append(os.path.normpath(os.path.join(here, "..", f"{base}_dividends_last10y.csv")))
    candidates.append(os.path.normpath(os.path.join(here, "..", f"{ticker}_dividends_last10y.csv")))
    candidates.append(os.path.join(os.getcwd(), f"{base}_dividends_last10y.csv"))
    candidates.append(os.path.join(os.getcwd(), f"{ticker}_dividends_last10y.csv"))
    candidates.append(os.path.join(here, "dividends.csv"))
    candidates.append(os.path.normpath(os.path.join(here, "..", "dividends.csv")))

    for p in candidates:
        if p and os.path.exists(p):
            try:
                df = pd.read_csv(p)
                return df
            except Exception:
                continue

    # ローカルに見つからなければ yfinance で取得を試みる
    try:
        import yfinance as yf
    except Exception:
        return None

    # yfinance で配当取得 (ticker の形式が 1332.T のような場合)
    try:
        tk = yf.Ticker(ticker.replace('_', '.'))
        div = tk.dividends
        if div is None or len(div) == 0:
            return None
        df = div.reset_index()
        df.columns = ["date", "dividend"]
        return df
    except Exception:
        return None


def simulate_trade(
    ticker: str,
    buy_date,
    sell_date: Optional[str] = None,
    hold_days: Optional[int] = None,
    prices_df: Optional[pd.DataFrame] = None,
    dividends_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    if prices_df is None:
        prices_df = load_prices()

    dates = prices_df.index
    buy_ts = _parse_date(buy_date)
    buy_idx = _get_nearest_date_index(dates, buy_ts, direction="next")
    actual_buy_date = dates[buy_idx]

    if sell_date is not None:
        sell_ts = _parse_date(sell_date)
        sell_idx = _get_nearest_date_index(dates, sell_ts, direction="prev")
    elif hold_days is not None:
        sell_idx = min(buy_idx + int(hold_days), len(dates) - 1)
    else:
        raise ValueError("sell_date か hold_days のいずれかを指定してください")

    actual_sell_date = dates[sell_idx]

    # ティッカー名をDataFrameの列名にマッピング
    col = _find_column_for_ticker(prices_df, ticker)
    try:
        buy_price = float(prices_df.at[actual_buy_date, col])
    except Exception as e:
        raise KeyError(f"買値取得エラー: ティッカー '{ticker}' -> 列 '{col}' または日付が存在しません ({e})")
    try:
        sell_price = float(prices_df.at[actual_sell_date, col])
    except Exception as e:
        raise KeyError(f"売値取得エラー: ティッカー '{ticker}' -> 列 '{col}' または日付が存在しません ({e})")

    profit_pct = (sell_price - buy_price) / buy_price * 100.0

    div_occurred = False
    if dividends_df is not None:
        start = actual_buy_date
        end = actual_sell_date
        div_occurred = dividends_in_period(dividends_df, ticker, start, end)

    return {
        "buy_date": actual_buy_date,
        "sell_date": actual_sell_date,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "profit_pct": profit_pct,
        "dividends_occurred": div_occurred,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="売買シミュレーション: ティッカー, 購入日, 売却日または保有日数を指定します")
    parser.add_argument("ticker", help="ティッカー (例: 3382_T or 1332.T)")
    parser.add_argument("buy_date", help="購入日 (YYYY-MM-DD)")
    parser.add_argument("arg3", help="売却日 (YYYY-MM-DD) または保有日数 (整数)")

    args = parser.parse_args()

    ticker = args.ticker
    buy_date = args.buy_date
    arg3 = args.arg3

    sell_date = None
    hold_days = None
    # arg3 を整数化して保有日数とみなすか、日付として扱う
    try:
        hold_days = int(arg3)
    except Exception:
        sell_date = arg3

    try:
        prices = load_prices()
    except FileNotFoundError as e:
        print(e)
        raise SystemExit(1)

    # 配当データを自動で探して渡す
    dividends_df = load_dividends_for_ticker(ticker)
    if dividends_df is None:
        print("配当データが見つかりませんでした。ローカルCSVか yfinance が必要です。配当チェックは無効化されます。")

    try:
        res = simulate_trade(ticker, buy_date, sell_date=sell_date, hold_days=hold_days, prices_df=prices, dividends_df=dividends_df)
    except ValueError as e:
        print(f"入力エラー: {e}")
        raise SystemExit(2)
    except KeyError as e:
        print(f"データ取得エラー: {e}")
        raise SystemExit(3)

    # 日本語で出力を整形して表示
    print("結果:")
    jp_map = {
        "buy_date": "購入日",
        "sell_date": "売却日",
        "buy_price": "購入価格",
        "sell_price": "売却価格",
        "profit_pct": "損益(%)",
        "dividends_occurred": "保有期間中に配当があったか",
    }

    for key in ["buy_date", "sell_date", "buy_price", "sell_price", "profit_pct", "dividends_occurred"]:
        v = res.get(key)
        if key == "dividends_occurred":
            v = "はい" if v else "いいえ"
        elif key in ("buy_date", "sell_date") and hasattr(v, 'strftime'):
            v = v.strftime('%Y-%m-%d')
        elif isinstance(v, float):
            # 小数点は見やすくフォーマット
            v = f"{v:.4f}" if key == "profit_pct" else f"{v:.2f}"
        print(f"{jp_map.get(key, key)}: {v}")
