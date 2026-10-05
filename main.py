
import argparse
import os
import sys

from overview import Table, format_overview
from validation import validate_table, export_issues, format_validation, clean_rows
from stats import (group_by_first_choice, fill_pattern, export_summary,
                   export_clean, format_stats)


def ensure_outdir(outdir):
    os.makedirs(outdir, exist_ok=True)
    return outdir


def cmd_overview(table):
    print("=" * 46)
    print("需求 1 · 读入与概览")
    print("=" * 46)
    print(format_overview(table))


def cmd_validate(table, id_len, outdir):
    print()
    print("=" * 46)
    print("需求 2 · 校验与清洗")
    print("=" * 46)
    issues, dup_reg = validate_table(table, id_len)
    print(format_validation(issues, dup_reg))
    if issues:
        out_path = export_issues(issues, os.path.join(outdir, "issues.csv"))
        print()
        print("问题清单已导出：%s（原文件未做任何改动）" % out_path)


def cmd_stats(table, id_len, outdir):
    print()
    print("=" * 46)
    print("需求 3 · 统计与导出")
    print("=" * 46)
    issues, _ = validate_table(table, id_len)
    kept = clean_rows(table, issues)
    groups = group_by_first_choice(kept)
    pattern = fill_pattern(kept)
    print(format_stats(groups, pattern, len(kept), len(table.rows)))

    summary_path = export_summary(groups, os.path.join(outdir, "summary.csv"))
    clean_path = export_clean(kept, os.path.join(outdir, "clean.csv"))
    print()
    print("汇总表已导出：%s" % summary_path)
    print("干净数据已导出：%s" % clean_path)


def build_parser():
    parser = argparse.ArgumentParser(
        description="志愿 CSV 数据处理小工具（读入概览 / 校验清洗 / 统计导出）")
    parser.add_argument("command", choices=["overview", "validate", "stats", "all"],
                        help="overview=需求1 validate=需求2 stats=需求3 all=依次全跑")
    parser.add_argument("csv", help="要处理的 CSV 文件路径")
    parser.add_argument("--id-len", type=int, default=None, metavar="N",
                        help="约定学号位数（默认不校验位数，只校验纯数字）")
    parser.add_argument("--outdir", default="out", help="输出目录，默认 out")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not os.path.exists(args.csv):
        sys.exit("文件不存在：%s" % args.csv)

    table = Table(args.csv)
    missing = [c for c in ["姓名", "学号", "邮箱", "志愿1", "志愿2", "推荐人"]
               if c not in table.header]
    if missing:
        sys.exit("表头缺少必需字段：%s。请确认 CSV 列名与 README 约定一致。"
                 % "、".join(missing))

    if args.command in ("validate", "stats", "all"):
        ensure_outdir(args.outdir)

    if args.command in ("overview", "all"):
        cmd_overview(table)
    if args.command in ("validate", "all"):
        cmd_validate(table, args.id_len, args.outdir)
    if args.command in ("stats", "all"):
        cmd_stats(table, args.id_len, args.outdir)


if __name__ == "__main__":
    main()
