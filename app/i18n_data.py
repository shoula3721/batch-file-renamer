"""翻译表：中文原文 -> English / 日本語。"""

from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "0 个文件": "0 files",
        "EXIF 时间通常没有时区信息，默认保持原始值；视频 mvhd 是 UTC，选择“转换为本地时间”会按系统时区转换。": (
            "EXIF times usually carry no time zone, so the original value is kept by default; "
            "video mvhd is UTC, and “Convert to local time” converts it using the system time zone."
        ),
        "ISO 感光度": "ISO sensitivity",
        "一键还原": "One-click restore",
        "一键还原…": "One-click restore…",
        "上移": "Move up",
        "下移": "Move down",
        "不改变": "Keep unchanged",
        "不足位补齐": "Pad with zeros",
        "专辑 / 系列": "Album / Series",
        "个字符": "characters",
        "个字符开始": "of the file name",
        "中文": "中文",
        "仅替换首次匹配": "Replace first match only",
        "从文件名第": "From character",
        "优先读取 EXIF 与视频 mvhd 时间；找不到时自动回退文件修改时间，并在“拍摄时间”列用 ⓘ 标出。": (
            "EXIF and video mvhd times are read first; if unavailable, the file modified time is used "
            "and marked with ⓘ in the “Shot time” column."
        ),
        "位数": "Digits",
        "使用 * 插入原始文件名，使用 # 插入编号；\n点击下方占位符可插入日期、拍摄时间、文件大小等内容。": (
            "Use * for the original file name and # for the sequence number;\n"
            "click a placeholder below to insert dates, shot time, file size, and more."
        ),
        "使用正则表达式": "Use regular expression",
        "使用说明": "Instructions",
        "例如：A_#，留空则保留原名": "e.g. A_#; leave empty to keep the original name",
        "元数据": "Metadata",
        "先写入 JSON 备份，再用临时名两阶段改名；失败自动回滚": (
            "Write a JSON backup first, then rename in two stages through temporary names; "
            "failures roll back automatically"
        ),
        "光圈，如 f/2.8": "Aperture, e.g. f/2.8",
        "全选": "Select all",
        "全部扩展名": "All extensions",
        "全部移除": "Remove all",
        "共删除": "Total removed",
        "关于": "About",
        "关闭": "Close",
        "准备中…": "Preparing…",
        "分钟": "minute",
        "删除": "Delete",
        "删除文件名中所有匹配文本": "Delete all matching text in file names",
        "删除文件名中的": "Delete from the file name",
        "刷新列表": "Refresh list",
        "包含扩展名": "Include extension",
        "区分大小写": "Case sensitive",
        "原位置被占用时": "If the original path is taken",
        "原文件名（不含扩展名）": "Original file name (without extension)",
        "发布年份": "Release year",
        "取消": "Cancel",
        "含子文件夹": "Include subfolders",
        "命名规则": "Naming rule",
        "命名规则、编号、扩展名与大小写。规则为空时保留原文件名。": (
            "Naming rule, numbering, extension, and case. An empty rule keeps the original file name."
        ),
        "增量": "Increment",
        "备份与还原": "Backup & Restore",
        "备份目录里还没有记录": "No records in the backup folder yet",
        "备份管理": "Backup manager",
        "备份管理…": "Backup manager…",
        "外观设置": "Appearance",
        "夜间": "Dark",
        "大写": "Uppercase",
        "字母编号": "Letters",
        "导入方案": "Import preset",
        "导入方案…": "Import preset…",
        "导出方案": "Export preset",
        "导出方案…": "Export preset…",
        "小写": "Lowercase",
        "小时": "hour",
        "帮助": "Help",
        "年份": "Year",
        "开始于": "Start at",
        "开始重命名": "Start renaming",
        "当前文件": "Current file",
        "或输入 mp4;mkv": "or type mp4;mkv",
        "所有改名操作执行前都会自动生成 JSON 备份": (
            "A JSON backup is created automatically before every rename operation"
        ),
        "打开备份目录": "Open backup folder",
        "扩展删除": "Remove extension",
        "扩展名": "Extension",
        "扩展名改成": "Change extension to",
        "扩展添加": "Add extension",
        "批量文件改名": "Batch File Rename",
        "批量重命名 · 预览先行 · 随时可还原": (
            "Batch rename · Preview first · Restore anytime"
        ),
        "把": "Replace",
        "拍摄时间原文（EXIF / 视频）": "Shot time, raw (EXIF / video)",
        "拍摄时间（EXIF / 视频）": "Shot time (EXIF / video)",
        "按 EXIF 原始时间": "Use raw EXIF time",
        "按修改时间排序": "Sort by modified time",
        "按名称排序": "Sort by name",
        "按大小排序": "Sort by size",
        "按序号排序": "Sort by number",
        "按拍摄时间排序": "Sort by shot time",
        "插入占位符": "Insert placeholder",
        "撤销上一次重命名": "Undo last rename",
        "撤销本次重命名": "Undo this rename",
        "改变扩展名为大写": "Uppercase extension",
        "改变扩展名为小写": "Lowercase extension",
        "改变文件名为大写": "Uppercase file name",
        "改变文件名为小写": "Lowercase file name",
        "改变文件名和扩展名为大写": "Uppercase file name and extension",
        "改变文件名和扩展名为小写": "Lowercase file name and extension",
        "整体": "Entire name",
        "文件": "File",
        "文件修改时间": "File modified time",
        "文件列表": "File list",
        "文件创建时间": "File created time",
        "文件名前添加": "Prepend to file name",
        "文件名后添加": "Append to file name",
        "文件名称选项": "File name options",
        "文件大小": "File size",
        "日": "day",
        "日期时间：2026-11-21_214000": "Date time: 2026-11-21_214000",
        "日期来源": "Date source",
        "日期格式": "Date format",
        "日期：2026-11-21（格式见上方设置）": "Date: 2026-11-21 (see the format above)",
        "日本語": "日本語",
        "时区": "Time zone",
        "时间：214000": "Time: 214000",
        "替换": "Replace",
        "替换成": "with",
        "替换成（可留空表示删除）": "Replace with (leave empty to delete)",
        "替换文件名中的字符": "Replace characters in file names",
        "最近方案": "Recent presets",
        "月份": "month",
        "未选择文件": "No file selected",
        "标题 / 曲名": "Title / Track",
        "正则示例：^IMG_(\\d+) → 照片_$1\n支持 $1、\\1 或 ${name} 形式的捕获组引用。": (
            "Regex example: ^IMG_(\\d+) → photo_$1\n"
            "Supports capture group references as $1, \\1, or ${name}."
        ),
        "正在重命名": "Renaming",
        "每次改名都会先写入 JSON 备份。选择一批已完成的记录即可把文件还原到原名称；原位置被占用时默认跳过，不会覆盖。": (
            "Every rename writes a JSON backup first. Select a completed batch to restore files to "
            "their original names; taken original paths are skipped by default and never overwritten."
        ),
        "添加": "Add",
        "添加删除": "Add / Remove",
        "添加在文件名最前面": "Add at the start of the file name",
        "添加在文件名最后面": "Add at the end of the file name",
        "添加字符串": "Add text",
        "添加文件": "Add files",
        "添加文件…": "Add files…",
        "添加文件夹": "Add folder",
        "添加文件夹…": "Add folder…",
        "添加文件夹时一并扫描子文件夹中的文件": "Also scan subfolders when adding a folder",
        "清空列表": "Clear list",
        "清空拍摄时间缓存，重新读取列表中全部文件（文件被外部修改后使用）": (
            "Clear the shot-time cache and re-read every file in the list "
            "(use after files change outside the app)"
        ),
        "清除筛选": "Clear filters",
        "点击“添加”选择文件，或直接把文件/文件夹拖到窗口里。\n所有改动都只显示在“预览”列，确认后才会写入磁盘。": (
            "Click “Add” to choose files, or drag files/folders into the window.\n"
            "All changes appear only in the “Preview” column and are written to disk once confirmed."
        ),
        "点击占位符会插入到上方命名规则的光标位置。": (
            "Clicking a placeholder inserts it at the cursor in the naming rule above."
        ),
        "白天": "Light",
        "相机型号": "Camera model",
        "秒": "second",
        "移除": "Remove",
        "移除所选": "Remove selected",
        "筛选": "Filter",
        "筛选扩展名": "Filter extensions",
        "筛选扩展名…": "Filter extensions…",
        "编号": "Numbering",
        "编号（同 #）": "Number (same as #)",
        "编辑": "Edit",
        "置底": "Move to bottom",
        "置顶": "Move to top",
        "自动加序号 (1)、(2)…": "Auto-number (1), (2)…",
        "自动解决命名冲突（追加 (1)、(2)…）": (
            "Auto-resolve conflicts ((1), (2)…)"
        ),
        "自定义": "Custom",
        "自定义格式": "Custom format",
        "艺术家 / 导演": "Artist / Director",
        "要插入的字符串": "Text to insert",
        "要查找的文本": "Text to find",
        "视图": "View",
        "语言": "Language",
        "请选择要还原的批次": "Select a batch to restore",
        "跟随系统": "Follow system",
        "跳过，不覆盖（推荐）": "Skip, do not overwrite (recommended)",
        "转换为本地时间": "Convert to local time",
        "还原所选": "Restore selected",
        "还没有添加文件": "No files added yet",
        "退出": "Exit",
        "重命名完成": "Rename complete",
        "重新读取元数据": "Re-read metadata",
        "重置为默认设置": "Reset to defaults",
        "镜头": "Lens",
        "风格 / 分类": "Genre / Category",
        # ---- 动态模板与提示 ----
        "{total} 个文件 · 筛选 {filter} · 预计成功 {ready} · 冲突 {conflict} · 错误 {error} · 未更改 {unchanged}": (
            "{total} files · Filter {filter} · Ready {ready} · Conflicts {conflict} · "
            "Errors {error} · Unchanged {unchanged}"
        ),
        "全部": "All",
        "{count} 个文件": "{count} files",
        "筛选 {visible} / {total} 个文件": "Showing {visible} of {total} files",
        "已添加 {added} 个文件（来自 {folders} 个文件夹）": "Added {added} files (from {folders} folders)",
        "已添加 {added} 个文件": "Added {added} files",
        "已移除 {removed} 个文件": "Removed {removed} files",
        "一次最多添加 {max} 个文件，超出部分已忽略": (
            "At most {max} files can be added at once; the rest were ignored"
        ),
        "文件：{name}": "File: {name}",
        "大小：{size} · 修改时间：{modified}": "Size: {size} · Modified: {modified}",
        "拍摄时间：读取中…": "Shot time: reading…",
        "拍摄时间：{time}（{source}）": "Shot time: {time} ({source})",
        "拍摄时间：未检测到（命名时回退文件修改时间）": (
            "Shot time: not detected (falls back to the file modified time when naming)"
        ),
        "元数据原文：{raw}": "Metadata (raw): {raw}",
        "已选择 {count} 个文件": "{count} files selected",
        "未知": "Unknown",
        "标题": "Title",
        "风格": "Genre",
        "相机": "Camera",
        "未检测到拍摄时间，命名时将回退到文件修改时间": (
            "No shot time detected; naming will fall back to the file modified time"
        ),
        "拍摄时间：{time}": "Shot time: {time}",
        "来源：{source}": "Source: {source}",
        "未找到媒体时间，已回退到文件修改时间": (
            "No media time found; fell back to the file modified time"
        ),
        "标题：{value}": "Title: {value}",
        "艺术家 / 导演：{value}": "Artist / Director: {value}",
        "专辑 / 系列：{value}": "Album / Series: {value}",
        "风格：{value}": "Genre: {value}",
        "年份：{value}": "Year: {value}",
        "相机 {value}": "Camera {value}",
        "镜头 {value}": "Lens {value}",
        "成功 {success} 个 · 失败 {failed} 个 · 跳过 {skipped} 个": (
            "Succeeded {success} · Failed {failed} · Skipped {skipped}"
        ),
        "原位置被占用而跳过 {count} 个": "Skipped {count} (original path in use)",
        "文件已不存在 {count} 个": "{count} files no longer exist",
        "该批次没有完全还原，可稍后重试剩余文件。": (
            "This batch was not fully restored; you can retry the remaining files later."
        ),
        "…还有 {count} 条失败记录": "…and {count} more failure records",
        "该批次不可还原：只有“完成 / 部分失败”的重命名批次支持一键还原。": (
            "This batch cannot be restored: only “Completed / Partially failed” rename batches "
            "support one-click restore."
        ),
        "将还原 {count} 个文件": "Will restore {count} files",
        "跳过 {count} 个（原位置被占用）": "Skip {count} (original path in use)",
        "缺失 {count} 个": "Missing {count}",
        "读取备份失败：{error}": "Failed to read backup: {error}",
        "请先添加要重命名的文件": "Please add files to rename first",
        "预览尚未完成，请稍候再点击“开始重命名”": (
            "The preview is not ready yet; please wait before clicking “Start renaming”"
        ),
        "没有需要重命名的文件（全部未更改或存在错误）": (
            "No files need renaming (all unchanged or with errors)"
        ),
        "正在撤销": "Undoing",
        "正在还原": "Restoring",
        "撤销完成": "Undo complete",
        "还原完成": "Restore complete",
        "共 {count} 个文件，按“写入备份 → 临时名 → 目标名”执行。": (
            "{count} files will be processed as “write backup → temporary name → target name”."
        ),
        "正在把批次 {batch} 的 {count} 个文件还原到原名称。": (
            "Restoring {count} files of batch {batch} to their original names."
        ),
        "正在还原批次 {batch} 的 {count} 个文件。": (
            "Restoring {count} files of batch {batch}."
        ),
        "操作失败": "Operation failed",
        "执行过程中出现错误：\n{message}\n\n如果已有文件被改动，请重新启动程序，启动时会提示恢复未完成的批次；也可以在“编辑 → 一键还原”中查看备份记录。": (
            "An error occurred during execution:\n{message}\n\n"
            "If any files were changed, restart the app; on startup it will offer to recover the "
            "unfinished batch. You can also check backup records under “Edit → One-click restore”."
        ),
        "没有可撤销的重命名记录。": "There is no rename record to undo.",
        "上一次重命名没有成功项，无需撤销。": (
            "The last rename had no successful items, so there is nothing to undo."
        ),
        "该批次没有成功改名的文件。": "This batch has no successfully renamed files.",
        "该批次没有可还原的文件。": "This batch has no files to restore.",
        "找不到备份记录：{batch}": "Backup record not found: {batch}",
        "批次：{created}\n将把 {count} 个文件还原到原名称。\n原位置被占用时会跳过，不会覆盖。": (
            "Batch: {created}\n"
            "Will restore {count} files to their original names.\n"
            "Taken original paths will be skipped, never overwritten."
        ),
        "确认还原": "Confirm restore",
        "将还原批次 {batch} 的 {count} 个文件；{policy}。": (
            "Will restore {count} files of batch {batch}; {policy}."
        ),
        "跳过被占用的原位置": "Skip taken original paths",
        "原位置被占用时自动加序号": "Auto-number when the original path is taken",
        "确认退出": "Confirm exit",
        "已恢复默认设置": "Default settings restored",
        "已切换为白天模式": "Switched to light mode",
        "已切换为夜间模式": "Switched to dark mode",
        "外观已跟随系统": "Appearance now follows the system",
        "外观已更新": "Appearance updated",
        "语言已切换为 {language}": "Language switched to {language}",
        "备份目录不可用": "Backup folder unavailable",
        "无法读取或创建备份目录：{error}\n\n为避免改名后无法还原，已禁用执行操作。": (
            "Cannot read or create the backup folder: {error}\n\n"
            "Execution is disabled so that renames cannot become unrecoverable."
        ),
        "发现未完成的重命名": "Unfinished rename detected",
        "已保留未完成批次，可在“编辑 → 一键还原”查看备份。": (
            "The unfinished batch was kept; see “Edit → One-click restore” for its backup."
        ),
        "恢复失败": "Recovery failed",
        "恢复完成": "Recovery complete",
        "已还原 {count} 个文件。{detail}": "Restored {count} files. {detail}",
        "无法导入方案：\n{error}": "Cannot import preset:\n{error}",
        "已导入方案：{name}": "Preset imported: {name}",
        "无法写入方案：\n{error}": "Cannot write preset:\n{error}",
        "已导出方案：{name}": "Preset exported: {name}",
        "方案文件已不存在：\n{path}": "Preset file no longer exists:\n{path}",
        "无法读取方案：\n{error}": "Cannot read preset:\n{error}",
        "已载入方案：{name}": "Preset loaded: {name}",
        "清除最近记录": "Clear recent list",
        "（暂无）": "(none)",
        "正在处理": "Processing",
        "正在取消：已处理的文件会保留，可在结果中撤销…": (
            "Cancelling: already processed files are kept and can be undone in the results…"
        ),
        "光圈": "Aperture",
        "原文件名": "Original name",
        "拍摄时间": "Shot time",
        "预览": "Preview",
        "结果": "Result",
        "状态": "Status",
        "待预览": "Pending",
        "就绪": "Ready",
        "冲突已处理": "Conflict resolved",
        "未更改": "Unchanged",
        "错误": "Error",
        "成功": "Success",
        "失败": "Failed",
        "跳过": "Skipped",
        "已还原": "Restored",
        "已撤销": "Undone",
        "格式示例：{sample}": "Format example: {sample}",
        "已读取 {count} 个文件：{detail}": "Read {count} files: {detail}",
        "视频 {count}": "Video {count}",
        "回退 {count}": "Fallback {count}",
        "EXIF {count}": "EXIF {count}",
        "未找到拍摄时间": "No media time found",
        "EXIF 拍摄时间": "EXIF shot time",
        "XMP 拍摄时间": "XMP date",
        "图片文本时间": "Image text date",
        "视频拍摄时间": "Video capture time",
        "视频标签时间": "Video tag date",
        "音频标签时间": "Audio tag date",
        "媒体标签时间": "Media tag date",
        "文件修改时间": "File modified time",
        "文件创建时间": "File created time",
        "文件修改时间（未找到拍摄时间）": "File modified time (no shot time found)",
        "EXIF 拍摄时间（已转换为本地时间）": "EXIF shot time (converted to local)",
        "视频拍摄时间（UTC）": "Video capture time (UTC)",
        "视频拍摄时间（UTC → 本地）": "Video capture time (UTC → local)",
        "自动解决冲突": "Auto-resolve conflicts",
        "命名冲突时自动追加 (1)、(2)…": "Append (1), (2)… when names collide",
        "已清空文件列表": "File list cleared",
        "排序已更新，编号将按当前顺序生成": "Sort updated; numbering follows the current order",
        "顺序已更新，编号将按当前顺序生成": "Order updated; numbering follows the current order",
        "确定要从列表中移除全部 {count} 个文件吗？\n这不会删除磁盘上的文件。": "Remove all {count} files from the list?\nThis does not delete files on disk.",
    },
    "ja": {
        "0 个文件": "0 ファイル",
        "EXIF 时间通常没有时区信息，默认保持原始值；视频 mvhd 是 UTC，选择“转换为本地时间”会按系统时区转换。": (
            "EXIF の時刻には通常タイムゾーン情報がないため、既定では元の値を保持します。"
            "動画の mvhd は UTC で、「ローカル時刻に変換」を選ぶとシステムのタイムゾーンで変換します。"
        ),
        "ISO 感光度": "ISO 感度",
        "一键还原": "ワンクリック復元",
        "一键还原…": "ワンクリック復元…",
        "上移": "上へ",
        "下移": "下へ",
        "不改变": "変更しない",
        "不足位补齐": "ゼロ埋め",
        "专辑 / 系列": "アルバム / シリーズ",
        "个字符": "文字",
        "个字符开始": "文字目から",
        "中文": "中文",
        "仅替换首次匹配": "最初の一致のみ置換",
        "从文件名第": "ファイル名の",
        "优先读取 EXIF 与视频 mvhd 时间；找不到时自动回退文件修改时间，并在“拍摄时间”列用 ⓘ 标出。": (
            "EXIF と動画の mvhd 時刻を優先して読み取り、見つからない場合はファイルの更新時刻に"
            "自動でフォールバックし、「撮影日時」列に ⓘ で表示します。"
        ),
        "位数": "桁数",
        "使用 * 插入原始文件名，使用 # 插入编号；\n点击下方占位符可插入日期、拍摄时间、文件大小等内容。": (
            "* で元のファイル名、# で連番を挿入します。\n"
            "下のプレースホルダーをクリックすると、日付・撮影日時・ファイルサイズなどを挿入できます。"
        ),
        "使用正则表达式": "正規表現を使用",
        "使用说明": "使い方",
        "例如：A_#，留空则保留原名": "例：A_#（空欄の場合は元の名前を保持）",
        "元数据": "メタデータ",
        "先写入 JSON 备份，再用临时名两阶段改名；失败自动回滚": (
            "先に JSON バックアップを書き込み、一時名を経て 2 段階で改名します。"
            "失敗時は自動でロールバックします。"
        ),
        "光圈，如 f/2.8": "絞り値（例：f/2.8）",
        "全选": "すべて選択",
        "全部扩展名": "すべての拡張子",
        "全部移除": "すべて削除",
        "共删除": "削除合計",
        "关于": "バージョン情報",
        "关闭": "閉じる",
        "准备中…": "準備中…",
        "分钟": "分",
        "删除": "削除",
        "删除文件名中所有匹配文本": "ファイル名内の一致するテキストをすべて削除",
        "删除文件名中的": "ファイル名から削除",
        "刷新列表": "リストを更新",
        "包含扩展名": "拡張子を含める",
        "区分大小写": "大文字と小文字を区別",
        "原位置被占用时": "元の場所が使用中の場合",
        "原文件名（不含扩展名）": "元のファイル名（拡張子なし）",
        "发布年份": "公開年",
        "取消": "キャンセル",
        "含子文件夹": "サブフォルダーを含める",
        "命名规则": "命名規則",
        "命名规则、编号、扩展名与大小写。规则为空时保留原文件名。": (
            "命名規則・連番・拡張子・大文字小文字。規則が空の場合は元のファイル名を保持します。"
        ),
        "增量": "増分",
        "备份与还原": "バックアップと復元",
        "备份目录里还没有记录": "バックアップフォルダーに記録はまだありません",
        "备份管理": "バックアップ管理",
        "备份管理…": "バックアップ管理…",
        "外观设置": "外観設定",
        "夜间": "ダーク",
        "大写": "大文字",
        "字母编号": "英字連番",
        "导入方案": "プリセットを読み込み",
        "导入方案…": "プリセットを読み込み…",
        "导出方案": "プリセットを書き出し",
        "导出方案…": "プリセットを書き出し…",
        "小写": "小文字",
        "小时": "時",
        "帮助": "ヘルプ",
        "年份": "年",
        "开始于": "開始値",
        "开始重命名": "改名を開始",
        "当前文件": "現在のファイル",
        "或输入 mp4;mkv": "または mp4;mkv を入力",
        "所有改名操作执行前都会自动生成 JSON 备份": (
            "すべての改名操作の前に JSON バックアップを自動作成します"
        ),
        "打开备份目录": "バックアップフォルダーを開く",
        "扩展删除": "拡張子の削除",
        "扩展名": "拡張子",
        "扩展名改成": "拡張子を次に変更",
        "扩展添加": "拡張子の追加",
        "批量文件改名": "一括ファイル名変更",
        "批量重命名 · 预览先行 · 随时可还原": (
            "一括改名 · プレビュー優先 · いつでも復元"
        ),
        "把": "を",
        "拍摄时间原文（EXIF / 视频）": "撮影日時（元データ・EXIF / 動画）",
        "拍摄时间（EXIF / 视频）": "撮影日時（EXIF / 動画）",
        "按 EXIF 原始时间": "EXIF の元の時刻を使用",
        "按修改时间排序": "更新時刻で並べ替え",
        "按名称排序": "名前で並べ替え",
        "按大小排序": "サイズで並べ替え",
        "按序号排序": "連番で並べ替え",
        "按拍摄时间排序": "撮影日時で並べ替え",
        "插入占位符": "プレースホルダーを挿入",
        "撤销上一次重命名": "直前の改名を元に戻す",
        "撤销本次重命名": "今回の改名を元に戻す",
        "改变扩展名为大写": "拡張子を大文字に",
        "改变扩展名为小写": "拡張子を小文字に",
        "改变文件名为大写": "ファイル名を大文字に",
        "改变文件名为小写": "ファイル名を小文字に",
        "改变文件名和扩展名为大写": "ファイル名と拡張子を大文字に",
        "改变文件名和扩展名为小写": "ファイル名と拡張子を小文字に",
        "整体": "全体",
        "文件": "ファイル",
        "文件修改时间": "ファイル更新時刻",
        "文件列表": "ファイル一覧",
        "文件创建时间": "ファイル作成時刻",
        "文件名前添加": "ファイル名の先頭に追加",
        "文件名后添加": "ファイル名の末尾に追加",
        "文件名称选项": "ファイル名オプション",
        "文件大小": "ファイルサイズ",
        "日": "日",
        "日期时间：2026-11-21_214000": "日時：2026-11-21_214000",
        "日期来源": "日付の取得元",
        "日期格式": "日付フォーマット",
        "日期：2026-11-21（格式见上方设置）": "日付：2026-11-21（形式は上の設定を参照）",
        "日本語": "日本語",
        "时区": "タイムゾーン",
        "时间：214000": "時刻：214000",
        "替换": "置換",
        "替换成": "に置換",
        "替换成（可留空表示删除）": "置換後（空欄の場合は削除）",
        "替换文件名中的字符": "ファイル名の文字を置換",
        "最近方案": "最近のプリセット",
        "月份": "月",
        "未选择文件": "ファイルが選択されていません",
        "标题 / 曲名": "タイトル / 曲名",
        "正则示例：^IMG_(\\d+) → 照片_$1\n支持 $1、\\1 或 ${name} 形式的捕获组引用。": (
            "正規表現の例：^IMG_(\\d+) → 写真_$1\n"
            "$1、\\1、${name} 形式のキャプチャグループ参照に対応しています。"
        ),
        "正在重命名": "改名中",
        "每次改名都会先写入 JSON 备份。选择一批已完成的记录即可把文件还原到原名称；原位置被占用时默认跳过，不会覆盖。": (
            "改名のたびに先に JSON バックアップを書き込みます。完了した記録を選ぶとファイルを"
            "元の名前に復元できます。元の場所が使用中の場合は既定でスキップし、上書きはしません。"
        ),
        "添加": "追加",
        "添加删除": "追加 / 削除",
        "添加在文件名最前面": "ファイル名の先頭に追加",
        "添加在文件名最后面": "ファイル名の末尾に追加",
        "添加字符串": "文字列を追加",
        "添加文件": "ファイルを追加",
        "添加文件…": "ファイルを追加…",
        "添加文件夹": "フォルダーを追加",
        "添加文件夹…": "フォルダーを追加…",
        "添加文件夹时一并扫描子文件夹中的文件": (
            "フォルダー追加時にサブフォルダー内のファイルも走査する"
        ),
        "清空列表": "リストをクリア",
        "清空拍摄时间缓存，重新读取列表中全部文件（文件被外部修改后使用）": (
            "撮影日時のキャッシュをクリアし、リスト内のすべてのファイルを再読み取りします"
            "（外部でファイルが変更された場合に使用）。"
        ),
        "清除筛选": "フィルターを解除",
        "点击“添加”选择文件，或直接把文件/文件夹拖到窗口里。\n所有改动都只显示在“预览”列，确认后才会写入磁盘。": (
            "「追加」をクリックしてファイルを選ぶか、ファイル／フォルダーをウィンドウに"
            "ドラッグしてください。\n変更は「プレビュー」列にのみ表示され、確認後にのみ"
            "ディスクへ書き込まれます。"
        ),
        "点击占位符会插入到上方命名规则的光标位置。": (
            "プレースホルダーをクリックすると、上の命名規則のカーソル位置に挿入されます。"
        ),
        "白天": "ライト",
        "相机型号": "カメラ機種",
        "秒": "秒",
        "移除": "削除",
        "移除所选": "選択項目を削除",
        "筛选": "フィルター",
        "筛选扩展名": "拡張子で絞り込み",
        "筛选扩展名…": "拡張子で絞り込み…",
        "编号": "連番",
        "编号（同 #）": "連番（# と同じ）",
        "编辑": "編集",
        "置底": "最下部へ",
        "置顶": "最上部へ",
        "自动加序号 (1)、(2)…": "自動連番 (1)、(2)…",
        "自动解决命名冲突（追加 (1)、(2)…）": (
            "名前の衝突を自動解決"
        ),
        "自定义": "カスタム",
        "自定义格式": "カスタム形式",
        "艺术家 / 导演": "アーティスト / 監督",
        "要插入的字符串": "挿入する文字列",
        "要查找的文本": "検索するテキスト",
        "视图": "表示",
        "语言": "言語",
        "请选择要还原的批次": "復元するバッチを選択してください",
        "跟随系统": "システムに合わせる",
        "跳过，不覆盖（推荐）": "スキップして上書きしない（推奨）",
        "转换为本地时间": "ローカル時刻に変換",
        "还原所选": "選択項目を復元",
        "还没有添加文件": "ファイルがまだ追加されていません",
        "退出": "終了",
        "重命名完成": "改名完了",
        "重新读取元数据": "メタデータを再読み取り",
        "重置为默认设置": "既定の設定に戻す",
        "镜头": "レンズ",
        "风格 / 分类": "ジャンル / カテゴリ",
        # ---- 動的テンプレートとヒント ----
        "{total} 个文件 · 筛选 {filter} · 预计成功 {ready} · 冲突 {conflict} · 错误 {error} · 未更改 {unchanged}": (
            "{total} ファイル · フィルター {filter} · 成功見込み {ready} · 衝突 {conflict} · "
            "エラー {error} · 未変更 {unchanged}"
        ),
        "全部": "すべて",
        "{count} 个文件": "{count} ファイル",
        "筛选 {visible} / {total} 个文件": "{visible} / {total} ファイルを表示",
        "已添加 {added} 个文件（来自 {folders} 个文件夹）": (
            "{folders} 個のフォルダーから {added} ファイルを追加しました"
        ),
        "已添加 {added} 个文件": "{added} ファイルを追加しました",
        "已移除 {removed} 个文件": "{removed} ファイルを削除しました",
        "一次最多添加 {max} 个文件，超出部分已忽略": (
            "一度に追加できるのは最大 {max} ファイルです。超過分は無視されました"
        ),
        "文件：{name}": "ファイル：{name}",
        "大小：{size} · 修改时间：{modified}": "サイズ：{size} · 更新日時：{modified}",
        "拍摄时间：读取中…": "撮影日時：読み取り中…",
        "拍摄时间：{time}（{source}）": "撮影日時：{time}（{source}）",
        "拍摄时间：未检测到（命名时回退文件修改时间）": (
            "撮影日時：未検出（命名時はファイルの更新日時にフォールバック）"
        ),
        "元数据原文：{raw}": "メタデータ（元データ）：{raw}",
        "已选择 {count} 个文件": "{count} ファイルを選択中",
        "未知": "不明",
        "标题": "タイトル",
        "风格": "ジャンル",
        "相机": "カメラ",
        "未检测到拍摄时间，命名时将回退到文件修改时间": (
            "撮影日時が検出されないため、命名時はファイルの更新日時にフォールバックします"
        ),
        "拍摄时间：{time}": "撮影日時：{time}",
        "来源：{source}": "取得元：{source}",
        "未找到媒体时间，已回退到文件修改时间": (
            "メディアの時刻が見つからないため、ファイルの更新日時にフォールバックしました"
        ),
        "标题：{value}": "タイトル：{value}",
        "艺术家 / 导演：{value}": "アーティスト / 監督：{value}",
        "专辑 / 系列：{value}": "アルバム / シリーズ：{value}",
        "风格：{value}": "ジャンル：{value}",
        "年份：{value}": "年：{value}",
        "相机 {value}": "カメラ {value}",
        "镜头 {value}": "レンズ {value}",
        "成功 {success} 个 · 失败 {failed} 个 · 跳过 {skipped} 个": (
            "成功 {success} · 失敗 {failed} · スキップ {skipped}"
        ),
        "原位置被占用而跳过 {count} 个": "元の場所が使用中のため {count} 件をスキップ",
        "文件已不存在 {count} 个": "{count} ファイルが存在しません",
        "该批次没有完全还原，可稍后重试剩余文件。": (
            "このバッチは完全には復元されませんでした。残りのファイルは後で再試行できます。"
        ),
        "…还有 {count} 条失败记录": "…ほか {count} 件の失敗記録",
        "该批次不可还原：只有“完成 / 部分失败”的重命名批次支持一键还原。": (
            "このバッチは復元できません。「完了 / 一部失敗」の改名バッチのみ"
            "ワンクリック復元に対応しています。"
        ),
        "将还原 {count} 个文件": "{count} ファイルを復元します",
        "跳过 {count} 个（原位置被占用）": "{count} 件をスキップ（元の場所が使用中）",
        "缺失 {count} 个": "{count} 件が欠落",
        "读取备份失败：{error}": "バックアップの読み取りに失敗しました：{error}",
        "请先添加要重命名的文件": "先に改名するファイルを追加してください",
        "预览尚未完成，请稍候再点击“开始重命名”": (
            "プレビューがまだ完了していません。「改名を開始」を押す前にお待ちください"
        ),
        "没有需要重命名的文件（全部未更改或存在错误）": (
            "改名が必要なファイルはありません（すべて未変更またはエラー）"
        ),
        "正在撤销": "元に戻しています",
        "正在还原": "復元中",
        "撤销完成": "元に戻しました",
        "还原完成": "復元完了",
        "共 {count} 个文件，按“写入备份 → 临时名 → 目标名”执行。": (
            "{count} ファイルを「バックアップ書き込み → 一時名 → 目的の名前」の順に処理します。"
        ),
        "正在把批次 {batch} 的 {count} 个文件还原到原名称。": (
            "バッチ {batch} の {count} ファイルを元の名前に復元しています。"
        ),
        "正在还原批次 {batch} 的 {count} 个文件。": (
            "バッチ {batch} の {count} ファイルを復元しています。"
        ),
        "操作失败": "操作に失敗しました",
        "执行过程中出现错误：\n{message}\n\n如果已有文件被改动，请重新启动程序，启动时会提示恢复未完成的批次；也可以在“编辑 → 一键还原”中查看备份记录。": (
            "実行中にエラーが発生しました：\n{message}\n\n"
            "すでにファイルが変更されている場合は、アプリを再起動してください。起動時に"
            "未完了のバッチの復元を促します。「編集 → ワンクリック復元」でバックアップ記録を"
            "確認することもできます。"
        ),
        "没有可撤销的重命名记录。": "元に戻せる改名記録がありません。",
        "上一次重命名没有成功项，无需撤销。": (
            "前回の改名に成功した項目がないため、元に戻す必要はありません。"
        ),
        "该批次没有成功改名的文件。": "このバッチには改名に成功したファイルがありません。",
        "该批次没有可还原的文件。": "このバッチには復元できるファイルがありません。",
        "找不到备份记录：{batch}": "バックアップ記録が見つかりません：{batch}",
        "批次：{created}\n将把 {count} 个文件还原到原名称。\n原位置被占用时会跳过，不会覆盖。": (
            "バッチ：{created}\n"
            "{count} ファイルを元の名前に復元します。\n"
            "元の場所が使用中の場合はスキップし、上書きはしません。"
        ),
        "确认还原": "復元の確認",
        "将还原批次 {batch} 的 {count} 个文件；{policy}。": (
            "バッチ {batch} の {count} ファイルを復元します。{policy}。"
        ),
        "跳过被占用的原位置": "使用中の元の場所をスキップ",
        "原位置被占用时自动加序号": "元の場所が使用中の場合は自動で連番を付加",
        "确认退出": "終了の確認",
        "已恢复默认设置": "既定の設定に戻しました",
        "已切换为白天模式": "ライトモードに切り替えました",
        "已切换为夜间模式": "ダークモードに切り替えました",
        "外观已跟随系统": "外観をシステムに合わせました",
        "外观已更新": "外観を更新しました",
        "语言已切换为 {language}": "言語を {language} に切り替えました",
        "备份目录不可用": "バックアップフォルダーを利用できません",
        "无法读取或创建备份目录：{error}\n\n为避免改名后无法还原，已禁用执行操作。": (
            "バックアップフォルダーを読み取れないか作成できません：{error}\n\n"
            "改名後に復元できなくなるのを防ぐため、実行操作を無効にしています。"
        ),
        "发现未完成的重命名": "未完了の改名が見つかりました",
        "已保留未完成批次，可在“编辑 → 一键还原”查看备份。": (
            "未完了のバッチを保持しました。「編集 → ワンクリック復元」でバックアップを"
            "確認できます。"
        ),
        "恢复失败": "復元に失敗しました",
        "恢复完成": "復元完了",
        "已还原 {count} 个文件。{detail}": "{count} ファイルを復元しました。{detail}",
        "无法导入方案：\n{error}": "プリセットを読み込めません：\n{error}",
        "已导入方案：{name}": "プリセットを読み込みました：{name}",
        "无法写入方案：\n{error}": "プリセットを書き出せません：\n{error}",
        "已导出方案：{name}": "プリセットを書き出しました：{name}",
        "方案文件已不存在：\n{path}": "プリセットファイルが存在しません：\n{path}",
        "无法读取方案：\n{error}": "プリセットを読み取れません：\n{error}",
        "已载入方案：{name}": "プリセットを読み込みました：{name}",
        "清除最近记录": "最近の記録を消去",
        "（暂无）": "（なし）",
        "正在处理": "処理中",
        "正在取消：已处理的文件会保留，可在结果中撤销…": (
            "キャンセル中：処理済みのファイルは保持され、結果から元に戻せます…"
        ),
        "光圈": "絞り",
        "原文件名": "元のファイル名",
        "拍摄时间": "撮影日時",
        "预览": "プレビュー",
        "结果": "結果",
        "状态": "状態",
        "待预览": "プレビュー待ち",
        "就绪": "準備完了",
        "冲突已处理": "競合を解決済み",
        "未更改": "変更なし",
        "错误": "エラー",
        "成功": "成功",
        "失败": "失敗",
        "跳过": "スキップ",
        "已还原": "復元済み",
        "已撤销": "元に戻し済み",
        "格式示例：{sample}": "形式の例：{sample}",
        "已读取 {count} 个文件：{detail}": "{count} ファイルを読み取りました：{detail}",
        "视频 {count}": "動画 {count}",
        "回退 {count}": "フォールバック {count}",
        "EXIF {count}": "EXIF {count}",
        "未找到拍摄时间": "撮影日時が見つかりません",
        "EXIF 拍摄时间": "EXIF 撮影日時",
        "XMP 拍摄时间": "XMP 日時",
        "图片文本时间": "画像テキスト日時",
        "视频拍摄时间": "動画の撮影日時",
        "视频标签时间": "動画タグ日時",
        "音频标签时间": "音声タグ日時",
        "媒体标签时间": "メディアタグ日時",
        "文件修改时间": "ファイル更新日時",
        "文件创建时间": "ファイル作成日時",
        "文件修改时间（未找到拍摄时间）": "ファイル更新日時（撮影日時なし）",
        "EXIF 拍摄时间（已转换为本地时间）": "EXIF 撮影日時（ローカル時刻に変換）",
        "视频拍摄时间（UTC）": "動画の撮影日時（UTC）",
        "视频拍摄时间（UTC → 本地）": "動画の撮影日時（UTC → ローカル）",
        "自动解决冲突": "名前の衝突を自動解決",
        "命名冲突时自动追加 (1)、(2)…": "名前が衝突したら (1)、(2)… を自動付加",
        "已清空文件列表": "ファイル一覧をクリアしました",
        "排序已更新，编号将按当前顺序生成": "並べ替えを更新しました。連番は現在の順序で生成されます",
        "顺序已更新，编号将按当前顺序生成": "順序を更新しました。連番は現在の順序で生成されます",
        "确定要从列表中移除全部 {count} 个文件吗？\n这不会删除磁盘上的文件。": "一覧から {count} ファイルをすべて削除しますか？\nディスク上のファイルは削除されません。",
    },
}
