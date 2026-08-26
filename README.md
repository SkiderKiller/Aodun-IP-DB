# Aodun-IP-DB

自动把 [sapics/ip-location-db](https://github.com/sapics/ip-location-db) 的
GeoLite2 城市库转换成傲盾可导入的 `.addr`，并发到 Release。

## 下载

固定地址，永远指向最新一版：

```
https://github.com/SkiderKiller/Aodun-IP-DB/releases/latest/download/all-ip-location.addr
```

## 工作方式

每天 03:17 UTC（北京时间 11:17）跑一次 [`build-addr.yml`](.github/workflows/build-addr.yml)：

1. 查上游 release `latest` 里 `geolite2-city-ipv4.csv.7z` 的 SHA256。
   GitHub API 的 asset 直接带 `digest` 字段，所以这步不用下那 17MB 的包。
2. 跟 [`state/upstream.json`](state/upstream.json) 里记的值比对，**一样就直接结束**。
3. 不一样才下载、校验 SHA256、解压、跑转换。
4. 产物过一遍体检（见下），通过才发 Release，然后把新 SHA256 提交回仓库。

也可以在 Actions 页面手动触发，勾上 `force` 能忽略 SHA256 强制重建。

## 输出格式

```
1.0.1.0|1.0.3.255|0|0|亚洲|中国大陆|福建|
1.0.4.0|1.0.7.255|0|0|大洋洲|澳大利亚||
```

`起始IP|结束IP|0|0|洲|国家|省份|`，UTF-8 **无 BOM**，LF 换行。

## 体检项

[`scripts/verify_addr.py`](scripts/verify_addr.py) 在发布前检查，任何一项不过就让
workflow 失败，避免把废文件推上去：

- 不能带 BOM —— BOM 会让第 1 行的起始 IP 变成 `﻿1.0.1.0`，傲盾解析失败
- 每行必须 8 个字段、行尾带 `|`
- **国家为「中国大陆」的行必须有省份** —— 空省份会被判格式错误，
  转换脚本会把查不到的填成「未知省」
- IP 合法、起始不大于结束、整体升序不重叠
- 总行数不低于 10 万，防止上游数据出问题时发出一个空文件

## 省份中文名

`convert_geolite2_to_addr.py` 的 `--csv` 分支会先查内置的 `CN_PROVINCE_MAP`
拿中文省名，查不到再拿 [`namemap/`](namemap/) 里的旧 `.addr` 按 IP 段反查。
少了这个名称表，中国大陆的省份会变成 `Guangdong` 这种英文，且覆盖率明显下降。

## 授权

数据来自 GeoLite2，经 sapics/ip-location-db 分发，遵循
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。
