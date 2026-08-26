#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple, Iterator
import bisect
import csv

import maxminddb
from maxminddb.reader import Reader


UNKNOWN_CONTINENT = "其他区域"
UNKNOWN_COUNTRY = "其他区域"
DEFAULT_PROVINCE = ""
# 傲盾导入时国家为中国大陆的行必须带省份，否则整行被判格式错误
CN_COUNTRY = "中国大陆"
UNKNOWN_PROVINCE = "未知省"


@dataclass
class AddrRow:
    start: int
    end: int
    continent: str
    country: str
    province: str


@dataclass
class NameRange:
    start: int
    end: int
    continent: str
    country: str
    province: str


def parse_args() -> argparse.Namespace:
    today = dt.date.today().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Convert mmdb ranges to .addr format.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--mmdb",
        default=None,
        help="Path to mmdb file",
    )
    group.add_argument(
        "--csv",
        default=None,
        help="Path to dbip/geolite city csv file",
    )
    parser.add_argument(
        "--name-map-addr",
        default=guess_default_name_map(),
        help="Optional .addr file for country/continent Chinese names",
    )
    parser.add_argument(
        "--output",
        default=f"all-ip-location-{today}.addr",
        help="Output .addr file path",
    )
    return parser.parse_args()


def guess_default_mmdb() -> str:
    for name in [
        "geolite2-city-ipv4.mmdb",
        "geolite2-geo-whois-asn-country-ipv4.mmdb",
    ]:
        if Path(name).exists():
            return name
    return "geolite2-city-ipv4.mmdb"


def guess_default_name_map() -> Optional[str]:
    preferred = Path("all-ip-location-2023-08-14.addr")
    if preferred.exists():
        return str(preferred)
    candidates = sorted(Path(".").glob("all-ip-location-*.addr"))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    return None


def int_to_ip(value: int) -> str:
    return str(ipaddress.IPv4Address(value))


def normalize_region(value: str) -> str:
    return (value or "").strip()


def parse_addr_name_index(path: Path) -> Tuple[list[NameRange], list[int]]:
    ranges: list[NameRange] = []
    starts: list[int] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("|")
            if len(fields) < 6:
                continue
            start_ip = fields[0].strip()
            end_ip = fields[1].strip()
            continent = fields[4].strip()
            country = fields[5].strip()
            province = fields[6].strip() if len(fields) > 6 else ""
            try:
                start = int(ipaddress.IPv4Address(start_ip))
                end = int(ipaddress.IPv4Address(end_ip))
            except Exception:
                continue
            ranges.append(NameRange(start, end, continent, country, province))
            starts.append(start)
    return ranges, starts


def lookup_name(
    ip_value: int,
    ranges: list[NameRange],
    starts: list[int],
) -> Optional[NameRange]:
    if not ranges:
        return None
    idx = bisect.bisect_right(starts, ip_value) - 1
    if idx < 0:
        return None
    r = ranges[idx]
    if ip_value <= r.end:
        return r
    return None


def get_cc_name(
    cc: str,
    ip_value: int,
    name_ranges: list[NameRange],
    name_starts: list[int],
    cc_name_map: dict[str, Tuple[str, str]],
) -> Tuple[str, str]:
    if not cc:
        return UNKNOWN_CONTINENT, UNKNOWN_COUNTRY
    if cc in ("HK", "MO", "TW"):
        return "亚洲", f"中国{ {'HK':'香港','MO':'澳门','TW':'台湾'}[cc] }"
    if cc == "CN":
        return "亚洲", CN_COUNTRY
    if cc == "KP":
        return "亚洲", "朝鲜"
    if cc in cc_name_map:
        return cc_name_map[cc]
    if name_ranges:
        hit = lookup_name(ip_value, name_ranges, name_starts)
        if hit and hit.country and hit.country != UNKNOWN_COUNTRY:
            continent = hit.continent if hit.continent else UNKNOWN_CONTINENT
            cc_name_map[cc] = (continent, hit.country)
            return cc_name_map[cc]
    return UNKNOWN_CONTINENT, cc


def get_cn_province(
    region: str,
    ip_value: int,
    name_ranges: list[NameRange],
    name_starts: list[int],
) -> str:
    region = normalize_region(region)
    if region:
        mapped = CN_PROVINCE_MAP.get(region)
        if mapped:
            return mapped
    hit = lookup_name(ip_value, name_ranges, name_starts)
    if hit and hit.province:
        return hit.province
    if region:
        return region
    return DEFAULT_PROVINCE


def pick_province(record: dict) -> str:
    # City mmdb usually has state1/state2/city; country mmdb won't.
    for key in ("state1", "state2", "city"):
        value = normalize_region(record.get(key, ""))
        if value:
            return value
    return DEFAULT_PROVINCE


