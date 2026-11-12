# 字体来源（全部 SIL Open Font License 1.1，可商用，许可证全文见 OFL.txt）

| 文件 | 字体 | 说明 |
|---|---|---|
| HanSansSC-Subset-VF.otf | 由 Adobe 思源黑体 SC 可变字体（Source Han Sans SC VF 2.003，wght 250–900）裁剪的子集 | 只保留 GB 2312 全部 6763 个汉字和符号区，外加少量医学常用字，约 7.7 MB（原字体 38.8 MB）。按 OFL 第 3 条，修改版不得使用保留字体名“Source”，所以字体内部名称改为 “Han Sans Subset SC VF”，版式里的注册名为 HeiTiSub。原作：https://github.com/adobe-fonts/source-han-sans |

子集缺字时，成片 QA（tools/check_fonts.py）会逐字报出来。要用完整字体：从原作下载 SourceHanSansSC-VF.otf 放进专题的 assets/fonts/，把专题 layout.json 里 fonts.files.HeiTiSub.src 改成它。
