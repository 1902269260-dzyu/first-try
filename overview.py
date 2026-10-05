"""需求 1 —— 读入志愿 CSV 并打印概览。

概览包含三件事：
  1. 一共多少行（数据行数，另附空行数量）
  2. 每列有多少个空值
  3. 有没有完全重复的行（所有列内容一字不差）

本模块同时提供其他模块共用的读表能力（Row / Table / COLUMNS / is_blank），
所以 validation.py 与 stats.py 都从这里 import。
"""

import csv
import io

# 约定的表头字段（顺序即输出 CSV 时的列顺序）
COLUMNS = ["姓名", "学号", "邮箱", "志愿1", "志愿2", "推荐人"]

# 依次尝试的编码。Excel 另存的 CSV 常见是 utf-8-sig 或 gbk。
ENCODINGS = ("utf-8-sig", "utf-8", "gbk")


def is_blank(value):
    """空值的定义：None、空字符串、只有空格/制表符。"""
    return value is None or str(value).strip() == ""


class Row:
    """一行数据。

    line   : 在原始 CSV 文件中的行号（表头算第 1 行），方便用户回文件里定位
    cells  : csv 解析出的原始单元格列表（未去空格）
    values : {约定字段名: 去掉首尾空格后的字符串}
    extra  : 表头里多出来的、COLUMNS 之外的列
    malformed: 本行列数与表头列数不一致（脏数据里很常见）
    """

    __slots__ = ("line", "cells", "values", "extra", "malformed")

    def __init__(self, line, cells, header):
        self.line = line
        self.cells = cells
        self.malformed = len(cells) != len(header)
        self.values = {}
        self.extra = {}
        for idx, name in enumerate(header):
            cell = cells[idx].strip() if idx < len(cells) else ""
            if name in COLUMNS:
                self.values[name] = cell
            elif name:
                self.extra[name] = cell
        # 列数少于表头时，缺失的约定字段补空串，后续校验会报“某列为空”
        for name in COLUMNS:
            self.values.setdefault(name, "")

    @property
    def key(self):
        """用于判断“完全重复行”的指纹：约定列 + 额外列全部参与比较。"""
        return tuple(self.cells)

    def field(self, name):
        return self.values.get(name, "")


class Table:
    """读入后的整张表。"""

    def __init__(self, path):
        self.path = path
        text, encoding = _decode_file(path)
        self.encoding = encoding

        header_line = None
        rows = []
        blank_lines = []
        for idx, cells in enumerate(csv.reader(io.StringIO(text)), start=1):
            if not cells or all(is_blank(c) for c in cells):
                blank_lines.append(idx)
                continue
            if header_line is None:
                header_line = idx
                self.header = [c.strip() for c in cells]
                continue
            rows.append(Row(idx, cells, self.header))

        self.header_line = header_line
        self.rows = rows
        self.blank_lines = blank_lines

    # ---- 概览所需的统计 ----

    @property
    def missing_columns(self):
        return [c for c in COLUMNS if c not in self.header]

    @property
    def extra_columns(self):
        return [c for c in self.header if c not in COLUMNS]

    def blank_counts(self):
        """每列空值数量，返回 [(列名, 数量), ...]，按约定字段顺序。"""
        result = []
        for name in COLUMNS:
            if name in self.header:
                count = sum(1 for r in self.rows if is_blank(r.field(name)))
                result.append((name, count))
        for name in self.extra_columns:
            count = 0
            for r in self.rows:
                if is_blank(r.extra.get(name, "")):
                    count += 1
            result.append((name, count))
        return result

    def duplicate_groups(self):
        """完全重复的行组：{指纹: [Row, ...]}，只保留出现 >=2 次的。"""
        buckets = {}
        for r in self.rows:
            buckets.setdefault(r.key, []).append(r)
        return {k: v for k, v in buckets.items() if len(v) > 1}

    def malformed_rows(self):
        return [r for r in self.rows if r.malformed]


def _decode_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    last_error = None
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(
        "无法解码 %s（试过 %s）：%s" % (path, "、".join(ENCODINGS), last_error)
    )


def format_overview(table):
    """把概览拼成一段可直接打印的文本。"""
    lines = []
    lines.append("文件：%s" % table.path)
    lines.append("编码：%s" % table.encoding)

    if table.missing_columns:
        lines.append("⚠ 表头缺少约定字段：%s" % "、".join(table.missing_columns))
    if table.extra_columns:
        lines.append("⚠ 表头多出未约定字段：%s（统计时忽略）"
                     % "、".join(table.extra_columns))

    dup = table.duplicate_groups()
    extra_dup_rows = sum(len(v) - 1 for v in dup.values())
    malformed = table.malformed_rows()

    lines.append("")
    lines.append("【行数】")
    lines.append("数据行：%d 行（不含表头）" % len(table.rows))
    lines.append("表头行：第 %s 行" % table.header_line)
    if table.blank_lines:
        lines.append("空行：%d 行（第 %s 行，已跳过）"
                     % (len(table.blank_lines),
                        "、".join(str(n) for n in table.blank_lines)))
    if malformed:
        lines.append("列数与表头不符的行：%d 行（第 %s 行）"
                     % (len(malformed), "、".join(str(r.line) for r in malformed)))

    lines.append("")
    lines.append("【每列空值】")
    counts = table.blank_counts()
    if counts:
        width = max(len(name) for name, _ in counts) + 2
        for name, count in counts:
            flag = "" if count == 0 else "  ← 有空值"
            lines.append("%s%s%d 个%s" % (name, " " * (width - len(name)), count, flag))
    else:
        lines.append("（没有可统计的列）")

    lines.append("")
    lines.append("【完全重复的行】")
    if not dup:
        lines.append("未发现完全重复的行")
    else:
        lines.append("发现 %d 组、共 %d 行重复（多出 %d 行）："
                     % (len(dup), sum(len(v) for v in dup.values()), extra_dup_rows))
        for group_id, (_, group) in enumerate(sorted(
                dup.items(), key=lambda kv: kv[1][0].line), start=1):
            names = "、".join(str(r.line) for r in group)
            preview = " | ".join(c.strip() for c in group[0].cells) or "（整行为空）"
            lines.append("  第 %d 组：原文件第 %s 行 → %s"
                         % (group_id, names, preview))
    return "\n".join(lines)


def print_overview(path):
    """命令行入口：读入并打印概览，返回 Table 方便复用。"""
    table = Table(path)
    print(format_overview(table))
    return table
