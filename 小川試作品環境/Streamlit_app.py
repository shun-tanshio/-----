import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import datetime


@st.cache_data
def load_prices(path: Path):
    df = pd.read_csv(path)

    if "Ticker" in df.columns:
        df = df.set_index("Ticker").T

    idx = pd.to_datetime(df.index, errors="coerce")
    mask = ~idx.isna()
    df = df.loc[mask].copy()
    df.index = pd.DatetimeIndex(idx[mask])
    df = df.apply(pd.to_numeric, errors="coerce").sort_index()
    return df


def normalize_series(s: pd.Series):
    return s / s.iloc[0] * 100 if not s.empty else s


def main():
    st.title("株価シミュレーション")

    csv_path = Path(__file__).resolve().parents[1] / "prices_close_wide.csv"
    df = load_prices(csv_path)

    if df.empty:
        st.error("データがありません")
        return

    # ===== ティッカー選択 =====
    tickers = sorted(df.columns.tolist())
    selected_tickers = st.sidebar.multiselect(
        "ティッカー（複数選択可）",
        tickers,
        default=tickers[:1],
    )

    if not selected_tickers:
        st.info("ティッカーを1つ以上選択してください")
        return

    # ===== データ期間 =====
    min_date = df.index.min().date()
    max_date = df.index.max().date()
    st.sidebar.caption(f"📅 データ期間: {min_date} 〜 {max_date}")

    # ===== 開始日（基準日） =====
    start_base_date = st.sidebar.date_input(
        "開始日（基準日）",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

    # ===== 期間 =====
    period = st.sidebar.radio(
        "期間",
        ["1M", "3M", "6M", "YTD", "1Y", "MAX"],
        horizontal=True,
        index=5,
    )

    start_base_date = pd.Timestamp(start_base_date)

    # ===== 期間計算 =====
    if period == "1M":
        end_date = start_base_date + datetime.timedelta(days=30)
    elif period == "3M":
        end_date = start_base_date + datetime.timedelta(days=90)
    elif period == "6M":
        end_date = start_base_date + datetime.timedelta(days=180)
    elif period == "YTD":
        end_date = pd.Timestamp(start_base_date.year, 12, 31)
    elif period == "1Y":
        end_date = start_base_date + datetime.timedelta(days=365)
    else:  # MAX
        end_date = pd.Timestamp(max_date)

    # データ範囲ガード
    if end_date.date() > max_date:
        end_date = pd.Timestamp(max_date)

    start_date = start_base_date

    st.sidebar.caption(f"選択期間: {period} ｜ {start_date.date()} 〜 {end_date.date()}")

    # ===== 正規化 =====
    normalize = st.sidebar.checkbox("開始を100に正規化", value=True)

    # ===== プロット用データ =====
    plot_rows = []

    for ticker in selected_tickers:
        s = df[ticker].dropna()
        s_range = s.loc[start_date:end_date]

        if s_range.empty:
            continue

        if normalize:
            s_range = normalize_series(s_range)

        plot_rows.append(
            pd.DataFrame(
                {
                    "Date": s_range.index,
                    "Value": s_range.values,
                    "Ticker": ticker,
                }
            )
        )

    if not plot_rows:
        st.info("選択期間にデータがありません")
        return

    df_plot = pd.concat(plot_rows, ignore_index=True)

    y_label = "正規化値（開始=100）" if normalize else "価格"

    fig = px.line(
        df_plot,
        x="Date",
        y="Value",
        color="Ticker",
        labels={"Value": y_label},
        title=f"{start_date.date()} 〜 {end_date.date()}",
    )

    results = []

    for ticker in selected_tickers:
        s = df[ticker].dropna()
        s_range = s.loc[start_date:end_date]

        if s_range.empty:
            continue

        # ===== リターン計算（生値）=====
        start_price = s_range.iloc[0]
        end_price = s_range.iloc[-1]
        rtn_pct = (end_price / start_price - 1) * 100

        results.append(
            {
                "Ticker": ticker,
                "開始価格": round(start_price, 2),
                "終了価格": round(end_price, 2),
                "騰落率 (%)": round(rtn_pct, 2),
            }
        )

        # ===== プロット用 =====
        if normalize:
            s_range = normalize_series(s_range)

        plot_rows.append(
            pd.DataFrame(
                {
                    "Date": s_range.index,
                    "Value": s_range.values,
                    "Ticker": ticker,
                }
            )
        )



    # ===== グラフUI無効化 =====
    fig.update_layout(
        xaxis_fixedrange=True,
        yaxis_fixedrange=True,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.subheader("📊 期間リターン")

    df_result = pd.DataFrame(results).sort_values("騰落率 (%)", ascending=False)

    st.dataframe(
        df_result,
        use_container_width=True,
        hide_index=True,
    )



if __name__ == "__main__":
    main()
