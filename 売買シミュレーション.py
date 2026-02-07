"""
売買シミュレーション（シンプル実装）

使い方（概要）:
- 価格データはデフォルトで `prices_close_wide.csv` を参照します（終値のみ想定）。
- `simulate_trade(ticker, buy_date, sell_date=None, hold_days=None, prices_df=None, dividends_df=None)` を使って
  保有期間中の配当有無、購入価格、売却価格、損益を取得します。

注意:
- 与えられているワークスペースには過去の終値（close）のCSVがある想定です。始値(open)データが無い場合は始値は近似できないため、購入価格/売却価格は終値で計算します。

日本語コメントでできるだけ分かりやすく実装しています。
"""

from datetime import datetime, timedelta
import pandas as pd
import os
from typing import Optional, Dict, Any


def _parse_date(d):
    if isinstance(d, (pd.Timestamp, datetime)):
        return pd.Timestamp(d).normalize()
    return pd.to_datetime(d).normalize()


def load_prices(path: str = "prices_close_wide.csv") -> pd.DataFrame:
    """価格CSVを読み込み、日付インデックスのDataFrameを返す。

    CSVは先頭列が日付、以降がティッカー列という想定。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"価格ファイルが見つかりません: {path}")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index).normalize()
    return df


def _get_nearest_date_index(dates, target: pd.Timestamp, direction: str = "next") -> int:
    # searchsorted を使って最寄りのインデックスを取得
    i = dates.searchsorted(target)
    if direction == "next":
        if i >= len(dates):
            raise IndexError("指定日以降の取引日が存在しません")
        return i
    else:  # prev
        if i == 0:
            raise IndexError("指定日以前の取引日が存在しません")
        # searchsorted は挿入位置を返すので1つ戻す
        return i - 1


def dividends_in_period(dividends_df: pd.DataFrame, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    """与えられた配当データ（DataFrame）に指定期間中の配当があるかを判定する。

    期待されるフォーマットの例:
    - 列に 'date' と 'ticker' がある場合はそれを使う
    - ない場合は日付インデックスか、単一ティッカー用のファイルと想定
    """
    if dividends_df is None:
        return False
    df = dividends_df.copy()
    # 日付列を探す
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        date_col = "date"
    else:
        # 日付がインデックスになっている想定
        df.index = pd.to_datetime(df.index).normalize()
        df = df.reset_index().rename(columns={"index": "date"})
        date_col = "date"

    if "ticker" in df.columns:
        df = df[df["ticker"] == ticker]

    # 範囲内に日付が存在するか
    mask = (df[date_col] >= start) & (df[date_col] <= end)
    return mask.any()


def simulate_trade(
    ticker: str,
    buy_date,
    sell_date: Optional[str] = None,
    hold_days: Optional[int] = None,
    prices_df: Optional[pd.DataFrame] = None,
    dividends_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """シンプルな売買シミュレーション。

    引数:
    - `ticker`: 価格DataFrameの列名に対応するティッカー
    - `buy_date`: 購入希望日（文字列またはdatetime）
    - `sell_date`: 売却希望日（省略可）
    - `hold_days`: 保有日数（省略可）。`sell_date` が無い場合に使用する
    - `prices_df`: 事前に読み込んだ価格DataFrame（省略時は `prices_close_wide.csv` を読み込む）
    - `dividends_df`: 配当データのDataFrame（任意）

    戻り値: 辞書
    - `buy_date`, `sell_date`: 実際に使った取引日
    - `buy_price`, `sell_price`: 使用した価格（終値のみ想定）
    - `profit_pct`: パーセンテージ損益 ((sell-buy)/buy*100)
    - `dividends_occurred`: 保有期間中に配当があったか
    """
    if prices_df is None:
        prices_df = load_prices()

    dates = prices_df.index
    buy_ts = _parse_date(buy_date)

    # 購入日は指定日以降の最初の取引日を使う（取引日の始まりで買う想定）
    buy_idx = _get_nearest_date_index(dates, buy_ts, direction="next")
    actual_buy_date = dates[buy_idx]

    # 売却日を決定
    if sell_date is not None:
        sell_ts = _parse_date(sell_date)
        # 売却は指定日以前の直近の取引日の終値で売る想定
        sell_idx = _get_nearest_date_index(dates, sell_ts, direction="prev")
    elif hold_days is not None:
        sell_idx = min(buy_idx + int(hold_days), len(dates) - 1)
    else:
        raise ValueError("sell_date か hold_days のいずれかを指定してください")

    actual_sell_date = dates[sell_idx]

    # 価格取得
    try:
        buy_price = float(prices_df.at[actual_buy_date, ticker])
    except Exception as e:
        raise KeyError(f"買値取得エラー: ティッカー '{ticker}' または日付が存在しません ({e})")
    try:
        sell_price = float(prices_df.at[actual_sell_date, ticker])
    except Exception as e:
        raise KeyError(f"売値取得エラー: ティッカー '{ticker}' または日付が存在しません ({e})")

    profit_pct = (sell_price - buy_price) / buy_price * 100.0

    # 配当の有無判定（dividends_df が与えられている場合のみ）
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
    # 簡単なCLI: 引数は ticker buy_date sell_date
    import sys

    if len(sys.argv) < 4:
        print("使い方: python 売買シミュレーション.py <TICKER> <BUY_DATE> <SELL_DATE>")
        print("例: python 売買シミュレーション.py 3382_T 2020-01-10 2021-03-15")
        sys.exit(0)

    ticker = sys.argv[1]
    buy_date = sys.argv[2]
    sell_date = sys.argv[3]

    prices = None
    try:
        prices = load_prices()
    except FileNotFoundError:
        print("prices_close_wide.csv が見つかりません。実行ディレクトリを確認してください。")
        sys.exit(1)

    res = simulate_trade(ticker, buy_date, sell_date=sell_date, prices_df=prices)
    print("結果:")
    for k, v in res.items():
        print(f"{k}: {v}")
