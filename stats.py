"""需求 3 —— 统计与导出。

基于“清洗后的干净数据”（validation.clean_rows 的结果）做三件事：
  1. 按志愿1分组统计人数，输出汇总表（CSV + 终端表格）。
  2. 统计两个志愿都填了多少人、只填了一个的有多少人。
  3. 把清洗后的数据导出成新 CSV（列顺序按约定字段）。
"""

import csv

from overview import COLUMNS, is_blank


def group_by_first_choice(rows):
    """按志愿1分组计数，返回 [(志愿, 人数)]，按人数降序、同数按名称排。"""
    counts = {}
    for r in rows:
        v = r.field("志愿1")
        counts[v] = counts.get(v, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def fill_pattern(rows):
    """志愿填写情况：both=两个都填，only1=只填志愿1，only2=只填志愿2，none=都没填。"""
    both = only1 = only2 = none = 0
    for r in rows:
        has1 = not is_blank(r.field("志愿1"))
        has2 = not is_blank(r.field("志愿2"))
        if has1 and has2:
            both += 1
        elif has1:
            only1 += 1
        elif has2:
            only2 += 1
        else:
            none += 1
    return {"both": both, "only1": only1, "only2": only2, "none": none}


def export_summary(groups, out_path):
    """志愿1分组汇总表 CSV。"""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["志愿1", "人数"])
        for name, count in groups:
            writer.writerow([name, count])
    return out_path


def export_clean(rows, out_path):
    """清洗后的干净数据 CSV，只保留约定六列。"""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for r in rows:
            writer.writerow([r.field(c) for c in COLUMNS])
    return out_path


def format_stats(groups, pattern, kept, total):
    lines = []
    lines.append("清洗前 %d 行 → 清洗后保留 %d 行（剔除 %d 行，见问题清单）。"
                 % (total, kept, total - kept))
    lines.append("")
    lines.append("【按志愿1分组】")
    width = max((len(name) for name, _ in groups), default=4)
    for name, count in groups:
        lines.append("  %s %s%3d 人  %s" % (name, " " * (width - len(name)),
                                            count, "█" * count))
    lines.append("")
    lines.append("【志愿填写情况】")
    lines.append("  两个志愿都填了：%d 人" % pattern["both"])
    lines.append("  只填了志愿1：%d 人" % pattern["only1"])
    lines.append("  只填了志愿2：%d 人" % pattern["only2"])
    if pattern["none"]:
        lines.append("  两个都没填：%d 人" % pattern["none"])
    return "\n".join(lines)