CN_PROVINCE_MAP = {
    "Anhui": "安徽",
    "Beijing": "北京",
    "Chongqing": "重庆",
    "Fujian": "福建",
    "Gansu": "甘肃",
    "Guangdong": "广东",
    "Guangxi": "广西",
    "Guizhou": "贵州",
    "Hainan": "海南",
    "Hebei": "河北",
    "Heilongjiang": "黑龙江",
    "Henan": "河南",
    "Hong Kong": "香港",
    "Hubei": "湖北",
    "Hunan": "湖南",
    "Inner Mongolia": "内蒙古",
    "Nei Mongol": "内蒙古",
    "Jiangsu": "江苏",
    "Jiangxi": "江西",
    "Jilin": "吉林",
    "Liaoning": "辽宁",
    "Macau": "澳门",
    "Macao": "澳门",
    "Ningxia": "宁夏",
    "Qinghai": "青海",
    "Shaanxi": "陕西",
    "Shandong": "山东",
    "Shanghai": "上海",
    "Shanxi": "山西",
    "Sichuan": "四川",
    "Tianjin": "天津",
    "Tibet": "西藏",
    "Xinjiang": "新疆",
    "Yunnan": "云南",
    "Zhejiang": "浙江",
    "Taiwan": "台湾",
}


def iter_mmdb_rows(
    reader: Reader,
    name_ranges: list[NameRange],
    name_starts: list[int],
) -> Iterator[AddrRow]:
    cc_name_map: dict[str, Tuple[str, str]] = {}
    for network, record in reader:
        if network.version != 4:
            continue
        if not isinstance(record, dict):
            cc = ""
            province = DEFAULT_PROVINCE
        else:
            cc = (record.get("country_code") or "").strip()
            if cc and cc != "CN":
                province = DEFAULT_PROVINCE
            else:
                province = pick_province(record)
        continent, country = get_cc_name(
            cc,
            int(network.network_address),
            name_ranges,
            name_starts,
            cc_name_map,
        )
        yield AddrRow(
            start=int(network.network_address),
            end=int(network.broadcast_address),
            continent=continent,
            country=country,
            province=province,
        )


def iter_csv_rows(
    csv_path: Path,
    name_ranges: list[NameRange],
    name_starts: list[int],
) -> Iterator[AddrRow]:
    cc_name_map: dict[str, Tuple[str, str]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2:
                continue
            start_ip = row[0].strip()
            end_ip = row[1].strip()
            try:
                start = int(ipaddress.IPv4Address(start_ip))
                end = int(ipaddress.IPv4Address(end_ip))
            except Exception:
                continue
            cc = row[2].strip() if len(row) > 2 else ""
            region = row[3].strip() if len(row) > 3 else ""
            city = row[5].strip() if len(row) > 5 else ""
            if cc and cc != "CN":
                province = DEFAULT_PROVINCE
            else:
                province = get_cn_province(region or city, start, name_ranges, name_starts)
            continent, country = get_cc_name(
                cc,
                start,
                name_ranges,
                name_starts,
                cc_name_map,
            )
            yield AddrRow(
                start=start,
                end=end,
                continent=continent,
                country=country,
                province=province,
            )


def write_addr(path: Path, rows: Iterable[AddrRow]) -> int:
    count = 0
    prev: Optional[AddrRow] = None
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            if row.country == CN_COUNTRY and not row.province.strip():
                row.province = UNKNOWN_PROVINCE
            if prev is None:
                prev = row
                continue
            if (
                prev.end + 1 == row.start
                and prev.continent == row.continent
                and prev.country == row.country
                and prev.province == row.province
            ):
                prev.end = row.end
                continue
            f.write(
                f"{int_to_ip(prev.start)}|{int_to_ip(prev.end)}|0|0|"
                f"{prev.continent}|{prev.country}|{prev.province}|\n",
            )
            count += 1
            prev = row
        if prev is not None:
            f.write(
                f"{int_to_ip(prev.start)}|{int_to_ip(prev.end)}|0|0|"
                f"{prev.continent}|{prev.country}|{prev.province}|\n",
            )
            count += 1
    return count


def main() -> None:
    args = parse_args()
    csv_path: Optional[Path] = Path(args.csv) if args.csv else None
    mmdb_path: Optional[Path] = Path(args.mmdb) if args.mmdb else None
    if csv_path is None and mmdb_path is None:
        mmdb_path = Path(guess_default_mmdb())
    if csv_path is not None and not csv_path.exists():
        raise FileNotFoundError(f"csv file not found: {csv_path}")
    if mmdb_path is not None and not mmdb_path.exists():
        raise FileNotFoundError(f"mmdb file not found: {mmdb_path}")

    name_ranges: list[NameRange] = []
    name_starts: list[int] = []
    if args.name_map_addr:
        name_path = Path(args.name_map_addr)
        if name_path.exists():
            name_ranges, name_starts = parse_addr_name_index(name_path)

    if csv_path is not None:
        rows: Iterable[AddrRow] = iter_csv_rows(csv_path, name_ranges, name_starts)
        rows_iter = rows
    else:
        with Reader(str(mmdb_path), mode=maxminddb.MODE_MEMORY) as reader:
            rows_iter = list(iter_mmdb_rows(reader, name_ranges, name_starts))

    output_path = Path(args.output)
    count = write_addr(output_path, rows_iter)
    print(f"output={output_path}")
    print(f"ranges={count}")


if __name__ == "__main__":
    main()
