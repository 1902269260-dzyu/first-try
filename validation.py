"""需求 2 —— 校验与清洗。

规则（对每行独立判断，一行可命中多个问题）：
  1. 学号必须非空且为纯数字；命令行给了 --id-len 时还要求位数一致。
  2. 邮箱必须非空，且严格等于 学号@smbu.edu.cn（比较前去掉首尾空格）。
  3. 姓名、志愿1 为必填；志愿2、推荐人允许为空。
  4. 完全重复的行（每一列一字不差）：保留最早一行，其后每一行都算问题行。
  5. 重复报名：同一学号出现两次及以上（即使其他列不同），全部标记。
  6. 列数与表头不符的行本身就是脏数据，直接算问题行。

原文件只读不改。问题行连同“为什么有问题”导出为单独的问题清单 CSV。
"""

import csv

from overview import COLUMNS, is_blank

EMAIL_SUFFIX = "@smbu.edu.cn"

ISSUE_COLUMNS = ["原文件行号", "姓名", "学号", "邮箱", "志愿1", "志愿2", "推荐人", "问题原因"]


def check_row(row, header_len, id_len=None):
    """返回该行所有问题描述；空列表表示这行本身干净。"""
    problems = []

    if row.malformed:
        return ["列数与表头不符（表头 %d 列，本行 %d 列），无法可靠校验"
                % (header_len, len(row.cells))]

    name = row.field("姓名")
    student_id = row.field("学号")
    email = row.field("邮箱")

    if is_blank(name):
        problems.append("姓名为空")

    id_is_digits = False
    if is_blank(student_id):
        problems.append("学号为空")
    elif not student_id.isdigit():
        problems.append("学号不是纯数字（实际为「%s」）" % student_id)
    else:
        id_is_digits = True
        if id_len is not None and len(student_id) != id_len:
            problems.append("学号位数与约定不符（期望 %d 位，实际 %d 位）"
                            % (id_len, len(student_id)))

    if is_blank(email):
        problems.append("邮箱为空")
    elif id_is_digits and email != student_id + EMAIL_SUFFIX:
        problems.append("邮箱与学号不匹配（期望「%s%s」，实际「%s」）"
                        % (student_id, EMAIL_SUFFIX, email))

    if is_blank(row.field("志愿1")):
        problems.append("志愿1 为空")

    return problems


class IssueRow:
    """问题清单里的一行：原行数据 + 问题原因。"""

    def __init__(self, row, problems):
        self.row = row
        self.problems = problems

    @property
    def joined(self):
        return "；".join(self.problems)


def validate_table(table, id_len=None):
    """校验整张表，返回 (issues, dup_reg)。

    issues   : [IssueRow]，按原文件行号排序
    dup_reg  : {学号: [Row, ...]}，重复报名分组（只含出现≥2次的学号）
    """
    header_len = len(table.header)

    # 重复报名分组：学号非空即参与分组（哪怕不是纯数字，也方便人眼看出报了两次）
    by_id = {}
    for r in table.rows:
        sid = r.field("学号")
        if not is_blank(sid):
            by_id.setdefault(sid, []).append(r)
    dup_reg = {sid: g for sid, g in by_id.items() if len(g) > 1}

    # 完全重复行：每组保留第一行，其余行算问题
    dup_exact = table.duplicate_groups()
    later_copies = set()
    for group in dup_exact.values():
        for r in group[1:]:
            later_copies.add(r.line)

    issues = []
    for r in table.rows:
        problems = check_row(r, header_len, id_len)

        if r.line in later_copies:
            problems.append("与前面某行完全重复（内容一字不差）")

        sid = r.field("学号")
        if not is_blank(sid) and sid in dup_reg:
            others = [x.line for x in dup_reg[sid] if x.line != r.line]
            problems.append("重复报名：同一学号还出现在原文件第 %s 行"
                            % "、".join(str(n) for n in others))

        if problems:
            issues.append(IssueRow(r, problems))

    return issues, dup_reg


def clean_rows(table, issues):
    """清洗规则（README 里也会写明）：
      - 剔除问题清单中的全部行（包括“重复报名”组里的所有行，宁严勿漏，交人工裁决）
      - 完全重复只保留最早一行的逻辑已包含在“后一份必然进问题清单”里
    返回保留下来的 Row 列表。
    """
    bad_lines = {item.row.line for item in issues}
    return [r for r in table.rows if r.line not in bad_lines]


def export_issues(issues, out_path):
    """把问题行导出为问题清单 CSV（utf-8-sig，Excel 直接打开不乱码）。"""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(ISSUE_COLUMNS)
        for item in issues:
            r = item.row
            writer.writerow(
                [r.line] + [r.field(c) for c in COLUMNS] + [item.joined]
            )
    return out_path


def format_validation(issues, dup_reg):
    lines = ["发现问题行 %d 行（原因逐行见下，完整清单在问题 CSV 里）。" % len(issues)]
    if not issues:
        lines.append("未发现任何校验问题。")
    for item in issues:
        lines.append("· 第 %d 行（%s / 学号 %s）：%s"
                     % (item.row.line,
                        item.row.field("姓名") or "（无姓名）",
                        item.row.field("学号") or "（无学号）",
                        item.joined))
    if dup_reg:
        lines.append("")
        lines.append("重复报名的学号：")
        for sid, group in sorted(dup_reg.items()):
            lines.append("  学号 %s → 原文件第 %s 行（%s）"
                         % (sid,
                            "、".join(str(r.line) for r in group),
                            "、".join(r.field("姓名") or "（无姓名）" for r in group)))
    return "\n".join(lines)
