# Safe File Operation Checklist

1. 使用 `pwd`，并把所有源路径和目标路径限制在 `$lab` 内。
2. `cp` 或 `mv` 的目标路径已经存在时，会丢失目标路径上的旧版本文件。
3. 删除前先使用精确条件预览目标：

   ```bash
   find "$lab/archive" -maxdepth 1 -type f -name 'keep.txt' -print
   ```

   从预览切换到删除时，只把 `-print` 改成 `-delete`；起点、`-maxdepth`、`-type` 和 `-name` 不变。
4. 如果没有备份、快照或版本记录，被删除或覆盖的旧内容可能无法恢复；因此操作前应该备份。
5. 操作后使用以下命令验证结果：
   - `test ! -e <旧路径>`：确认旧路径已经消失。
   - `test -f <新路径>`：确认新文件已经存在且为普通文件。
   - `cmp -s <源文件> <目标文件>`：确认两份文件内容一致。
   - `find <范围> -print`：查找范围内符合条件的文件或路径。

## Incident Review

拒绝直接覆盖并执行过宽删除。覆盖前需要先备份被覆盖版本；删除前应该先打印将要删除的目标文件。原建议会先把今天的新版 `report.txt` 覆盖到昨天唯一可回退版本，然后又把包括刚覆盖新内容的 `report-final.txt` 在内的 `archive` 第一层普通文件全部删除。

首次只读检查命令：

```bash
find "$lab/archive" -maxdepth 1 -type f -print
```

## English Summary

I created a file in `$lab/source/report.txt`, and then I copied it to `archive/report-copy.txt`. The source file still exists. I moved `source/keep.txt` to `archive/keep.txt`. I renamed `report-copy.txt` to `report-final.txt`. I previewed and removed `keep.txt`.
