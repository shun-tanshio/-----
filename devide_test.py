import yfinance as yf
import pandas as pd


# シンプル版: yfinance から配当を取得して CSV に保存します。
# 使い方:
# - このファイル内の `ticker` と `years` を変更するだけで実行できます。
# - 例: ticker = "3382.T" (東証コード形式)、years = 10
# 依存: yfinance, pandas


def fetch_dividends(ticker: str = "3382.T", years: int = 10) -> pd.DataFrame:
	"""指定銘柄の過去 `years` 年分の配当を取得して DataFrame で返す。

	引数:
	  ticker: yfinance の銘柄コード（例: '3382.T'）
	  years: 過去何年分を取得するか（整数）

	返り値:
	  Date と Dividend カラムを持つ pandas.DataFrame（該当データがなければ空の DataFrame）
	"""
	tk = yf.Ticker(ticker)
	div = tk.dividends
	if div is None or div.empty:
		return pd.DataFrame(columns=["Date", "Dividend"])

	# DatetimeIndex がタイムゾーン付きの場合に備えて合わせる
	tz = div.index.tz
	if tz is not None:
		start = pd.Timestamp.now(tz=tz) - pd.DateOffset(years=years)
	else:
		start = pd.Timestamp.now() - pd.DateOffset(years=years)

	df = div[div.index >= start].reset_index()
	df.columns = ["Date", "Dividend"]
	return df


if __name__ == "__main__":
	# --- ここを変更して実行 ---
	ticker = "3382.T"  # 取得する銘柄
	years = 10          # 過去何年分を取得するか

	# 配当を取得して表示・CSV保存
	result = fetch_dividends(ticker, years)
	if result.empty:
		print(f"{ticker} の過去 {years} 年の配当データは見つかりませんでした。")
	else:
		print(result.to_string(index=False))
		out_file = f"{ticker.replace('.','_')}_dividends_last{years}y.csv"
		result.to_csv(out_file, index=False)
		print(f"Saved: {out_file}")


