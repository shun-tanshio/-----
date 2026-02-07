"""
同階層の `売買シミュレーション.py` を import して
メインのシミュレーションを2回実行するランナーです。

使い方:
 - デフォルトの2ケースで実行:
     python run_two_simulations.py
 - 引数で2つのシミュを指定:
     python run_two_simulations.py "1332.T,2020-01-10,30" "3382_T,2020-01-10,2021-03-15"

引数フォーマット: "TICKER,BUY_DATE,SELL_OR_HOLD"
"""

from pathlib import Path
import sys


def load_sim_module():
    # 同ディレクトリにある trade_simulation を通常の import で読み込む
    here = Path(__file__).parent.resolve()
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import trade_simulation as sim
    return sim


def parse_arg(arg: str):
    # arg = "TICKER,BUY,SELL_OR_HOLD"
    parts = [p.strip() for p in arg.split(",")]
    if len(parts) != 3:
        raise ValueError("引数は 'TICKER,BUY_DATE,SELL_OR_HOLD' の形式で3つ指定してください")
    ticker, buy, third = parts
    # third が整数であれば保有日数
    try:
        hold = int(third)
        sell = None
        hold_days = hold
    except Exception:
        sell = third
        hold_days = None
    return ticker, buy, sell, hold_days


def format_result(res: dict) -> str:
    jp_map = {
        "buy_date": "購入日",
        "sell_date": "売却日",
        "buy_price": "購入価格",
        "sell_price": "売却価格",
        "profit_pct": "損益(%)",
        "dividends_occurred": "保有期間中に配当があったか",
    }
    lines = []
    for key in ["buy_date", "sell_date", "buy_price", "sell_price", "profit_pct", "dividends_occurred"]:
        v = res.get(key)
        if key == "dividends_occurred":
            v = "はい" if v else "いいえ"
        elif key in ("buy_date", "sell_date") and hasattr(v, 'strftime'):
            v = v.strftime("%Y-%m-%d")
        elif isinstance(v, float):
            v = f"{v:.4f}" if key == "profit_pct" else f"{v:.2f}"
        lines.append(f"{jp_map.get(key, key)}: {v}")
    return "\n".join(lines)


def main():
    sim = load_sim_module()

    # 引数が2つ与えられればそちらを使う、なければデフォルトの2ケース
    cases = []
    if len(sys.argv) >= 3:
        # 引数として2ケースを期待
        cases.append(sys.argv[1])
        cases.append(sys.argv[2])
    else:
        cases = [
            "1332.T,2020-01-10,30",
            "3382_T,2020-01-10,2021-03-15",
        ]

    for i, arg in enumerate(cases, start=1):
        print(f"--- シミュレーション {i} ---")
        try:
            ticker, buy, sell, hold_days = parse_arg(arg)
        except Exception as e:
            print(f"引数パースエラー: {e}")
            continue

        try:
            res = sim.simulate_trade(ticker, buy, sell_date=sell, hold_days=hold_days)
            print(format_result(res))
        except Exception as e:
            print(f"シミュ実行エラー: {e}")


if __name__ == "__main__":
    main()
