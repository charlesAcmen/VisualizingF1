import argparse
import json
from pathlib import Path

import fastf1
import pandas as pd


def format_lap_time(value):
    if value is None or pd.isna(value):
        return None
    total_seconds = value.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes}:{seconds:06.3f}"


def float_or_none(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def int_or_none(value):
    if value is None or pd.isna(value):
        return None
    return int(value)


def resolve_event_name(event):
    if event is None:
        return None
    try:
        return event.get("EventName")
    except AttributeError:
        try:
            return event["EventName"]
        except Exception:
            return str(event)


def main():
    parser = argparse.ArgumentParser(description="Build a single-lap telemetry JSON for the web demo.")
    parser.add_argument("--season", type=int, default=2023)
    parser.add_argument("--gp", type=str, default="Bahrain")
    parser.add_argument("--session", type=str, default="Q")
    parser.add_argument("--driver", type=str, default="VER")
    parser.add_argument("--lap", type=str, default="fastest")
    parser.add_argument("--out", type=str, default=str(Path(__file__).parent / "data" / "lap_telemetry.json"))
    parser.add_argument("--dedupe-distance", action="store_true", help="Drop duplicated distance rows.")
    parser.add_argument("--fill-missing-with-zero", action="store_true", help="Fill missing values with zero.")
    parser.add_argument("--round-decimals", type=int, default=-1, help="Round numeric values to N decimals (-1 keeps full precision).")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    cache_dir = repo_root / ".fastf1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    fastf1.Cache.enable_cache(str(cache_dir))
    fastf1.set_log_level("WARNING")

    session = fastf1.get_session(args.season, args.gp, args.session)
    session.load(telemetry=True, weather=False, messages=False)

    driver = args.driver.strip().upper()
    laps = session.laps.pick_drivers(driver)
    if laps.empty:
        raise SystemExit(f"No laps found for driver '{driver}'.")

    if args.lap.lower() == "fastest":
        lap = laps.pick_fastest()
    else:
        try:
            lap_number = int(args.lap)
        except ValueError as exc:
            raise SystemExit("Lap must be 'fastest' or an integer lap number.") from exc
        lap = laps.pick_lap(lap_number)
        if lap.empty:
            raise SystemExit(f"Lap {lap_number} not found for driver '{driver}'.")

    car_data = lap.get_car_data()
    car_data = car_data.add_distance()
    car_data = car_data[car_data["Distance"].notna()].copy()
    if args.dedupe_distance:
        car_data = car_data.loc[~car_data["Distance"].duplicated()].reset_index(drop=True)

    channels = [
        ("Speed", "km/h"),
        ("Throttle", "%"),
        ("Brake", "bool"),
        ("RPM", "rpm"),
        ("nGear", "gear"),
    ]

    if args.round_decimals >= 0:
        distance_values = [
            None if val is None else round(val, args.round_decimals)
            for val in [float_or_none(v) for v in car_data["Distance"].to_numpy()]
        ]
    else:
        distance_values = [float_or_none(v) for v in car_data["Distance"].to_numpy()]
    data = {"distance_m": distance_values}
    channel_units = {}
    for channel, unit in channels:
        if channel not in car_data.columns:
            continue
        channel_units[channel] = unit
        series = car_data[channel]
        if args.fill_missing_with_zero:
            series = series.fillna(0)
        if channel == "Brake":
            values = [int_or_none(val) for val in series.to_numpy()]
        elif channel == "nGear":
            values = [int_or_none(val) for val in series.to_numpy()]
        else:
            values = [float_or_none(val) for val in series.to_numpy()]

        if args.round_decimals >= 0 and channel not in {"Brake", "nGear"}:
            values = [None if val is None else round(val, args.round_decimals) for val in values]
        data[channel] = values

    lap_time = format_lap_time(lap.get("LapTime"))
    lap_number_value = int(lap.get("LapNumber")) if not pd.isna(lap.get("LapNumber")) else None
    meta = {
        "season": args.season,
        "event": resolve_event_name(session.event),
        "session": session.name,
        "driver": driver,
        "lap_number": lap_number_value,
        "lap_time": lap_time,
    }

    output = {
        "meta": meta,
        "channels": list(channel_units.keys()),
        "channel_units": channel_units,
        "data": data,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
