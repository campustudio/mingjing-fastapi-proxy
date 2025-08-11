# scripts/audit_indexes.py
import os, json
from collections import defaultdict
from pymongo import MongoClient

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB  = os.environ.get("MONGODB_DB", "mingjing")

# 你应用里“期望”的索引（用于对比）
EXPECTED = {
    "messages": [
        ( (("user_id", 1), ("created_at", 1)), {"unique": False, "sparse": False} ),
    ],
    "users": [
        ( (("username_lower", 1),), {"unique": True} ),
    ],
    "memories": [
        ( (("user_id", 1),), {"unique": True} ),
    ],
}

def norm_opts(ix):
    return {
        "unique": bool(ix.get("unique", False)),
        "sparse": bool(ix.get("sparse", False)),
        # 以下三个常见导致冲突的选项也纳入对比
        "partialFilterExpression": ix.get("partialFilterExpression", None),
        "collation": ix.get("collation", None),
        "expireAfterSeconds": ix.get("expireAfterSeconds", None),
    }

def main():
    assert MONGODB_URI, "Set MONGODB_URI first"
    cli = MongoClient(MONGODB_URI)
    db = cli[MONGODB_DB]

    cols = set(EXPECTED.keys())
    # 也可以自动扫描库里的所有集合：
    # cols.update(db.list_collection_names())

    has_problem = False

    for col in sorted(cols):
        if col not in db.list_collection_names():
            print(f"[{col}] (collection not found yet)")
            continue

        print(f"\n=== Inspecting {col} ===")
        idxs = list(db[col].list_indexes())
        # 按 key 分组
        groups = defaultdict(list)
        for ix in idxs:
            key_tuple = tuple(ix["key"].items())  # e.g. (('user_id',1),('created_at',1))
            groups[key_tuple].append(ix)

        # 打印所有同键的索引（名字不同/选项不同都能看出来）
        for key, g in groups.items():
            if len(g) > 1:
                has_problem = True
                print(f"[!] Multiple indexes with same keys {key}:")
                for ix in g:
                    print("   -", ix.get("name"), json.dumps(norm_opts(ix), ensure_ascii=False))

        # 和 EXPECTED 对比（如果配置了）
        expected_for_col = dict(EXPECTED.get(col, []))
        for key, exp_opts in expected_for_col.items():
            candidates = groups.get(key, [])
            if not candidates:
                has_problem = True
                print(f"[!] Missing expected index {key} on {col}")
                continue
            # 找是否存在一个与期望一致的索引
            if not any(norm_opts(ix) == {
                **{"unique": exp_opts.get("unique", False), "sparse": exp_opts.get("sparse", False)},
                "partialFilterExpression": None,
                "collation": None,
                "expireAfterSeconds": None,
            } for ix in candidates):
                has_problem = True
                print(f"[!] Found same-key index on {col} but options differ for {key}:")
                for ix in candidates:
                    print("   -", ix.get("name"), json.dumps(norm_opts(ix), ensure_ascii=False))
                # 给出建议 drop 命令（让应用按幂等逻辑重建）
                print("    Suggested dropIndex for the wrong ones:")
                for ix in candidates:
                    print(f"      db.{col}.dropIndex('{ix.get('name')}')")

    if not has_problem:
        print("\nAll good: no duplicate-key/different-option indexes found.")

if __name__ == "__main__":
    main()
