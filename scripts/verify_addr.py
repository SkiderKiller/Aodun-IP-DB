#!/usr/bin/env python3
"""发布前体检 .addr，任何一项不过就让 workflow 失败，避免把废文件推到 Release。

检查项对应踩过的坑：BOM 会让第 1 行解析失败；国家为中国大陆但省份为空的行
会被傲盾判格式错误。
"""
from __future__ import annotations

import ipaddress
import os
import sys
from pathlib import Path

MIN_LINES = 100000
CN_COUNTRY = "中国大陆"


def emit(**kwargs: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        for key, value in kwargs.items():
            print(f"{key}={value}")
        return
    with open(target, "a", encoding="utf-8") as f:
        for key, value in kwargs.items():
            f.write(f"{key}={value}\n")


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/all-ip-location.addr")
    if not path.exists():
        sys.exit(f"产物不存在: {path}")

    with path.open("rb") as f:
        head = f.read(4)
    problems: list[str] = []
    if head.startswith(b"\xef\xbb\xbf"):
        problems.append("文件带 BOM")

    total = cn = cn_empty = bad_fields = bad_ip = 0
    prev_end = -1
    unsorted = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\r\n")
            if not line:
                continue
            total += 1
            parts = line.split("|")
            if len(parts) != 8 or parts[7] != "":
                bad_fields += 1
                if bad_fields <= 3:
                    problems.append(f"第 {lineno} 行字段数异常: {line[:60]}")
                continue
            try:
                start = int(ipaddress.IPv4Address(parts[0]))
                end = int(ipaddress.IPv4Address(parts[1]))
            except ipaddress.AddressValueError:
                bad_ip += 1
                if bad_ip <= 3:
                    problems.append(f"第 {lineno} 行 IP 非法: {line[:60]}")
                continue
            if end < start:
                bad_ip += 1
                problems.append(f"第 {lineno} 行 起始 IP 大于结束 IP")
            if start <= prev_end:
                unsorted += 1
            prev_end = end
            if parts[5] == CN_COUNTRY:
                cn += 1
                if not parts[6].strip():
                    cn_empty += 1
                    if cn_empty <= 3:
                        problems.append(f"第 {lineno} 行 中国大陆缺省份: {line[:60]}")

    if total < MIN_LINES:
        problems.append(f"行数只有 {total}，少于下限 {MIN_LINES}，上游数据可能异常")
    if cn_empty:
        problems.append(f"共 {cn_empty} 行中国大陆缺省份")
    if unsorted:
        problems.append(f"共 {unsorted} 处网段未按升序排列或存在重叠")

    print(f"总行数        = {total}")
    print(f"中国大陆行数  = {cn}")
    print(f"缺省份        = {cn_empty}")
    print(f"字段数异常    = {bad_fields}")
    print(f"IP 异常       = {bad_ip}")
    print(f"乱序/重叠     = {unsorted}")
    print(f"大小          = {path.stat().st_size / 1048576:.1f} MB")

    emit(lines=str(total), cn_lines=str(cn))

    if problems:
        print("\n体检不通过:")
        for item in problems:
            print(f"  - {item}")
        sys.exit(1)
    print("\n体检通过")


if __name__ == "__main__":
    main()
